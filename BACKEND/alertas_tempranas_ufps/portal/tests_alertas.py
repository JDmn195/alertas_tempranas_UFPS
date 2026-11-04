"""
HU-39: Consulta de alertas propias en el portal (GET /api/portal/alertas/ y detalle).

Las alertas se crean con la metadata real de cada origen: alertas.evaluacion (reglas
generales), alertas_corte.evaluar_cortes_nota y alertas_inasistencia._metadata.
"""
from datetime import timedelta
from decimal import Decimal
from unittest import mock

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from academico.models import Curso, Docente, Materia, Nota, Periodo
from alertas.alertas_corte import evaluar_cortes_nota
from alertas.alertas_inasistencia import MOTIVO_CIERRE, _metadata as metadata_inasistencia
from alertas.evaluacion import evaluar_regla
from alertas.models import Alerta, AnotacionIntervencion, Evidencia, Intervencion, Regla
from alertas.services import NotificationService
from usuarios.models import Auditoria, Usuario

from .tests import _auth, _cuenta_estudiante, _estudiante

INDICADORES = {
    'ppa': 2.31, 'reprobadas': 3, 'materias_reprobadas': ['Cálculo I', 'Física I', 'Química'],
    'atraso': 2, 'materias_atrasadas': ['Álgebra Lineal', 'Programación I'], 'semestre_ref': 4,
}


class AlertasPortalBase(TestCase):
    def setUp(self):
        patcher = mock.patch.object(NotificationService, 'notificar_alerta')
        patcher.start()
        self.addCleanup(patcher.stop)

        self.cuenta = _cuenta_estudiante('ana@ufps.edu.co')
        self.ana = _estudiante('1151001', 'Ana Pérez', usuario=self.cuenta)
        self.otra_cuenta = _cuenta_estudiante('luis@ufps.edu.co')
        self.luis = _estudiante('1151002', 'Luis Gómez', usuario=self.otra_cuenta)

        self.periodo = Periodo.objects.create(anio=2026, semestre=1)
        self.periodo_anterior = Periodo.objects.create(anio=2025, semestre=2)
        self.docente_usuario = Usuario.objects.create(nombre='Docente Prueba', correo='docente@ufps.edu.co', rol='DOCENTE')
        self.docente = Docente.objects.create(codigo='D1', nombre='Docente Prueba', tipo_vinculacion='PLANTA',
                                              usuario=self.docente_usuario)
        self.calculo = Curso.objects.create(materia=Materia.objects.create(codigo='1150101', nombre='Cálculo I',
                                                                           creditos=4, semestre=1),
                                            grupo='A', docente=self.docente)
        self.fisica = Curso.objects.create(materia=Materia.objects.create(codigo='1150102', nombre='Física I',
                                                                          creditos=4, semestre=2),
                                           grupo='B', docente=self.docente)

        # Reglas CORTE (C1..C4) e INASISTENCIA: migraciones 0016 y 0018
        self.regla_inasistencia = Regla.objects.get(tipo='INASISTENCIA')
        self.regla_promedio = Regla.objects.create(nombre='Promedio Crítico', tipo='PROMEDIO', operador='<',
                                                   valor_umbral=Decimal('2.5'), nivel='high')
        self.regla_reprobacion = Regla.objects.create(nombre='Materias reprobadas', tipo='REPROBACION', operador='>',
                                                      valor_umbral=Decimal('2'), nivel='medium')
        self.regla_atraso = Regla.objects.create(nombre='Atraso curricular', tipo='ATRASO', operador='>=',
                                                 valor_umbral=Decimal('2'), nivel='low')

    # -- creación de alertas con la metadata de cada origen ---------------------------

    def alerta_general(self, regla, estudiante=None, estado='activa', dias=0):
        aplica, valor, metadata = evaluar_regla(regla, INDICADORES)
        self.assertTrue(aplica)
        return self._crear(estudiante or self.ana, regla, estado, valor, metadata, dias)

    def alertas_corte(self, c1=None, c2=None, c3=None, examen=None, curso=None, periodo=None, estudiante=None):
        nota, _ = Nota.objects.update_or_create(
            estudiante=estudiante or self.ana, curso=curso or self.calculo, periodo=periodo or self.periodo,
            defaults={'corte1': c1, 'corte2': c2, 'corte3': c3, 'examen_final': examen},
        )
        evaluar_cortes_nota(nota)
        return Alerta.objects.filter(estudiante=nota.estudiante, regla__tipo='CORTE')

    def alerta_inasistencia(self, estudiante=None, curso=None, periodo='2026-1', estado='activa', dias=0):
        resultado = {'porcentaje': Decimal('33.33'), 'total_clases': 6, 'faltas': 2, 'faltas_justificadas': 1}
        metadata = metadata_inasistencia(curso or self.fisica, periodo, resultado, Decimal('20'), 'regla')
        return self._crear(estudiante or self.ana, self.regla_inasistencia, estado, resultado['porcentaje'],
                           metadata, dias)

    def _crear(self, estudiante, regla, estado, valor, metadata, dias):
        alerta = Alerta.objects.create(estudiante=estudiante, regla=regla, estado=estado,
                                       valor_causa=valor, metadata=metadata)
        if dias:
            Alerta.objects.filter(pk=alerta.pk).update(fecha_generacion=timezone.now() - timedelta(days=dias))
        return alerta

    # -- llamadas ---------------------------------------------------------------------

    def listar(self, usuario=None, **params):
        return self.client.get(reverse('portal-alertas'), params, **_auth(usuario or self.cuenta))

    def detalle(self, alerta_id, usuario=None):
        return self.client.get(reverse('portal-alerta-detalle', args=[alerta_id]), **_auth(usuario or self.cuenta))

    def ids(self, resp):
        self.assertEqual(resp.status_code, 200, resp.content)
        return [a['id'] for a in resp.json()['alertas']]


