"""
Flujo del portal del estudiante (HU-37): el administrador crea la cuenta, el
estudiante define su contraseña con la recuperación, inicia sesión, consulta su
riesgo y no puede consultar la información de otro estudiante.
"""
import re

from django.core import mail
from django.urls import reverse

from academico.models import Estudiante
from alertas.models import Alerta, Intervencion
from usuarios.models import Auditoria, Usuario

from .base import CONTRASENA, IntegracionTestCase


class FlujoPortalEstudianteTests(IntegracionTestCase):

    def setUp(self):
        super().setUp()
        self.otro = Estudiante.objects.create(
            codigo='1152002', nombre='Luis Gómez', tipo_documento='CC', numero_documento='100200301',
            semestre=2, estado_matricula='ACTIVO', email_institucional='luis@ufps.edu.co',
        )

    def _definir_contrasena(self, correo):
        """El estudiante usa '¿Olvidaste tu contraseña?' para definir su primera contraseña."""
        resp = self.client.post(reverse('solicitar_recuperacion'), data={'email': correo},
                                content_type='application/json')
        self.assertEqual(resp.status_code, 200)
        token = re.search(r'/reset-password/(\S+)', mail.outbox[-1].body).group(1)
        resp = self.client.post(reverse('cambiar_contrasena'), data={'token': token, 'password': CONTRASENA},
                                content_type='application/json')
        self.assertEqual(resp.status_code, 200, resp.content)

    def test_estudiante_consulta_su_riesgo_y_no_el_de_otro(self):
        # 1. El administrador crea la cuenta del estudiante (sin contraseña utilizable)
        resp = self.api('post', 'cuenta_estudiante', self.admin, datos={}, args=[self.estudiante.codigo])
        self.assertEqual(resp.status_code, 201, resp.content)
        cuenta = Usuario.objects.get(correo='ana@ufps.edu.co')
        self.assertEqual(cuenta.rol, 'ESTUDIANTE')
        self.assertEqual(self.login(cuenta, self.estudiante.codigo).status_code, 401)
        self.assertEqual(self.login(cuenta, self.estudiante.numero_documento).status_code, 401)

        # 2. Define su contraseña e inicia sesión
        self._definir_contrasena(cuenta.correo)
        resp = self.login(cuenta)
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()['rol'], 'ESTUDIANTE')

        # 3. Sin cálculo todavía: nivel null con mensaje
        resp = self.api('get', 'portal-riesgo', cuenta)
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.json()['riesgo']['nivel'])

        # 4. Se importa su historial (PPA 2.0 < 2.5) y consulta su riesgo
        resp = self.importar_historial(self.historial_en_riesgo())
        self.assertEqual(resp.status_code, 200, resp.content)
        resp = self.api('get', 'portal-riesgo', cuenta)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data['estudiante']['codigo'], self.estudiante.codigo)
        self.assertEqual(data['riesgo']['nivel'], 'high')
        self.assertEqual(data['riesgo']['periodo'], '2026-1')
        causa = next(c for c in data['causas'] if c['tipo'] == 'PROMEDIO')
        self.assertEqual((causa['regla'], causa['umbral'], causa['valor']), ('Promedio Crítico', 2.5, 2.0))
        self.assertEqual(data['indicadores']['materias_reprobadas'], 1)

        # 5. Intenta consultar a otro estudiante: 403 y queda en la auditoría
        resp = self.api('get', 'detail-student', cuenta, args=[self.otro.codigo])
        self.assertEqual(resp.status_code, 403)
        self.assertNotIn('Luis', resp.content.decode())
        resp = self.api('get', 'portal-riesgo', cuenta, query={'codigo': self.otro.codigo})
        self.assertEqual(resp.json()['estudiante']['codigo'], self.estudiante.codigo)

        registro = Auditoria.objects.filter(usuario=cuenta, tipo_accion='ACCESO_DENEGADO').get()
        self.assertIn(self.otro.codigo, registro.detalle)
        self.assertTrue(Auditoria.objects.filter(tipo_accion='CREAR_CUENTA_ESTUDIANTE', usuario=self.admin).exists())


