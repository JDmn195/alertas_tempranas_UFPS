import logging
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.utils import timezone

from academico.models import Nota, Periodo, Estudiante
from academico.constants import NOTA_APROBATORIA, PESO_CORTES, PESO_EXAMEN, CANTIDAD_CORTES
from alertas.models import Regla, Alerta
from alertas.services import NotificationService
from usuarios.utils import registrar_auditoria

logger = logging.getLogger(__name__)

ESTADOS_CERRADOS = ['cerrada', 'closed']


def calcular_nota_necesaria(c1, c2, c3):
    """
    Nota requerida en el examen final para aprobar con NOTA_APROBATORIA (3.0):
    nota_necesaria = (NOTA_APROBATORIA - promedio_cortes * PESO_CORTES) / PESO_EXAMEN
    Redondeada a 2 decimales usando ROUND_HALF_UP.
    """
    d_c1 = Decimal(str(c1))
    d_c2 = Decimal(str(c2))
    d_c3 = Decimal(str(c3))
    promedio_cortes = (d_c1 + d_c2 + d_c3) / CANTIDAD_CORTES
    necesaria = (NOTA_APROBATORIA - (promedio_cortes * PESO_CORTES)) / PESO_EXAMEN
    return necesaria.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _cumple_operador(valor, operador, umbral):
    if valor is None:
        return False
    try:
        v = float(valor)
        u = float(umbral)
    except (TypeError, ValueError):
        return False
    return {
        '<': v < u,
        '>': v > u,
        '<=': v <= u,
        '>=': v >= u,
        '==': v == u,
    }.get(operador, False)


def _obtener_corte_valor(nota, num_corte):
    if num_corte == 1:
        return nota.corte1
    if num_corte == 2:
        return nota.corte2
    if num_corte == 3:
        return nota.corte3
    return None