class ListadoAlertasTests(AlertasPortalBase):

    def test_solo_ve_sus_alertas_ordenadas_de_la_mas_reciente(self):
        antigua = self.alerta_general(self.regla_promedio, dias=10)
        reciente = self.alerta_inasistencia(dias=1)
        hoy = self.alerta_general(self.regla_atraso)
        ajenas = [self.alerta_general(self.regla_promedio, estudiante=self.luis),
                  self.alerta_inasistencia(estudiante=self.luis)]

        resp = self.listar()
        self.assertEqual(self.ids(resp), [hoy.id, reciente.id, antigua.id])
        for ajena in ajenas:
            self.assertNotIn(ajena.id, self.ids(resp))

        # Luis solo ve las suyas, aunque pida el código de Ana
        self.assertEqual(sorted(self.ids(self.listar(self.otra_cuenta, codigo=self.ana.codigo))),
                         sorted(a.id for a in ajenas))

    def test_campos_del_listado(self):
        self.alerta_inasistencia()
        alerta = self.listar().json()['alertas'][0]
        self.assertEqual(alerta['tipo'], self.regla_inasistencia.nombre)
        self.assertEqual(alerta['categoria'], 'INASISTENCIA')
        self.assertEqual(alerta['origen'], 'inasistencia')
        self.assertEqual((alerta['severidad'], alerta['severidad_texto']), ('high', 'Alta'))
        self.assertEqual((alerta['estado'], alerta['estado_texto']), ('activa', 'Activa'))
        self.assertEqual((alerta['periodo'], alerta['materia']), ('2026-1', 'Física I'))
        self.assertIsNone(alerta['fecha_cierre'])
        self.assertTrue(alerta['fecha_generacion'])
        self.assertNotIn('explicacion', alerta)

    def test_conteos_por_estado_y_periodos(self):
        self.alerta_general(self.regla_promedio)
        self.alerta_general(self.regla_reprobacion, estado='en_seguimiento')
        self.alerta_general(self.regla_atraso, estado='closed')  # nombre antiguo del estado
        self.alerta_inasistencia(periodo='2025-2', estado='cerrada')
        self.alerta_inasistencia(periodo='2026-1', estado='atendida')
        self.alerta_general(self.regla_promedio, estudiante=self.luis)

        data = self.listar(estado='activa').json()
        self.assertEqual(data['conteos'],
                         {'activa': 1, 'en_seguimiento': 1, 'atendida': 1, 'cerrada': 2, 'total': 5})
        self.assertEqual(data['periodos'], ['2026-1', '2025-2'])

    def test_sin_alertas_lista_vacia_con_mensaje(self):
        resp = self.listar()
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['alertas'], [])
        self.assertEqual(data['conteos']['total'], 0)
        self.assertIn('No tienes alertas', data['mensaje'])

    def test_filtros_sin_resultados_mensaje_distinto(self):
        self.alerta_general(self.regla_promedio)
        data = self.listar(estado='cerrada').json()
        self.assertEqual(data['alertas'], [])
        self.assertIn('filtros', data['mensaje'])