class FlujoEvolucionPromedioTests(IntegracionTestCase):
    """HU-38: el estudiante inicia sesión y consulta la evolución de su promedio."""

    def test_estudiante_consulta_su_evolucion(self):
        cuenta = self._usuario('Ana Pérez', 'ana@ufps.edu.co', 'ESTUDIANTE')
        self.estudiante.usuario = cuenta
        self.estudiante.save(update_fields=['usuario'])

        # Sin notas: serie vacía
        resp = self.api('get', 'portal-evolucion', cuenta)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['serie'], [])

        # 2025-2 cerrado (Física 2.0) y 2026-1 en curso: un solo periodo con definitivas
        resp = self.importar_historial(self.historial_en_riesgo())
        self.assertEqual(resp.status_code, 200, resp.content)
        data = self.api('get', 'portal-evolucion', cuenta).json()
        self.assertEqual(data['serie'], [
            {'periodo': '2025-2', 'pps': 2.0, 'ppa': 2.0, 'creditos_cursados': 3, 'creditos_aprobados': 0},
        ])
        self.assertFalse(data['historia_suficiente'])

        # Se agrega un periodo anterior aprobado: ya hay tendencia, y coincide con la ficha
        filas = [self.fila('2025-1', '1150101', definitiva=4.0, nombre='Cálculo I')] + self.historial_en_riesgo()
        resp = self.importar_historial(filas)
        self.assertEqual(resp.status_code, 200, resp.content)
        data = self.api('get', 'portal-evolucion', cuenta).json()
        self.assertEqual([p['periodo'] for p in data['serie']], ['2025-1', '2025-2'])
        self.assertEqual(data['tendencia'], 'baja')
        self.assertEqual(data['promedio_actual'], 3.0)

        ficha = self.api('get', 'student-indicators', self.admin, args=[self.estudiante.codigo]).json()
        self.assertEqual(ficha['indicadores']['promedio_acumulado'], data['promedio_actual'])


class FlujoAlertasPortalTests(IntegracionTestCase):
    """HU-39: el estudiante inicia sesión, lista sus alertas, abre una propia y no puede abrir una ajena."""

    def test_estudiante_consulta_sus_alertas(self):
        cuenta = self._usuario('Ana Pérez', 'ana@ufps.edu.co', 'ESTUDIANTE')
        self.estudiante.usuario = cuenta
        self.estudiante.save(update_fields=['usuario'])
        otro = Estudiante.objects.create(
            codigo='1152002', nombre='Luis Gómez', tipo_documento='CC', numero_documento='100200301',
            semestre=2, estado_matricula='ACTIVO', email_institucional='luis@ufps.edu.co',
        )

        # 1. Inicia sesión; aún no tiene alertas
        resp = self.login(cuenta)
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()['rol'], 'ESTUDIANTE')
        data = self.api('get', 'portal-alertas', cuenta).json()
        self.assertEqual(data['alertas'], [])
        self.assertIn('No tienes alertas', data['mensaje'])

        # 2. Se importan los historiales de ambos: PPA 2.0 (PROMEDIO) y cortes de Cálculo I (C1, C2A, C4)
        for codigo in (self.estudiante.codigo, otro.codigo):
            resp = self.importar_historial(self.historial_en_riesgo(), codigo=codigo)
            self.assertEqual(resp.status_code, 200, resp.content)

        resp = self.api('get', 'portal-alertas', cuenta)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        propias = set(Alerta.objects.filter(estudiante=self.estudiante).values_list('id', flat=True))
        ajenas = set(Alerta.objects.filter(estudiante=otro).values_list('id', flat=True))
        self.assertTrue(ajenas)
        self.assertEqual({a['id'] for a in data['alertas']}, propias)
        self.assertEqual({a['categoria'] for a in data['alertas']}, {'PROMEDIO', 'CORTE'})
        self.assertEqual(data['conteos']['activa'], len(propias))
        self.assertEqual(data['periodos'], ['2026-1'])

        # 3. Filtra por tipo y abre el detalle de la alerta C4
        cortes = self.api('get', 'portal-alertas', cuenta, query={'tipo': 'CORTE', 'periodo': '2026-1'}).json()
        self.assertEqual(len(cortes['alertas']), 3)
        c4 = next(a for a in cortes['alertas'] if a['tipo'].startswith('Materia perdida'))
        resp = self.api('get', 'portal-alerta-detalle', cuenta, args=[c4['id']])
        self.assertEqual(resp.status_code, 200)
        detalle = resp.json()
        self.assertEqual(detalle['explicacion']['valores']['nota_necesaria'], 5.33)
        self.assertEqual(detalle['materia'], 'Cálculo I')
        self.assertIn('5.33', detalle['explicacion']['mensaje'])

        # 4. Intenta abrir una alerta de Luis: 404 sin datos y queda en la auditoría
        ajena = next(iter(ajenas))
        resp = self.api('get', 'portal-alerta-detalle', cuenta, args=[ajena])
        self.assertEqual(resp.status_code, 404)
        self.assertNotIn('Luis', resp.content.decode())
        registro = Auditoria.objects.get(usuario=cuenta, tipo_accion='ACCESO_DENEGADO')
        self.assertIn(f'alerta ID {ajena}', registro.detalle)


