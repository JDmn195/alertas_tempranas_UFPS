"""SDAT-333: una sola definición de «alerta activa» (no cerrada) y barras por semestre completas."""
from django.test import TestCase
from django.urls import reverse

from academico.models import Curso, Docente, Estudiante, Materia, Nota, Periodo
from alertas.models import Alerta, Regla, RiesgoEstudiante
from usuarios.models import Usuario
from usuarios.tests_cuentas_estudiante import _auth


def _estudiante(codigo, semestre, nivel=None):
    e = Estudiante.objects.create(codigo=codigo, nombre=f'Est {codigo}', tipo_documento='CC',
                                  numero_documento=codigo, semestre=semestre, estado_matricula='ACTIVO')
    if nivel:
        RiesgoEstudiante.objects.create(estudiante=e, nivel_riesgo=nivel)
    return e


class AlertaActivaUnificadaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.director = Usuario.objects.create(nombre='Dir', correo='d333b@ufps.edu.co', rol='DIRECTOR', contrasena='!')
        cls.usuario_doc = Usuario.objects.create(nombre='Doc', correo='doc333b@ufps.edu.co', rol='DOCENTE',
                                                 contrasena='!')
        docente = Docente.objects.create(codigo='D333', nombre='Doc', tipo_vinculacion='Planta',
                                         usuario=cls.usuario_doc)
        curso = Curso.objects.create(materia=Materia.objects.create(codigo='333001', nombre='M', creditos=3,
                                                                    semestre=1), grupo='A', docente=docente)
        periodo = Periodo.objects.create(anio=2026, semestre=2)
        regla = Regla.objects.create(nombre='R', tipo='PROMEDIO', operador='<', valor_umbral=3, nivel='medium')
        cls.e1 = _estudiante('B3331', 1, 'high')
        cls.e2 = _estudiante('B3332', 4, 'low')
        cls.e3 = _estudiante('B3333', 4)  # sin dato de riesgo
        for e in (cls.e1, cls.e2, cls.e3):
            Nota.objects.create(estudiante=e, curso=curso, periodo=periodo)
        for estado in ('activa', 'en_seguimiento', 'atendida', 'cerrada'):
            Alerta.objects.create(estudiante=cls.e1, regla=regla, estado=estado)

    def test_panel_cuenta_alertas_no_cerradas(self):
        datos = self.client.get(reverse('director-indicadores'), **_auth(self.director)).json()
        self.assertEqual(datos['alertas_activas'], 3)

    def test_gestion_de_alertas_informa_el_total_de_abiertas(self):
        datos = self.client.get(reverse('listar-alertas'), **_auth(self.director)).json()
        self.assertEqual(datos['conteos']['abiertas'], 3)

    def test_panel_del_docente_cuenta_alertas_no_cerradas(self):
        datos = self.client.get(reverse('teacher-dashboard'), **_auth(self.usuario_doc)).json()
        self.assertEqual(datos['total_alertas_activas'], 3)

    def test_barras_por_semestre_incluyen_sin_dato_y_eje_completo(self):
        datos = self.client.get(reverse('director-indicadores'), **_auth(self.director)).json()
        dist = datos['distribucion_riesgo']
        self.assertEqual([d['semester'] for d in dist], [f'Sem {n}' for n in range(1, 11)])
        sem4 = next(d for d in dist if d['semester'] == 'Sem 4')
        self.assertEqual((sem4['low'], sem4['sin_dato']), (1, 1))
        total = sum(d['low'] + d['medium'] + d['high'] + d['sin_dato'] for d in dist)
        self.assertEqual(total, datos['total_estudiantes_activos'])
