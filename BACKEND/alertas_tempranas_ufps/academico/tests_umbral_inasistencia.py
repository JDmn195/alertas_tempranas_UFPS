"""
HU-35: umbral de inasistencia por curso y su integración con el cálculo de la HU-34.
"""
import json
from decimal import Decimal

from django.urls import reverse

from academico.asistencia import obtener_umbral_inasistencia
from academico.models import Estudiante, Nota
from academico.tests_inasistencia import InasistenciaBaseTestCase
from alertas.models import Regla
from usuarios.models import Auditoria, Usuario


class UmbralCursoBaseTestCase(InasistenciaBaseTestCase):
    def setUp(self):
        super().setUp()
        # La migración 0018 deja la regla general activa con 20 %
        self.regla = Regla.objects.get(tipo='INASISTENCIA')

    def patch_umbral(self, umbral, usuario=None, curso=None, cuerpo=None):
        return self.client.patch(
            reverse('course-absence-threshold', args=[(curso or self.curso).id]),
            json.dumps({'umbral': umbral} if cuerpo is None else cuerpo),
            content_type='application/json',
            HTTP_AUTHORIZATION=self.auth(usuario or self.admin),
        )

    def sin_regla_activa(self):
        Regla.objects.filter(pk=self.regla.pk).update(activo=False)


class ObtenerUmbralTests(UmbralCursoBaseTestCase):

    def test_sin_umbral_propio_usa_el_general(self):
        self.assertEqual(obtener_umbral_inasistencia(self.curso), (Decimal('20'), 'general'))

    def test_umbral_del_curso_reemplaza_al_general(self):
        self.curso.umbral_inasistencia = Decimal('40')
        self.assertEqual(obtener_umbral_inasistencia(self.curso), (Decimal('40'), 'curso'))
        # Un umbral propio de 0 también es propio (no se confunde con "sin umbral")
        self.curso.umbral_inasistencia = Decimal('0')
        self.assertEqual(obtener_umbral_inasistencia(self.curso), (Decimal('0'), 'curso'))

    def test_umbral_propio_aplica_aunque_no_haya_regla_activa(self):
        self.sin_regla_activa()
        self.curso.umbral_inasistencia = Decimal('35')
        self.assertEqual(obtener_umbral_inasistencia(self.curso), (Decimal('35'), 'curso'))

    def test_sin_regla_activa_ni_umbral_del_curso(self):
        self.sin_regla_activa()
        self.assertEqual(obtener_umbral_inasistencia(self.curso), (None, None))
        Regla.objects.filter(tipo='INASISTENCIA').delete()
        self.assertEqual(obtener_umbral_inasistencia(self.curso), (None, None))

    def test_cambio_del_umbral_general_se_refleja(self):
        Regla.objects.filter(pk=self.regla.pk).update(valor_umbral=Decimal('15'))
        self.assertEqual(obtener_umbral_inasistencia(self.curso), (Decimal('15'), 'general'))