class FlujoAcompanamientoPortalTests(IntegracionTestCase):
    """HU-40: el personal registra intervenciones y el estudiante consulta su acompañamiento."""

    def test_estudiante_consulta_su_acompanamiento(self):
        cuenta = self._usuario('Ana Pérez', 'ana@ufps.edu.co', 'ESTUDIANTE')
        self.estudiante.usuario = cuenta
        self.estudiante.save(update_fields=['usuario'])
        otro = Estudiante.objects.create(
            codigo='1152002', nombre='Luis Gómez', tipo_documento='CC', numero_documento='100200301',
            semestre=2, estado_matricula='ACTIVO', email_institucional='luis@ufps.edu.co',
        )
        for codigo in (self.estudiante.codigo, otro.codigo):
            resp = self.importar_historial(self.historial_en_riesgo(), codigo=codigo)
            self.assertEqual(resp.status_code, 200, resp.content)

        # 1. Inicia sesión: aún sin acompañamiento
        self.assertEqual(self.login(cuenta).status_code, 200)
        data = self.api('get', 'portal-intervenciones', cuenta).json()
        self.assertEqual(data['intervenciones'], [])

        # 2. El docente y Bienestar registran intervenciones sobre las alertas de ambos estudiantes
        promedio = Alerta.objects.get(estudiante=self.estudiante, regla=self.regla_promedio)
        c1 = Alerta.objects.get(estudiante=self.estudiante, regla__parametros__clave='C1')
        ajena_alerta = Alerta.objects.get(estudiante=otro, regla=self.regla_promedio)
        registros = [
            (self.usuario_docente, c1, {'tipo': 'TUTORIA', 'observaciones': 'Nota interna del docente',
                                        'resultado': 'Asistió a la tutoría'}),
            (self.bienestar, promedio, {'tipo': 'CITACION', 'observaciones': 'Situación familiar delicada',
                                        'evidencia': 'acta-reservada'}),
            (self.bienestar, ajena_alerta, {'tipo': 'REMISION', 'observaciones': 'Caso de Luis'}),
        ]
        for usuario, alerta, datos in registros:
            resp = self.api('post', 'registrar-intervencion', usuario, datos=datos, args=[alerta.id])
            self.assertEqual(resp.status_code, 201, resp.content)

        # 3. Lista su acompañamiento: solo lo de sus alertas, sin observaciones ni evidencias
        resp = self.api('get', 'portal-intervenciones', cuenta)
        self.assertEqual(resp.status_code, 200)
        contenido = resp.content.decode()
        for privado in ('Nota interna', 'Situación familiar', 'acta-reservada', 'Caso de Luis',
                        'bienestar@ufps.edu.co', 'docente@ufps.edu.co'):
            self.assertNotIn(privado, contenido)
        data = resp.json()
        self.assertEqual([i['tipo'] for i in data['intervenciones']], ['CITACION', 'TUTORIA'])
        self.assertEqual({i['responsable'] for i in data['intervenciones']}, {'Docente Curso', 'Bienestar'})
        self.assertEqual(data['conteos'], {'en_curso': 2, 'concluida': 0, 'total': 2})

        # 4. Filtra por periodo (solo la alerta de corte tiene periodo) y abre el detalle
        [tutoria] = self.api('get', 'portal-intervenciones', cuenta, query={'periodo': '2026-1'}).json()['intervenciones']
        resp = self.api('get', 'portal-intervencion-detalle', cuenta, args=[tutoria['id']])
        self.assertEqual(resp.status_code, 200)
        detalle = resp.json()
        self.assertEqual((detalle['resultado'], detalle['responsable']), ('Asistió a la tutoría', 'Docente Curso'))
        self.assertEqual((detalle['alerta']['id'], detalle['alerta']['materia']), (c1.id, 'Cálculo I'))

        # 5. Intenta abrir la intervención de Luis: 404 y queda en la auditoría
        ajena = Intervencion.objects.get(alerta=ajena_alerta)
        resp = self.api('get', 'portal-intervencion-detalle', cuenta, args=[ajena.id])
        self.assertEqual(resp.status_code, 404)
        self.assertNotIn('Luis', resp.content.decode())
        registro = Auditoria.objects.get(usuario=cuenta, tipo_accion='ACCESO_DENEGADO')
        self.assertIn(f'intervención ID {ajena.id}', registro.detalle)