class FiltrosAlertasTests(AlertasPortalBase):
    def setUp(self):
        super().setUp()
        self.promedio = self.alerta_general(self.regla_promedio)
        self.atraso_cerrada = self.alerta_general(self.regla_atraso, estado='cerrada')
        self.inasistencia_actual = self.alerta_inasistencia(periodo='2026-1', estado='en_seguimiento')
        self.inasistencia_anterior = self.alerta_inasistencia(periodo='2025-2', estado='cerrada')
        self.cortes = list(self.alertas_corte(c1=1.5))  # C1 activa en 2026-1
        self.ajena = self.alerta_inasistencia(estudiante=self.luis, periodo='2026-1')

    def assertIds(self, resp, esperadas):
        self.assertEqual(sorted(self.ids(resp)), sorted(a.id for a in esperadas))

    def test_filtro_por_estado(self):
        self.assertIds(self.listar(estado='activa'), [self.promedio, *self.cortes])
        self.assertIds(self.listar(estado='cerrada'), [self.atraso_cerrada, self.inasistencia_anterior])
        self.assertIds(self.listar(estado='en_seguimiento'), [self.inasistencia_actual])
        self.assertIds(self.listar(estado='atendida'), [])

    def test_filtro_por_periodo(self):
        self.assertIds(self.listar(periodo='2026-1'), [self.inasistencia_actual, *self.cortes])
        self.assertIds(self.listar(periodo='2025-2'), [self.inasistencia_anterior])
        self.assertIds(self.listar(periodo='2024-1'), [])

    def test_filtro_por_tipo(self):
        self.assertIds(self.listar(tipo='INASISTENCIA'), [self.inasistencia_actual, self.inasistencia_anterior])
        self.assertIds(self.listar(tipo='corte'), self.cortes)  # no distingue mayúsculas
        self.assertIds(self.listar(tipo='PROMEDIO'), [self.promedio])

    def test_filtros_combinados(self):
        self.assertIds(self.listar(estado='cerrada', tipo='INASISTENCIA'), [self.inasistencia_anterior])
        self.assertIds(self.listar(estado='en_seguimiento', periodo='2026-1'), [self.inasistencia_actual])
        self.assertIds(self.listar(estado='activa', periodo='2026-1', tipo='CORTE'), self.cortes)
        self.assertIds(self.listar(estado='cerrada', periodo='2026-1', tipo='INASISTENCIA'), [])
        self.assertEqual(self.listar(estado='activa', tipo='CORTE').json()['filtros'],
                         {'estado': 'activa', 'tipo': 'CORTE'})

    def test_filtros_invalidos_400(self):
        casos = [
            ({'estado': 'pendiente'}, 'estado'),
            ({'periodo': '2026'}, 'periodo'),
            ({'periodo': '2026-3'}, 'periodo'),
            ({'periodo': 'abc-1'}, 'periodo'),
            ({'tipo': 'NOTAS'}, 'tipo'),
            ({'estado': 'activa', 'tipo': 'X'}, 'tipo'),  # un filtro válido no salva al inválido
        ]
        for params, campo in casos:
            with self.subTest(params=params):
                resp = self.listar(**params)
                self.assertEqual(resp.status_code, 400)
                self.assertEqual(set(resp.json()['detalle']), {campo})


