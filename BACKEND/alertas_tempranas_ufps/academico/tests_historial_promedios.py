"""
Serie histórica de promedios por periodo (academico/services/historial_promedios.py),
compartida por la ficha académica y el portal del estudiante (HU-38).
"""
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import jwt
from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from academico.models import Curso, Docente, Estudiante, Materia, Nota, Periodo
from academico.services.historial_promedios import serie_promedios_por_periodo, tendencia_promedio
from usuarios.models import Usuario


def _auth(usuario):
    ahora = datetime.now(timezone.utc)
    token = jwt.encode({'user_id': usuario.id, 'exp': ahora + timedelta(days=1), 'iat': ahora},
                       settings.SECRET_KEY, algorithm='HS256')
    return {'HTTP_AUTHORIZATION': f'Bearer {token}'}


class EscenarioHistorial:
    """
    Tres periodos cerrados y uno opcional en curso:

      2024-2: A (3 cr) 4.0, B (4 cr) 2.0            → PPS 2.86, PPA 2.86, cursados 7, aprobados 3
      2025-1: C (3 cr) 3.5, D (2 cr) 4.5            → PPS 3.90, PPA 3.29, cursados 5, aprobados 5
      2025-2: E (3 cr) 2.5, F (2 cr) en curso       → PPS 2.50, PPA 3.13, cursados 3, aprobados 0
      2026-1 (opcional): G (3 cr) en curso, solo cortes
    """

    def crear_escenario(self, codigo='1151001', usuario=None, en_curso=False):
        usuario_docente, _ = Usuario.objects.get_or_create(
            correo='doc.historial@ufps.edu.co', defaults={'nombre': 'Doc', 'rol': 'DOCENTE'})
        docente, _ = Docente.objects.get_or_create(
            codigo='DH1', defaults={'nombre': 'Doc', 'tipo_vinculacion': 'Planta', 'usuario': usuario_docente})
        estudiante = Estudiante.objects.create(
            codigo=codigo, nombre='Ana Pérez', tipo_documento='CC', numero_documento=f'9{codigo}',
            semestre=4, estado_matricula='ACTIVO', usuario=usuario,
        )

        def nota(periodo, codigo_materia, creditos, definitiva, **cortes):
            anio, semestre = periodo.split('-')
            p, _ = Periodo.objects.get_or_create(anio=int(anio), semestre=int(semestre))
            materia, _ = Materia.objects.get_or_create(
                codigo=codigo_materia, defaults={'nombre': f'Materia {codigo_materia}', 'creditos': creditos, 'semestre': 1})
            curso, _ = Curso.objects.get_or_create(materia=materia, grupo='A', defaults={'docente': docente})
            Nota.objects.create(estudiante=estudiante, curso=curso, periodo=p,
                                definitiva=Decimal(definitiva) if definitiva is not None else None, **cortes)

        nota('2024-2', 'MA', 3, '4.0')
        nota('2024-2', 'MB', 4, '2.0')
        nota('2025-1', 'MC', 3, '3.5')
        nota('2025-1', 'MD', 2, '4.5')
        nota('2025-2', 'ME', 3, '2.5')
        nota('2025-2', 'MF', 2, None, corte1=Decimal('1.0'))
        if en_curso:
            nota('2026-1', 'MG', 3, None, corte1=Decimal('4.0'), corte2=Decimal('4.5'))
        return estudiante