class FlujoAsistenciaPortalTests(IntegracionTestCase):
    """HU-42: el docente registra la asistencia y el estudiante consulta la suya en el portal."""

    def test_estudiante_consulta_su_asistencia(self):
        cuenta = self._usuario('Ana Pérez', 'ana@ufps.edu.co', 'ESTUDIANTE')
        self.estudiante.usuario = cuenta
        self.estudiante.save(update_fields=['usuario'])
        otro = Estudiante.objects.create(
            codigo='1152002', nombre='Luis Gómez', tipo_documento='CC', numero_documento='100200301',
            semestre=2, estado_matricula='ACTIVO', email_institucional='luis@ufps.edu.co',
        )
        # Ambos matriculados en 2026-1 en Cálculo I y Física I (fila sin notas = matrícula)
        filas = self.historial_en_riesgo() + [self.fila('2026-1', '1150102', nombre='Física I')]
        for codigo in (self.estudiante.codigo, otro.codigo):
            resp = self.importar_historial(filas, codigo=codigo)
            self.assertEqual(resp.status_code, 200, resp.content)

        # 1. Inicia sesión: matriculado pero sin registros de asistencia
        self.assertEqual(self.login(cuenta).status_code, 200)
        data = self.api('get', 'portal-asistencia', cuenta).json()
        self.assertEqual(data['periodo'], '2026-1')
        self.assertFalse(data['hay_registros'])
        self.assertEqual({c['materia'] for c in data['cursos']}, {'Cálculo I', 'Física I'})

        # 2. El docente registra 6 clases de Física I: Ana falta a 2, Luis asiste a todas
        for dia in range(6):
            estado_ana = 'FALTA' if dia in (1, 3) else 'ASISTIO'
            resp = self.api('post', 'course-attendance', self.usuario_docente, args=[self.curso_fisica.id], datos={
                'fecha': f'2026-02-{dia + 2:02d}',
                'registros': [
                    {'codigo_estudiante': self.estudiante.codigo, 'estado': estado_ana,
                     'observacion': 'Llegó tarde y sin justificación'},
                    {'codigo_estudiante': otro.codigo, 'estado': 'ASISTIO'},
                ],
            })
            self.assertEqual(resp.status_code, 200, resp.content)

        # 3. Ana consulta su asistencia: 33,33 % supera el umbral del 20 %
        resp = self.api('get', 'portal-asistencia', cuenta, query={'codigo': otro.codigo})
        self.assertEqual(resp.status_code, 200)
        self.assertNotIn('Llegó tarde', resp.content.decode())
        data = resp.json()
        self.assertTrue(data['hay_registros'])
        fisica = next(c for c in data['cursos'] if c['materia'] == 'Física I')
        self.assertEqual((fisica['total_clases'], fisica['faltas'], fisica['porcentaje'], fisica['umbral']),
                         (6, 2, 33.33, 20.0))
        self.assertTrue(fisica['supera_umbral'])
        self.assertEqual(len(fisica['detalle']), 6)
        calculo = next(c for c in data['cursos'] if c['materia'] == 'Cálculo I')
        self.assertIsNone(calculo['porcentaje'])

        # Coincide con lo que ve el docente y con la alerta de inasistencia que se generó
        personal = self.api('get', 'student-attendance', self.usuario_docente, args=[self.estudiante.codigo]).json()
        del_personal = next(c for c in personal['cursos'] if c['curso_id'] == fisica['curso_id'])
        self.assertEqual(del_personal['porcentaje'], fisica['porcentaje'])
        self.assertEqual(del_personal['supera_umbral'], fisica['supera_umbral'])
        self.assertTrue(Alerta.objects.filter(estudiante=self.estudiante, regla__tipo='INASISTENCIA').exists())

        # 4. Luis solo ve la suya
        cuenta_luis = self._usuario('Luis Gómez', 'luis@ufps.edu.co', 'ESTUDIANTE')
        otro.usuario = cuenta_luis
        otro.save(update_fields=['usuario'])
        data = self.api('get', 'portal-asistencia', cuenta_luis).json()
        fisica_luis = next(c for c in data['cursos'] if c['materia'] == 'Física I')
        self.assertEqual((fisica_luis['faltas'], fisica_luis['porcentaje'], fisica_luis['supera_umbral']), (0, 0.0, False))