def evaluar_cortes_nota(nota, usuario=None):
    """
    Evalúa todas las reglas CORTE activas sobre una nota específica.
    Cada nota se procesa en una transacción atómica (transaction.atomic).
    Notificaciones enviadas en on_commit.
    """
    with transaction.atomic():
        reglas_corte = list(Regla.objects.filter(tipo='CORTE', activo=True).order_by('id'))
        if not reglas_corte:
            return []

        periodo_str = f"{nota.periodo.anio}-{nota.periodo.semestre}"
        curso_id = nota.curso_id
        materia = nota.curso.materia
        estudiante = nota.estudiante

        # Metadatos base
        c1 = float(nota.corte1) if nota.corte1 is not None else None
        c2 = float(nota.corte2) if nota.corte2 is not None else None
        c3 = float(nota.corte3) if nota.corte3 is not None else None

        notas_dict = {
            'corte1': c1,
            'corte2': c2,
            'corte3': c3,
        }

        # 1. Separar reglas CORTE y NOTA_NECESARIA
        reglas_eval_corte = []
        reglas_nota_necesaria = []

        for r in reglas_corte:
            params = r.parametros or {}
            evalua = params.get('evalua')
            if evalua == 'CORTE':
                reglas_eval_corte.append(r)
            elif evalua == 'NOTA_NECESARIA':
                reglas_nota_necesaria.append(r)

        # 2. Evaluar reglas NOTA_NECESARIA
        # Aplican solo si los tres cortes están registrados y examen_final está vacío
        nota_necesaria_val = None
        reglas_nn_aplicables = []

        todos_cortes_registrados = (nota.corte1 is not None and nota.corte2 is not None and nota.corte3 is not None)
        examen_registrado = (nota.examen_final is not None)

        if todos_cortes_registrados and not examen_registrado:
            nota_necesaria_val = calcular_nota_necesaria(nota.corte1, nota.corte2, nota.corte3)
            for r in reglas_nota_necesaria:
                if _cumple_operador(nota_necesaria_val, r.operador, r.valor_umbral):
                    reglas_nn_aplicables.append(r)

        # Regla c: Entre las NOTA_NECESARIA que apliquen a la misma nota,
        # genera solo la de mayor valor_umbral (C4 sobre C3)
        regla_nn_ganadora = None
        if reglas_nn_aplicables:
            reglas_nn_aplicables.sort(key=lambda r: float(r.valor_umbral), reverse=True)
            regla_nn_ganadora = reglas_nn_aplicables[0]

        # 3. Procesar cada regla individualmente
        alertas_afectadas = []

        for r in reglas_corte:
            params = r.parametros or {}
            clave = params.get('clave', '')
            evalua = params.get('evalua')

            # Buscar alerta abierta existente por la llave de unicidad:
            # estudiante + regla + metadata__curso_id + metadata__periodo
            alerta_abierta = (
                Alerta.objects
                .filter(
                    estudiante=estudiante,
                    regla=r,
                    metadata__curso_id=curso_id,
                    metadata__periodo=periodo_str,
                )
                .exclude(estado__in=ESTADOS_CERRADOS)
                .first()
            )

            aplica = False
            valor_causa = None
            motivo_cierre = None
            metadata = {
                'clave': clave,
                'curso_id': curso_id,
                'materia_codigo': materia.codigo,
                'materia_nombre': materia.nombre,
                'grupo': nota.curso.grupo,
                'periodo': periodo_str,
                'notas': notas_dict,
            }

            if evalua == 'CORTE':
                num_corte = params.get('corte')
                corte_val = _obtener_corte_valor(nota, num_corte)
                corte_previo_num = params.get('corte_previo')

                if corte_val is not None:
                    # Si tiene corte_previo y ese corte está vacío, no aplica
                    if corte_previo_num is not None:
                        corte_previo_val = _obtener_corte_valor(nota, corte_previo_num)
                        if corte_previo_val is not None:
                            cumple_ppal = _cumple_operador(corte_val, r.operador, r.valor_umbral)
                            cumple_previo = _cumple_operador(
                                corte_previo_val,
                                params.get('operador_previo'),
                                params.get('umbral_previo')
                            )
                            if cumple_ppal and cumple_previo:
                                aplica = True
                                valor_causa = corte_val
                    else:
                        if _cumple_operador(corte_val, r.operador, r.valor_umbral):
                            aplica = True
                            valor_causa = corte_val

                metadata['corte'] = num_corte
                motivo_cierre = "Nota corregida"

            elif evalua == 'NOTA_NECESARIA':
                if r == regla_nn_ganadora and nota_necesaria_val is not None:
                    aplica = True
                    valor_causa = nota_necesaria_val

                if nota_necesaria_val is not None:
                    metadata['nota_necesaria'] = float(nota_necesaria_val)

                # Determinar motivo de cierre si ya no aplica
                if examen_registrado:
                    motivo_cierre = "Examen final registrado"
                elif clave == 'C3' and regla_nn_ganadora and (regla_nn_ganadora.parametros or {}).get('clave') == 'C4':
                    motivo_cierre = "Superada por C4"
                else:
                    motivo_cierre = "Nota corregida"

            # Aplicar acciones e / f
            if aplica:
                if alerta_abierta:
                    # Actualizar si cambiaron valor_causa o metadata
                    cambio = False
                    if alerta_abierta.valor_causa != valor_causa:
                        alerta_abierta.valor_causa = valor_causa
                        cambio = True
                    if alerta_abierta.metadata != metadata:
                        alerta_abierta.metadata = metadata
                        cambio = True
                    if cambio:
                        alerta_abierta.save(update_fields=['valor_causa', 'metadata'])
                    alertas_afectadas.append(alerta_abierta)
                else:
                    # Crear nueva alerta activa
                    nueva_alerta = Alerta.objects.create(
                        estudiante=estudiante,
                        regla=r,
                        estado='activa',
                        valor_causa=valor_causa,
                        metadata=metadata,
                    )
                    alertas_afectadas.append(nueva_alerta)

                    # Registrar auditoría (mismo tipo que el motor de alertas)
                    registrar_auditoria(
                        usuario,
                        'GENERAR_ALERTAS',
                        f"Alerta generada por regla '{r.nombre}' (clave {clave}) para estudiante {estudiante.codigo} en curso {materia.codigo}-{nota.curso.grupo}."
                    )

                    # Notificar en transaction.on_commit
                    alerta_id = nueva_alerta.id
                    def _enviar_notif(aid=alerta_id):
                        try:
                            al_obj = Alerta.objects.select_related('estudiante', 'regla').get(id=aid)
                            NotificationService.notificar_alerta(al_obj)
                        except Exception as e:
                            logger.error("Error al notificar alerta por corte %s: %s", aid, e, exc_info=True)

                    transaction.on_commit(_enviar_notif)

            else:
                # No aplica: si había alerta abierta, cerrarla
                if alerta_abierta:
                    alerta_abierta.estado = 'cerrada'
                    meta = alerta_abierta.metadata or {}
                    meta['cierre_automatico'] = True
                    meta['motivo_cierre'] = motivo_cierre
                    alerta_abierta.metadata = meta
                    alerta_abierta.save()  # Dispara post_save signals (cancelación de recordatorios)

                    registrar_auditoria(
                        usuario,
                        'CERRAR_ALERTA',
                        f"Alerta ID {alerta_abierta.id} de regla '{r.nombre}' cerrada automáticamente. Motivo: {motivo_cierre}."
                    )
                    alertas_afectadas.append(alerta_abierta)

        return alertas_afectadas


def evaluar_cortes_estudiante(estudiante, usuario=None):
    """
    Evalúa las notas del estudiante en el periodo más reciente.
    Nunca genera alertas de corte para periodos anteriores.
    """
    periodo_reciente = (
        Periodo.objects
        .filter(nota__estudiante=estudiante)
        .order_by('-anio', '-semestre')
        .first()
    )
    if not periodo_reciente:
        return []

    notas = (
        Nota.objects
        .filter(estudiante=estudiante, periodo=periodo_reciente)
        .select_related('curso__materia', 'curso__docente__usuario', 'periodo')
    )

    alertas = []
    for nota in notas:
        alertas.extend(evaluar_cortes_nota(nota, usuario=usuario))
    return alertas


def evaluar_cortes_periodo_actual(usuario=None):
    """
    Evalúa las notas de todos los estudiantes con notas en el periodo más reciente.
    """
    periodo_reciente = Periodo.objects.order_by('-anio', '-semestre').first()
    if not periodo_reciente:
        return []

    notas = (
        Nota.objects
        .filter(periodo=periodo_reciente)
        .select_related('estudiante', 'curso__materia', 'curso__docente__usuario', 'periodo')
    )

    alertas = []
    for nota in notas:
        alertas.extend(evaluar_cortes_nota(nota, usuario=usuario))
    return alertas