class EndpointUmbralCursoTests(UmbralCursoBaseTestCase):

    def test_asignar_y_volver_al_general(self):
        res = self.patch_umbral(40)
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(res.json()['umbral_curso'], 40.0)
        self.assertEqual(res.json()['umbral_efectivo'], 40.0)
        self.assertEqual(res.json()['origen'], 'curso')
        self.curso.refresh_from_db()
        self.assertEqual(self.curso.umbral_inasistencia, Decimal('40'))

        res = self.patch_umbral(None)
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(res.json()['umbral_curso'])
        self.assertEqual(res.json()['umbral_efectivo'], 20.0)
        self.assertEqual(res.json()['origen'], 'general')
        self.curso.refresh_from_db()
        self.assertIsNone(self.curso.umbral_inasistencia)

    def test_acepta_decimales_y_limites(self):
        for valor, esperado in ((0, Decimal('0')), (100, Decimal('100')), ('33.5', Decimal('33.5')), (12.345, Decimal('12.35'))):
            self.assertEqual(self.patch_umbral(valor).status_code, 200, valor)
            self.curso.refresh_from_db()
            self.assertEqual(self.curso.umbral_inasistencia, esperado)

    def test_valores_invalidos(self):
        for valor in (-1, 100.5, 'abc', '', True, [20], {'v': 1}, 'NaN', 'Infinity'):
            res = self.patch_umbral(valor)
            self.assertEqual(res.status_code, 400, valor)
            self.assertIn('error', res.json())
        self.assertEqual(self.patch_umbral(None, cuerpo={}).status_code, 400)
        self.curso.refresh_from_db()
        self.assertIsNone(self.curso.umbral_inasistencia)

    def test_curso_inexistente(self):
        res = self.client.patch(
            reverse('course-absence-threshold', args=[99999]), json.dumps({'umbral': 30}),
            content_type='application/json', HTTP_AUTHORIZATION=self.auth(self.admin),
        )
        self.assertEqual(res.status_code, 404)

    def test_solo_administrador(self):
        for rol in ('DIRECTOR', 'BIENESTAR', 'DOCENTE'):
            usuario = Usuario.objects.create(nombre=rol, correo=f'{rol.lower()}@x.co', rol=rol, contrasena='x', activo=True)
            self.assertEqual(self.patch_umbral(30, usuario).status_code, 403, rol)
        # Ni siquiera el docente del curso puede cambiarlo
        self.assertEqual(self.patch_umbral(30, self.user_docente).status_code, 403)
        self.curso.refresh_from_db()
        self.assertIsNone(self.curso.umbral_inasistencia)

    def test_metodo_no_permitido(self):
        res = self.client.get(reverse('course-absence-threshold', args=[self.curso.id]),
                              HTTP_AUTHORIZATION=self.auth(self.admin))
        self.assertEqual(res.status_code, 405)

    def test_auditoria_con_valor_anterior_y_nuevo(self):
        self.patch_umbral(40)
        self.patch_umbral(35.5)
        self.patch_umbral(None)
        registros = list(
            Auditoria.objects.filter(tipo_accion='MODIFICAR_UMBRAL_INASISTENCIA').order_by('id')
            .values_list('detalle', flat=True)
        )
        self.assertEqual(len(registros), 3)
        for detalle in registros:
            self.assertIn('1155501-A', detalle)
            self.assertIn('Programacion Web', detalle)
        self.assertIn('anterior general, nuevo 40.00%', registros[0])
        self.assertIn('anterior 40.00%, nuevo 35.50%', registros[1])
        self.assertIn('anterior 35.50%, nuevo general', registros[2])
        self.assertTrue(
            Auditoria.objects.filter(tipo_accion='MODIFICAR_UMBRAL_INASISTENCIA', usuario=self.admin).exists()
        )