class SeriePromediosTests(EscenarioHistorial, TestCase):

    def test_serie_ordenada_con_pps_ppa_y_creditos(self):
        serie = serie_promedios_por_periodo(self.crear_escenario())

        self.assertEqual([p['periodo'] for p in serie], ['2024-2', '2025-1', '2025-2'])
        self.assertEqual([p['pps'] for p in serie], [2.86, 3.9, 2.5])
        self.assertEqual([p['ppa'] for p in serie], [2.86, 3.29, 3.13])
        self.assertEqual([p['creditos_cursados'] for p in serie], [7, 5, 3])
        self.assertEqual([p['creditos_aprobados'] for p in serie], [3, 5, 0])
        self.assertEqual([p['materias_en_curso'] for p in serie], [0, 0, 1])

    def test_materias_en_curso_no_afectan_el_promedio(self):
        estudiante = self.crear_escenario(en_curso=True)
        serie = serie_promedios_por_periodo(estudiante)

        # La nota en curso de 2025-2 (MF) no cambia el PPS de 2.5
        self.assertEqual(serie[2]['pps'], 2.5)
        # Un periodo solo con materias en curso no tiene PPS y conserva el PPA anterior
        self.assertEqual(serie[3], {
            'periodo': '2026-1', 'pps': None, 'ppa': 3.13,
            'creditos_cursados': 0, 'creditos_aprobados': 0, 'materias_en_curso': 1,
        })

    def test_sin_notas_serie_vacia(self):
        estudiante = Estudiante.objects.create(
            codigo='1159999', nombre='Sin notas', tipo_documento='CC', numero_documento='1',
            semestre=1, estado_matricula='ACTIVO',
        )
        self.assertEqual(serie_promedios_por_periodo(estudiante), [])

    def test_tendencia(self):
        self.assertEqual(tendencia_promedio(3.13, 3.29), {'valor': -0.16, 'porcentaje': 4.9, 'direccion': 'down'})
        self.assertEqual(tendencia_promedio(3.5, 3.0)['direccion'], 'up')
        self.assertEqual(tendencia_promedio(3.0, 3.0)['direccion'], 'stable')
        self.assertEqual(tendencia_promedio(3.0, None), {'valor': 0, 'porcentaje': 0, 'direccion': 'stable'})


class FichaAcademicaSinCambiosTests(EscenarioHistorial, TestCase):
    """La ficha del personal devuelve lo mismo que antes de extraer la serie compartida."""

    def setUp(self):
        self.admin = Usuario.objects.create(nombre='Admin', correo='admin@ufps.edu.co', rol='ADMINISTRADOR')

    def _indicadores(self, estudiante):
        resp = self.client.get(reverse('student-indicators', args=[estudiante.codigo]), **_auth(self.admin))
        self.assertEqual(resp.status_code, 200)
        return resp.json()['indicadores']

    def test_evolucion_y_tendencia_de_la_ficha(self):
        indicadores = self._indicadores(self.crear_escenario())

        self.assertEqual(indicadores['evolucion'], [
            {'periodo': '2024-2', 'pps': 2.86, 'ppa': 2.86},
            {'periodo': '2025-1', 'pps': 3.9, 'ppa': 3.29},
            {'periodo': '2025-2', 'pps': 2.5, 'ppa': 3.13},
        ])
        self.assertEqual(indicadores['promedio_acumulado'], 3.13)
        self.assertEqual(indicadores['tendencia'], {'valor': -0.16, 'porcentaje': 4.9, 'direccion': 'down'})

    def test_periodo_en_curso_en_la_ficha_sigue_con_ceros(self):
        indicadores = self._indicadores(self.crear_escenario(en_curso=True))

        self.assertEqual(indicadores['evolucion'][-1], {'periodo': '2026-1', 'pps': 0, 'ppa': 3.13})
        self.assertEqual(indicadores['promedio_acumulado'], 3.13)
        self.assertEqual(indicadores['tendencia'], {'valor': 0.0, 'porcentaje': 0.0, 'direccion': 'stable'})

    def test_sin_notas_la_ficha_devuelve_ceros(self):
        estudiante = Estudiante.objects.create(
            codigo='1159999', nombre='Sin notas', tipo_documento='CC', numero_documento='1',
            semestre=1, estado_matricula='ACTIVO',
        )
        indicadores = self._indicadores(estudiante)
        self.assertEqual(indicadores['evolucion'], [])
        self.assertEqual(indicadores['promedio_acumulado'], 0)
        self.assertEqual(indicadores['tendencia'], {'valor': 0, 'porcentaje': 0, 'direccion': 'stable'})