class DetalleAlertaTests(AlertasPortalBase):

    def explicacion(self, alerta):
        resp = self.detalle(alerta.id)
        self.assertEqual(resp.status_code, 200, resp.content)
        return resp.json()

    def test_regla_promedio(self):
        data = self.explicacion(self.alerta_general(self.regla_promedio))
        exp = data['explicacion']
        self.assertEqual(data['origen'], 'general')
        self.assertIsNone(data['periodo'])
        self.assertEqual(exp['valores'], {'valor': 2.31, 'umbral': 2.5, 'operador': '<'})
        self.assertIn('2.31', exp['mensaje'])
        self.assertIn('menor que 2.50', exp['mensaje'])
        self.assertTrue(exp['recomendacion'])
        self.assertIsNone(data['cierre'])

    def test_regla_reprobacion_y_atraso(self):
        exp = self.explicacion(self.alerta_general(self.regla_reprobacion))['explicacion']
        self.assertEqual(exp['valores']['valor'], 3)
        self.assertEqual(exp['valores']['umbral'], 2)
        self.assertEqual(exp['valores']['materias'], INDICADORES['materias_reprobadas'])
        self.assertIn('3 materias reprobadas', exp['mensaje'])

        exp = self.explicacion(self.alerta_general(self.regla_atraso))['explicacion']
        self.assertEqual((exp['valores']['valor'], exp['valores']['umbral'], exp['valores']['semestre']), (2, 2, 4))
        self.assertIn('Programación I', [d['valor'] for d in exp['datos']][-1])
        self.assertIn('2 materias de línea', exp['mensaje'])

    def test_alerta_de_corte_c1(self):
        c1 = self.alertas_corte(c1=1.5).get(regla__parametros__clave='C1')
        data = self.explicacion(c1)
        valores = data['explicacion']['valores']
        self.assertEqual(data['origen'], 'corte')
        self.assertEqual(data['severidad'], 'medium')
        self.assertEqual((valores['materia'], valores['grupo'], valores['periodo']), ('Cálculo I', 'A', '2026-1'))
        self.assertEqual((valores['corte'], valores['nota'], valores['nota_necesaria']), (1, 1.5, None))
        self.assertIn('1.5 en el corte 1', data['explicacion']['mensaje'])
        self.assertIn('Cálculo I, grupo A, periodo 2026-1', data['explicacion']['mensaje'])

    def test_alerta_de_corte_c2a(self):
        c2a = self.alertas_corte(c1=2.5, c2=2.0).get(regla__parametros__clave='C2A')
        exp = self.explicacion(c2a)['explicacion']
        self.assertEqual((exp['valores']['corte'], exp['valores']['nota']), (2, 2.0))
        self.assertIn('2.0 en el corte 2 y 2.5 en el corte 1', exp['mensaje'])

    def test_alerta_de_corte_c3_y_c4_con_nota_necesaria(self):
        # Promedio 3.0 → necesita (3.0 - 2.1) / 0.3 = 3.0: sin C3. Promedio 2.0 → necesita 5.33: C4
        c4 = self.alertas_corte(c1=1.5, c2=2.0, c3=2.5).get(regla__parametros__clave='C4')
        exp = self.explicacion(c4)['explicacion']
        self.assertEqual(exp['valores']['nota_necesaria'], 5.33)
        self.assertEqual(exp['valores']['notas'], {'corte1': 1.5, 'corte2': 2.0, 'corte3': 2.5})
        self.assertIn('5.33', exp['mensaje'])
        self.assertIn('nota máxima', exp['mensaje'])

        # Promedio 2.5 → necesita (3.0 - 1.75) / 0.3 = 4.17: C3
        c3 = self.alertas_corte(c1=2.5, c2=2.5, c3=2.5, curso=self.fisica).get(regla__parametros__clave='C3')
        data = self.explicacion(c3)
        self.assertEqual(data['explicacion']['valores']['nota_necesaria'], 4.17)
        self.assertEqual((data['materia'], data['periodo']), ('Física I', '2026-1'))
        self.assertIn('necesitas 4.17 en el examen final', data['explicacion']['mensaje'])

    def test_alerta_de_inasistencia(self):
        data = self.explicacion(self.alerta_inasistencia())
        exp = data['explicacion']
        self.assertEqual(exp['valores'], {
            'materia': 'Física I', 'grupo': 'B', 'periodo': '2026-1', 'porcentaje': 33.33, 'umbral': 20.0,
            'faltas': 2, 'total_clases': 6, 'faltas_justificadas': 1,
        })
        self.assertIn('2 faltas sin justificar de 6 clases', exp['mensaje'])
        self.assertIn('33.3 %', exp['mensaje'])
        self.assertIn('20.0 %', exp['mensaje'])

    def test_cierre_automatico_muestra_motivo_y_fecha(self):
        alertas = self.alertas_corte(c1=1.5)
        c1 = alertas.get(regla__parametros__clave='C1')
        self.alertas_corte(c1=3.5)  # nota corregida: el origen cierra la alerta
        c1.refresh_from_db()
        self.assertEqual(c1.estado, 'cerrada')

        data = self.explicacion(c1)
        self.assertEqual(data['estado'], 'cerrada')
        self.assertTrue(data['cierre_automatico'])
        self.assertEqual(data['cierre']['motivo'], 'Nota corregida')
        self.assertIn('se cerró automáticamente: Nota corregida', data['cierre']['mensaje'])
        self.assertIsNotNone(data['fecha_cierre'])
        self.assertEqual(data['cierre']['fecha'], data['fecha_cierre'])

    def test_cierre_automatico_de_inasistencia(self):
        alerta = self.alerta_inasistencia()
        alerta.estado = 'cerrada'
        alerta.metadata = {**alerta.metadata, 'cierre_automatico': True, 'motivo_cierre': MOTIVO_CIERRE}
        alerta.save()
        cierre = self.explicacion(alerta)['cierre']
        self.assertEqual((cierre['automatico'], cierre['motivo']), (True, MOTIVO_CIERRE))

    def test_cierre_manual_sin_motivo_automatico(self):
        alerta = self.alerta_general(self.regla_promedio)
        alerta.estado = 'cerrada'
        alerta.save(update_fields=['estado'])  # como el cierre de la re-evaluación
        data = self.explicacion(alerta)
        self.assertFalse(data['cierre']['automatico'])
        self.assertIsNone(data['cierre']['motivo'])
        self.assertIsNotNone(data['cierre']['fecha'])

    def test_alerta_ajena_404_y_auditoria(self):
        ajena = self.alerta_inasistencia(estudiante=self.luis)
        resp = self.detalle(ajena.id)
        self.assertEqual(resp.status_code, 404)
        self.assertNotIn('Luis', resp.content.decode())
        self.assertNotIn('Física', resp.content.decode())

        registro = Auditoria.objects.get(usuario=self.cuenta, tipo_accion='ACCESO_DENEGADO')
        self.assertIn(f'alerta ID {ajena.id}', registro.detalle)
        self.assertIn(self.luis.codigo, registro.detalle)

    def test_alerta_inexistente_misma_respuesta_404(self):
        ajena = self.alerta_inasistencia(estudiante=self.luis)
        inexistente = self.detalle(ajena.id + 1000)
        self.assertEqual(inexistente.status_code, 404)
        self.assertEqual(inexistente.json(), self.detalle(ajena.id).json())
        self.assertEqual(Auditoria.objects.filter(usuario=self.cuenta, tipo_accion='ACCESO_DENEGADO').count(), 2)


