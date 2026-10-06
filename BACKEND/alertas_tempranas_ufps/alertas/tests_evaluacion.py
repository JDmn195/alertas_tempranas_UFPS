from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal

import jwt
from django.conf import settings
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from academico.models import Curso, Docente, EquivalenciaMateria, Estudiante, Materia, Nota, Periodo
from academico.views.student_views import calcular_nivel_riesgo
from alertas.evaluacion import actualizar_promedio, calcular_indicadores
from alertas.models import Alerta, NotificacionHistorial, Regla
from alertas.views.alert_generation_views import evaluar_reglas_estudiante
from usuarios.models import Usuario


class EvaluacionBaseTestCase(TestCase):

    def setUp(self):
        usuario = Usuario.objects.create(nombre='Doc', correo='doc@ufps.edu.co', rol='DOCENTE', contrasena='x')
        self.docente = Docente.objects.create(codigo='D1', nombre='Doc', tipo_vinculacion='Planta', usuario=usuario)
        self.p1 = Periodo.objects.create(anio=2025, semestre=1)
        self.p2 = Periodo.objects.create(anio=2025, semestre=2)
        self.est = Estudiante.objects.create(
            codigo='E1', nombre='Estudiante', tipo_documento='CC', numero_documento='1', semestre=3,
        )

    def _curso(self, codigo, creditos=3, semestre=1, tipo='linea'):
        materia = Materia.objects.create(codigo=codigo, nombre=f'Materia {codigo}', creditos=creditos,
                                         semestre=semestre, tipo=tipo)
        return Curso.objects.create(materia=materia, grupo='A', docente=self.docente)

    def _nota(self, curso, definitiva, periodo=None):
        return Nota.objects.create(estudiante=self.est, curso=curso, periodo=periodo or self.p1,
                                   definitiva=Decimal(str(definitiva)) if definitiva is not None else None)


class PromedioTests(EvaluacionBaseTestCase):

    def test_ppa_ponderado_por_creditos(self):
        self._nota(self._curso('M1', creditos=4), 4.0)
        self._nota(self._curso('M2', creditos=1), 2.0)
        self._nota(self._curso('M3', creditos=2), None)  # sin definitiva: no cuenta
        self.assertEqual(actualizar_promedio(self.est), Decimal('3.60'))  # (16 + 2) / 5, no 3.0 simple

    def test_sin_creditos_usa_promedio_simple(self):
        self._nota(self._curso('M1', creditos=None), 4.0)
        self._nota(self._curso('M2', creditos=None), 2.0)
        self.assertEqual(actualizar_promedio(self.est), Decimal('3.00'))

    def test_sin_notas_conserva_el_promedio_importado(self):
        Estudiante.objects.filter(pk=self.est.pk).update(promedio=Decimal('3.3'))
        self.est.refresh_from_db()
        self.assertEqual(actualizar_promedio(self.est), Decimal('3.3'))


class ReglaPromedioSinDatosTests(EvaluacionBaseTestCase):

    def test_promedio_nulo_no_dispara_alerta_ni_riesgo(self):
        regla = Regla.objects.create(nombre='Bajo', tipo='PROMEDIO', operador='<', valor_umbral=Decimal('3.0'),
                                     nivel='medium', prioridad=10)
        aplica, valor, _ = evaluar_reglas_estudiante(self.est, [regla])[regla.id]
        self.assertFalse(aplica)
        self.assertIsNone(valor)
        self.assertEqual(calcular_nivel_riesgo(self.est), 'unknown')


class ReprobacionTests(EvaluacionBaseTestCase):

    def test_cuenta_materias_pendientes_una_sola_vez(self):
        recuperada = self._curso('M1')
        self._nota(recuperada, 2.0, self.p1)
        self._nota(recuperada, 3.5, self.p2)  # la perdió y luego la ganó

        repetida = self._curso('M2')
        self._nota(repetida, 2.0, self.p1)
        self._nota(repetida, 1.5, self.p2)  # perdida dos veces: cuenta como una

        ind = calcular_indicadores(self.est)
        self.assertEqual(ind['reprobadas'], 1)
        self.assertEqual(ind['materias_reprobadas'], ['Materia M2'])

    def test_la_equivalencia_aprobada_cubre_la_perdida(self):
        original = self._curso('M1')
        equivalente = self._curso('M9')
        EquivalenciaMateria.objects.create(materia_pensum=original.materia, materia_equivalente=equivalente.materia)
        self._nota(original, 2.0, self.p1)
        self._nota(equivalente, 4.0, self.p2)
        self.assertEqual(calcular_indicadores(self.est)['reprobadas'], 0)

    def test_por_periodo_solo_usa_notas_hasta_ese_periodo(self):
        curso = self._curso('M1')
        self._nota(curso, 2.0, self.p1)
        self._nota(curso, 3.5, self.p2)
        self.assertEqual(calcular_indicadores(self.est, periodo=self.p1)['reprobadas'], 1)
        self.assertEqual(calcular_indicadores(self.est, periodo=self.p2)['reprobadas'], 0)


class NivelYAlertasCoincidenTests(EvaluacionBaseTestCase):

    def test_atraso_ignora_electivas_en_nivel_y_alertas(self):
        self._nota(self._curso('M1', semestre=1), 4.0)
        self._curso('E1', semestre=1, tipo='profesional')  # electiva sin cursar
        regla = Regla.objects.create(nombre='Atraso', tipo='ATRASO', operador='>', valor_umbral=Decimal('0'),
                                     nivel='high', prioridad=10)
        aplica, valor, _ = evaluar_reglas_estudiante(self.est, [regla])[regla.id]
        self.assertEqual((aplica, valor), (False, 0))
        self.assertEqual(calcular_nivel_riesgo(self.est), 'low')


class FiltroFechasHistorialTests(TestCase):

    def setUp(self):
        self.admin = Usuario.objects.create(nombre='Admin', correo='admin@ufps.edu.co', rol='ADMINISTRADOR',
                                            contrasena='x')
        token = jwt.encode({'user_id': self.admin.id, 'exp': datetime.now(dt_timezone.utc) + timedelta(days=1)},
                           settings.SECRET_KEY, algorithm='HS256')
        self.auth = {'HTTP_AUTHORIZATION': f'Bearer {token}'}

        est = Estudiante.objects.create(codigo='E1', nombre='Est', tipo_documento='CC', numero_documento='1', semestre=1)
        regla = Regla.objects.create(nombre='R', tipo='PROMEDIO', operador='<', valor_umbral=Decimal('3'),
                                     nivel='low', prioridad=1)
        alerta = Alerta.objects.create(estudiante=est, regla=regla, estado='activa')
        for dia in (1, 15, 30):
            n = NotificacionHistorial.objects.create(alerta=alerta, destinatario='a@b.co', rol_destinatario='ESTUDIANTE',
                                                     canal='EMAIL', resultado='exitoso')
            fecha = timezone.make_aware(datetime(2026, 6, dia, 12))
            NotificacionHistorial.objects.filter(pk=n.pk).update(fecha_envio=fecha)

    def _historial(self, query):
        return self.client.get(reverse('historial-notificaciones') + query, **self.auth)

    def test_filtra_por_rango_de_fechas_inclusivo(self):
        data = self._historial('?fecha_inicio=2026-06-15&fecha_fin=2026-06-30').json()
        self.assertEqual(len(data['historial']), 2)

    def test_fecha_invalida_responde_400(self):
        self.assertEqual(self._historial('?fecha_inicio=2026-02-30').status_code, 400)
        self.assertEqual(self._historial('?fecha_fin=ayer').status_code, 400)