class RespuestasConUmbralTests(UmbralCursoBaseTestCase):
    def setUp(self):
        super().setUp()
        e1, e2, e3 = self.estudiantes
        self.registrar(e1, ['ASISTIO'] * 5)
        self.registrar(e2, ['FALTA', 'FALTA', 'ASISTIO', 'ASISTIO', 'ASISTIO'])       # 40 %
        self.registrar(e3, ['FALTA', 'FALTA', 'FALTA', 'ASISTIO', 'ASISTIO'])         # 60 %

    def curso_en_dashboard(self):
        res = self.get(reverse('teacher-dashboard'), self.user_docente)
        self.assertEqual(res.status_code, 200)
        return res.json(), next(c for c in res.json()['cursos'] if c['curso_id'] == self.curso.id)

    def test_panel_docente_con_umbral_general(self):
        data, curso = self.curso_en_dashboard()
        self.assertEqual(data['umbral_inasistencia'], 20.0)
        self.assertEqual(curso['umbral_inasistencia'], 20.0)
        self.assertEqual(curso['origen_umbral_inasistencia'], 'general')
        self.assertEqual(curso['inasistencia_sobre_umbral'], 2)

    def test_panel_docente_con_umbral_del_curso(self):
        self.patch_umbral(50)
        data, curso = self.curso_en_dashboard()
        self.assertEqual(data['umbral_inasistencia'], 20.0)  # el general no cambia
        self.assertEqual(curso['umbral_inasistencia'], 50.0)
        self.assertEqual(curso['origen_umbral_inasistencia'], 'curso')
        self.assertEqual(curso['inasistencia_sobre_umbral'], 1)

        url = reverse('teacher-course-students', args=[self.curso.id])
        data = self.get(url, self.user_docente, page_size=50).json()
        self.assertEqual(data['umbral_inasistencia'], 50.0)
        self.assertEqual(data['origen_umbral_inasistencia'], 'curso')
        supera = {e['codigo']: e['supera_umbral_inasistencia'] for e in data['estudiantes']}
        self.assertEqual(supera, {'1152001': False, '1152002': False, '1152003': True})

    def test_sin_umbral_el_panel_responde_con_null(self):
        self.sin_regla_activa()
        data, curso = self.curso_en_dashboard()
        self.assertIsNone(data['umbral_inasistencia'])
        self.assertIsNone(curso['umbral_inasistencia'])
        self.assertIsNone(curso['origen_umbral_inasistencia'])
        self.assertIsNone(curso['inasistencia_sobre_umbral'])

        url = reverse('teacher-course-students', args=[self.curso.id])
        res = self.get(url, self.user_docente, page_size=50)
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(res.json()['umbral_inasistencia'])
        for est in res.json()['estudiantes']:
            self.assertIsNone(est['supera_umbral_inasistencia'])
        # El porcentaje se sigue calculando aunque no haya umbral
        self.assertEqual({e['codigo']: e['porcentaje_inasistencia'] for e in res.json()['estudiantes']},
                         {'1152001': 0.0, '1152002': 40.0, '1152003': 60.0})

    def test_endpoint_del_curso_incluye_umbral_y_origen(self):
        url = reverse('course-absence', args=[self.curso.id])
        data = self.get(url).json()
        self.assertEqual((data['umbral'], data['origen_umbral'], data['total_sobre_umbral']), (20.0, 'general', 2))

        self.patch_umbral(50)
        data = self.get(url).json()
        self.assertEqual((data['umbral'], data['origen_umbral'], data['total_sobre_umbral']), (50.0, 'curso', 1))

        self.patch_umbral(None)
        self.sin_regla_activa()
        data = self.get(url).json()
        self.assertEqual((data['umbral'], data['origen_umbral'], data['total_sobre_umbral']), (None, None, None))
        self.assertTrue(all(e['supera_umbral'] is None for e in data['estudiantes']))

    def test_endpoint_del_estudiante_usa_el_umbral_de_cada_curso(self):
        self.patch_umbral(50)
        url = reverse('student-attendance', args=['1152002'])
        data = self.get(url).json()
        self.assertEqual(data['umbral'], 20.0)  # general
        curso = data['cursos'][0]
        self.assertEqual((curso['umbral'], curso['origen_umbral'], curso['supera_umbral']), (50.0, 'curso', False))

    def test_lista_de_cursos_incluye_umbral_efectivo(self):
        self.patch_umbral(40)
        res = self.get(reverse('course-indicators'), periodo_anio='todos', page_size=50)
        cursos = {c['curso_id']: c for c in res.json()['results']}
        propio, ajeno = cursos[self.curso.id], cursos[self.curso_ajeno.id]
        self.assertEqual((propio['umbral_inasistencia'], propio['umbral_inasistencia_curso'],
                          propio['origen_umbral_inasistencia']), (40.0, 40.0, 'curso'))
        self.assertEqual((ajeno['umbral_inasistencia'], ajeno['umbral_inasistencia_curso'],
                          ajeno['origen_umbral_inasistencia']), (20.0, None, 'general'))


class FormatoAsistenciaUmbralTests(UmbralCursoBaseTestCase):
    """Caso manual de formato_asistencia.xlsx (1155501A, 2026-2) con umbral general y propio."""

    def setUp(self):
        super().setUp()
        Estudiante.objects.create(codigo="1152004", nombre="Estudiante 4", semestre=5, numero_documento="DOC4")
        Nota.objects.create(estudiante_id="1152004", curso=self.curso, periodo=self.periodo)
        fechas = ['2026-09-01', '2026-09-03', '2026-09-08', '2026-09-10', '2026-09-15', '2026-09-17']
        estados = {
            '1152001': ['A', 'A', 'A', 'A', 'A', 'A'],
            '1152002': ['A', 'F', 'F', 'A', 'F', 'A'],
            '1152003': ['A', 'FJ', 'A', 'A', 'F', 'A'],
            '1152004': ['F', 'A', 'A', 'F', 'A', 'A'],
        }
        filas = [
            {'Periodo': '2026-2', 'Codigo Estudiante': codigo, 'Materia': '1155501A', 'Fecha': fecha, 'Estado': estado}
            for codigo, lista in estados.items() for fecha, estado in zip(fechas, lista)
        ]
        res = self.client.post(reverse('import-attendance'), {'file': self.excel(filas)},
                               HTTP_AUTHORIZATION=self.auth(self.admin))
        self.assertEqual(res.status_code, 200, res.content)

    def sobre_umbral(self):
        data = self.get(reverse('course-absence', args=[self.curso.id]), periodo='2026-2').json()
        return sorted(e['codigo'] for e in data['estudiantes'] if e['supera_umbral'])

    def test_umbral_general_propio_y_vuelta_al_general(self):
        self.assertEqual(self.sobre_umbral(), ['1152002', '1152004'])
        self.patch_umbral(40)
        self.assertEqual(self.sobre_umbral(), ['1152002'])
        self.patch_umbral(None)
        self.assertEqual(self.sobre_umbral(), ['1152002', '1152004'])