class FechaCierreTests(AlertasPortalBase):
    """Alerta.fecha_cierre sigue al estado en cualquier vía de guardado."""

    def test_se_asigna_al_cerrar_y_se_limpia_al_reabrir(self):
        alerta = self.alerta_general(self.regla_promedio)
        self.assertIsNone(alerta.fecha_cierre)

        alerta.estado = 'cerrada'
        alerta.save(update_fields=['estado'])
        alerta.refresh_from_db()
        fecha = alerta.fecha_cierre
        self.assertIsNotNone(fecha)

        alerta.save()  # guardar de nuevo no cambia la fecha
        alerta.refresh_from_db()
        self.assertEqual(alerta.fecha_cierre, fecha)

        alerta.estado = 'activa'
        alerta.save(update_fields=['estado'])
        alerta.refresh_from_db()
        self.assertIsNone(alerta.fecha_cierre)


class PrivacidadYAccesoTests(AlertasPortalBase):

    CAMPOS_LISTADO = {'id', 'tipo', 'categoria', 'origen', 'severidad', 'severidad_texto', 'estado', 'estado_texto',
                      'fecha_generacion', 'fecha_cierre', 'cierre_automatico', 'periodo', 'materia', 'resumen'}

    def test_respuesta_sin_datos_internos(self):
        alerta = self.alerta_inasistencia(estado='en_seguimiento')
        intervencion = Intervencion.objects.create(alerta=alerta, usuario=self.docente_usuario, tipo='TUTORIA',
                                                   observaciones='OBSERVACION-PRIVADA', resultado='RESULTADO-PRIVADO')
        AnotacionIntervencion.objects.create(intervencion=intervencion, usuario=self.docente_usuario,
                                             texto='ANOTACION-PRIVADA')
        Evidencia.objects.create(intervencion=intervencion, archivo_url='https://almacen.test/evidencia-privada.pdf',
                                 nombre_archivo='evidencia-privada.pdf')
        self.alertas_corte(c1=1.5)

        listado = self.listar()
        detalle = self.detalle(alerta.id)
        for resp in (listado, detalle):
            contenido = resp.content.decode()
            for privado in ('OBSERVACION-PRIVADA', 'RESULTADO-PRIVADO', 'ANOTACION-PRIVADA', 'evidencia-privada',
                            'Docente Prueba', 'docente@ufps.edu.co', 'curso_id', 'regla_id', 'origen_umbral',
                            'intervenciones', 'usuario', 'auditoria'):
                self.assertNotIn(privado, contenido)

        data = listado.json()
        self.assertEqual(set(data), {'alertas', 'conteos', 'periodos', 'filtros', 'mensaje'})
        for item in data['alertas']:
            self.assertEqual(set(item), self.CAMPOS_LISTADO)
        self.assertEqual(set(detalle.json()), self.CAMPOS_LISTADO | {'explicacion', 'cierre'})
        self.assertEqual(set(detalle.json()['explicacion']), {'mensaje', 'recomendacion', 'datos', 'valores'})

    def test_sin_token_401(self):
        alerta = self.alerta_general(self.regla_promedio)
        self.assertEqual(self.client.get(reverse('portal-alertas')).status_code, 401)
        self.assertEqual(self.client.get(reverse('portal-alerta-detalle', args=[alerta.id])).status_code, 401)

    def test_cuenta_sin_estudiante_asociado_403(self):
        alerta = self.alerta_general(self.regla_promedio)
        huerfana = _cuenta_estudiante('huerfana@ufps.edu.co')
        self.assertEqual(self.listar(huerfana).status_code, 403)
        self.assertEqual(self.detalle(alerta.id, huerfana).status_code, 403)
        self.assertTrue(Auditoria.objects.filter(usuario=huerfana, tipo_accion='ACCESO_DENEGADO').exists())

    def test_personal_recibe_403(self):
        alerta = self.alerta_general(self.regla_promedio)
        self.assertEqual(self.listar(self.docente_usuario).status_code, 403)
        self.assertEqual(self.detalle(alerta.id, self.docente_usuario).status_code, 403)
