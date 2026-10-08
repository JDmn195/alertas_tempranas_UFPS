"""
HU-35: regla INASISTENCIA (umbral general de inasistencia).

Validaciones del CRUD de reglas, exclusión del motor general y migración de datos.
"""
import importlib
import json
from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from unittest import mock

import jwt
from django.apps import apps as django_apps
from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from academico.models import Curso, Docente, Estudiante, Materia, Nota, Periodo
from academico.views.student_views import calcular_nivel_riesgo
from alertas import evaluacion
from alertas.models import Alerta, Regla
from alertas.reevaluacion import ejecutar_reevaluacion
from alertas.views.alert_generation_views import (
    calcular_y_guardar_riesgo_por_periodos, reevaluar_alertas_activas, reprocesar_alertas_completas,
)
from usuarios.models import Auditoria, Usuario

migracion_regla = importlib.import_module('alertas.migrations.0018_crear_regla_inasistencia')


def _auth(usuario):
    payload = {
        'user_id': usuario.id,
        'exp': datetime.now(dt_timezone.utc) + timedelta(days=1),
        'iat': datetime.now(dt_timezone.utc),
    }
    return f"Bearer {jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')}"


class ReglaInasistenciaBaseTestCase(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create(nombre='Admin', correo='admin@ufps.edu.co', rol='ADMINISTRADOR',
                                            contrasena='x', activo=True)
        # La migración 0018 deja creada la regla general (20 %, min_clases 4, activa)
        self.regla = Regla.objects.get(tipo='INASISTENCIA')

    def post(self, body):
        return self.client.post(reverse('listar_crear_reglas'), json.dumps(body),
                                content_type='application/json', HTTP_AUTHORIZATION=_auth(self.admin))

    def put(self, regla, body):
        return self.client.put(reverse('detalle_regla', args=[regla.id]), json.dumps(body),
                               content_type='application/json', HTTP_AUTHORIZATION=_auth(self.admin))

    def nueva(self, **cambios):
        body = {'nombre': 'Otra', 'tipo': 'INASISTENCIA', 'operador': '>', 'valor_umbral': 25,
                'nivel': 'high', 'activo': False, 'parametros': {'min_clases': 4}}
        body.update(cambios)
        return body


class ValidacionReglaInasistenciaTests(ReglaInasistenciaBaseTestCase):

    def test_umbral_fuera_de_rango(self):
        for valor in (-1, 100.01, 150, 'abc'):
            res = self.post(self.nueva(valor_umbral=valor))
            self.assertEqual(res.status_code, 400, valor)
            self.assertIn('umbral', res.json()['error'])
        res = self.put(self.regla, {'valor_umbral': 101})
        self.assertEqual(res.status_code, 400)
        self.regla.refresh_from_db()
        self.assertEqual(self.regla.valor_umbral, Decimal('20'))

    def test_limites_del_umbral_son_validos(self):
        for valor in (0, 100):
            self.assertEqual(self.put(self.regla, {'valor_umbral': valor}).status_code, 200, valor)

    def test_min_clases_invalido(self):
        for min_clases in (0, 51, -3, '4', 4.5, True, None):
            res = self.post(self.nueva(parametros={'min_clases': min_clases}))
            self.assertEqual(res.status_code, 400, min_clases)
            self.assertIn('min_clases', res.json()['error'])
        res = self.post(self.nueva(parametros={}))
        self.assertEqual(res.status_code, 400)
        res = self.put(self.regla, {'parametros': {'min_clases': 0}})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(Regla.objects.filter(tipo='INASISTENCIA').count(), 1)

    def test_segunda_regla_activa(self):
        res = self.post(self.nueva(activo=True))
        self.assertEqual(res.status_code, 400)
        self.assertIn('Ya existe una regla de inasistencia activa', res.json()['error'])

        # Inactiva se puede crear, pero no activar mientras la otra siga activa
        res = self.post(self.nueva(activo=False))
        self.assertEqual(res.status_code, 201)
        segunda = Regla.objects.get(pk=res.json()['id'])
        res = self.put(segunda, {'activo': True})
        self.assertEqual(res.status_code, 400)
        self.assertIn('Ya existe una regla de inasistencia activa', res.json()['error'])

        # Al desactivar la primera, la segunda sí se puede activar
        self.assertEqual(self.put(self.regla, {'activo': False}).status_code, 200)
        self.assertEqual(self.put(segunda, {'activo': True}).status_code, 200)

    def test_editar_la_regla_activa_no_choca_consigo_misma(self):
        res = self.put(self.regla, {'valor_umbral': 30, 'parametros': {'min_clases': 6}})
        self.assertEqual(res.status_code, 200, res.content)
        self.regla.refresh_from_db()
        self.assertEqual(self.regla.valor_umbral, Decimal('30'))
        self.assertEqual(self.regla.parametros, {'min_clases': 6})

    def test_listado_y_detalle_devuelven_parametros(self):
        res = self.client.get(reverse('listar_crear_reglas'), HTTP_AUTHORIZATION=_auth(self.admin))
        regla = next(r for r in res.json() if r['tipo'] == 'INASISTENCIA')
        self.assertEqual(regla['parametros'], {'min_clases': 4})
        self.assertEqual(regla['valor_umbral'], 20.0)
        res = self.client.get(reverse('detalle_regla', args=[self.regla.id]), HTTP_AUTHORIZATION=_auth(self.admin))
        self.assertEqual(res.json()['parametros'], {'min_clases': 4})

    def test_cambios_quedan_en_auditoria(self):
        self.put(self.regla, {'valor_umbral': 25, 'parametros': {'min_clases': 5}})
        registro = Auditoria.objects.filter(tipo_accion='MODIFICAR_REGLA').latest('fecha_hora')
        self.assertIn('25', registro.detalle)
        self.assertIn('mínimo de clases: 5', registro.detalle)

        self.put(self.regla, {'activo': False})
        self.assertTrue(Auditoria.objects.filter(tipo_accion='DESACTIVAR_REGLA').exists())

        self.post(self.nueva(nombre='Nueva'))
        registro = Auditoria.objects.filter(tipo_accion='CREAR_REGLA').latest('fecha_hora')
        self.assertIn("'Nueva'", registro.detalle)

    def test_guardar_la_regla_no_dispara_el_motor_general(self):
        with mock.patch('alertas.views.alert_generation_views.reprocesar_alertas_completas') as reprocesar:
            self.put(self.regla, {'valor_umbral': 30})
        reprocesar.assert_not_called()


class MotorGeneralExcluyeInasistenciaTests(TestCase):
    """El motor general (riesgo y alertas PROMEDIO/REPROBACION/ATRASO) no evalúa reglas INASISTENCIA."""

    def setUp(self):
        usuario = Usuario.objects.create(nombre='Doc', correo='doc@ufps.edu.co', rol='DOCENTE', contrasena='x')
        docente = Docente.objects.create(codigo='D1', nombre='Doc', tipo_vinculacion='Planta', usuario=usuario)
        periodo = Periodo.objects.create(anio=2026, semestre=2)
        materia = Materia.objects.create(codigo='M1', nombre='Materia', creditos=3, semestre=1, tipo='linea')
        curso = Curso.objects.create(materia=materia, grupo='A', docente=docente)
        self.est = Estudiante.objects.create(codigo='E1', nombre='Estudiante', tipo_documento='CC',
                                             numero_documento='1', semestre=3)
        Nota.objects.create(estudiante=self.est, curso=curso, periodo=periodo, definitiva=Decimal('2.0'))

        self.inasistencia = Regla.objects.get(tipo='INASISTENCIA')
        # Umbral 0: si el motor general la evaluara, cualquier valor la haría "aplicar"
        Regla.objects.filter(pk=self.inasistencia.pk).update(valor_umbral=0, operador='>=')
        self.promedio = Regla.objects.create(nombre='Bajo', tipo='PROMEDIO', operador='<', valor_umbral=3,
                                             nivel='medium', prioridad=10)

    def _tipos_evaluados(self, funcion, *args, **kwargs):
        tipos = set()
        original = evaluacion.evaluar_regla

        def espia(regla, indicadores):
            tipos.add(regla.tipo)
            return original(regla, indicadores)

        with mock.patch('alertas.evaluacion.evaluar_regla', side_effect=espia), \
                mock.patch('alertas.views.alert_generation_views.evaluar_regla', side_effect=espia):
            funcion(*args, **kwargs)
        return tipos

    def test_no_evalua_ni_genera_alertas_inasistencia(self):
        procesos = [
            (reprocesar_alertas_completas, (), {}),
            (reevaluar_alertas_activas, (), {}),  # evalúa las alertas abiertas que dejó el paso anterior
            (calcular_y_guardar_riesgo_por_periodos, (self.est,), {}),
            (calcular_nivel_riesgo, (self.est,), {}),
            (ejecutar_reevaluacion, (), {'origen': 'MANUAL'}),
        ]
        for funcion, args, kwargs in procesos:
            tipos = self._tipos_evaluados(funcion, *args, **kwargs)
            self.assertIn('PROMEDIO', tipos, funcion.__name__)
            self.assertNotIn('INASISTENCIA', tipos, funcion.__name__)

        self.assertTrue(Alerta.objects.filter(regla=self.promedio).exists())
        self.assertFalse(Alerta.objects.filter(regla__tipo='INASISTENCIA').exists())

    def test_no_cierra_alertas_inasistencia_abiertas(self):
        # Alerta creada por la HU-36: el motor general no debe tocarla
        alerta = Alerta.objects.create(estudiante=self.est, regla=self.inasistencia, estado='activa',
                                       valor_causa=Decimal('50'))
        reprocesar_alertas_completas()
        reevaluar_alertas_activas()
        ejecutar_reevaluacion(origen='MANUAL')
        alerta.refresh_from_db()
        self.assertEqual(alerta.estado, 'activa')
        self.assertEqual(alerta.valor_causa, Decimal('50'))


class MigracionReglaInasistenciaTests(TestCase):

    def test_crea_la_regla_una_sola_vez(self):
        regla = Regla.objects.get(tipo='INASISTENCIA')
        self.assertEqual(regla.nombre, 'Inasistencia superior al umbral')
        self.assertEqual(regla.operador, '>')
        self.assertEqual(regla.valor_umbral, Decimal('20'))
        self.assertEqual(regla.nivel, 'high')
        self.assertTrue(regla.activo)
        self.assertEqual(regla.parametros, {'min_clases': 4})
        self.assertTrue(regla.descripcion)

        migracion_regla.crear_regla_inasistencia(django_apps, None)
        migracion_regla.crear_regla_inasistencia(django_apps, None)
        self.assertEqual(Regla.objects.filter(tipo='INASISTENCIA').count(), 1)

    def test_no_crea_si_ya_existe_otra_regla_inasistencia(self):
        Regla.objects.filter(tipo='INASISTENCIA').update(nombre='Personalizada', activo=False)
        migracion_regla.crear_regla_inasistencia(django_apps, None)
        self.assertEqual(list(Regla.objects.filter(tipo='INASISTENCIA').values_list('nombre', flat=True)),
                         ['Personalizada'])

    def test_reversa(self):
        migracion_regla.eliminar_regla_inasistencia(django_apps, None)
        self.assertFalse(Regla.objects.filter(tipo='INASISTENCIA').exists())
        migracion_regla.crear_regla_inasistencia(django_apps, None)
        self.assertEqual(Regla.objects.filter(tipo='INASISTENCIA').count(), 1)
