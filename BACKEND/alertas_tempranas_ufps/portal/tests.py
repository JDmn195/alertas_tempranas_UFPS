"""
HU-37: Rol ESTUDIANTE, creación de cuentas y consulta del riesgo propio.
"""
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from io import StringIO

import jwt
from django.conf import settings
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from academico.models import Curso, Docente, Estudiante, Materia, Nota, Periodo
from alertas.models import Regla, RiesgoEstudiantePeriodo
from alertas.views.alert_generation_views import calcular_y_guardar_riesgo_por_periodos
from usuarios.models import Auditoria, Usuario


def _token(usuario):
    ahora = datetime.now(timezone.utc)
    payload = {'user_id': usuario.id, 'exp': ahora + timedelta(days=1), 'iat': ahora}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')


def _auth(usuario):
    return {'HTTP_AUTHORIZATION': f'Bearer {_token(usuario)}'}


def _estudiante(codigo, nombre='Estudiante', correo=None, documento=None, usuario=None):
    return Estudiante.objects.create(
        codigo=codigo, nombre=nombre, tipo_documento='CC', numero_documento=documento or f'9{codigo}',
        semestre=3, estado_matricula='ACTIVO', email_institucional=correo, usuario=usuario,
    )


def _cuenta_estudiante(correo):
    usuario = Usuario(nombre='Cuenta', correo=correo, rol='ESTUDIANTE')
    usuario.set_unusable_password()
    usuario.save()
    return usuario


# ---------------------------------------------------------------------------
# Comando crear_usuarios_estudiantes
# ---------------------------------------------------------------------------

class CrearUsuariosEstudiantesTests(TestCase):
    def setUp(self):
        self.ana = _estudiante('1151001', 'Ana Pérez', 'ana.perez@ufps.edu.co', documento='1001')
        self.luis = _estudiante('1151002', 'Luis Gómez', 'LUIS.GOMEZ@ufps.edu.co ', documento='1002')
        self.sin_correo = _estudiante('1151003', 'Sin Correo', None, documento='1003')
        self.correo_personal = _estudiante('1151004', 'Correo Personal', 'alguien@gmail.com', documento='1004')

    def _ejecutar(self, *args):
        salida = StringIO()
        call_command('crear_usuarios_estudiantes', *args, stdout=salida)
        return salida.getvalue()

    def test_crea_y_asocia_cuentas_sin_contrasena_utilizable(self):
        salida = self._ejecutar()

        self.ana.refresh_from_db()
        self.luis.refresh_from_db()
        self.assertEqual(self.ana.usuario.rol, 'ESTUDIANTE')
        self.assertEqual(self.ana.usuario.correo, 'ana.perez@ufps.edu.co')
        self.assertEqual(self.luis.usuario.correo, 'luis.gomez@ufps.edu.co')
        self.assertTrue(self.ana.usuario.activo)
        # Sin contraseña utilizable: ni el código ni el documento sirven para entrar
        for usuario, estudiante in ((self.ana.usuario, self.ana), (self.luis.usuario, self.luis)):
            self.assertFalse(usuario.check_password(estudiante.codigo))
            self.assertFalse(usuario.check_password(estudiante.numero_documento))
            self.assertTrue(usuario.contrasena.startswith('!'))
        self.assertIn('Se crearon 2 cuentas', salida)
        self.assertIn('sin correo institucional', salida)

        # Sin correo institucional no se crea nada
        self.assertIsNone(Estudiante.objects.get(codigo='1151003').usuario)
        self.assertIsNone(Estudiante.objects.get(codigo='1151004').usuario)
        self.assertEqual(Usuario.objects.filter(rol='ESTUDIANTE').count(), 2)

        auditoria = Auditoria.objects.filter(tipo_accion='CREAR_CUENTA_ESTUDIANTE')
        self.assertEqual(auditoria.count(), 1)
        self.assertIn('2 cuentas creadas', auditoria.first().detalle)

    def test_no_duplica_al_ejecutarse_dos_veces(self):
        self._ejecutar()
        salida = self._ejecutar()

        self.assertEqual(Usuario.objects.filter(rol='ESTUDIANTE').count(), 2)
        self.assertIn('Se crearon 0 cuentas', salida)
        self.assertEqual(Auditoria.objects.filter(tipo_accion='CREAR_CUENTA_ESTUDIANTE').count(), 1)

    def test_reporta_correo_ya_usado_sin_modificar_la_cuenta(self):
        docente = Usuario.objects.create(
            nombre='Docente', correo='ana.perez@ufps.edu.co', rol='DOCENTE', contrasena='hash-original',
        )
        salida = self._ejecutar()

        docente.refresh_from_db()
        self.assertEqual(docente.rol, 'DOCENTE')
        self.assertEqual(docente.contrasena, 'hash-original')
        self.ana.refresh_from_db()
        self.assertIsNone(self.ana.usuario)
        self.assertIn('ana.perez@ufps.edu.co ya pertenece a otra cuenta', salida)
        self.assertIn('1 estudiantes con el correo ya usado', salida)

    def test_dry_run_no_guarda_nada(self):
        salida = self._ejecutar('--dry-run')

        self.assertIn('Se crearían 2 cuentas', salida)
        self.assertFalse(Usuario.objects.filter(rol='ESTUDIANTE').exists())
        self.assertFalse(Estudiante.objects.filter(usuario__isnull=False).exists())
        self.assertFalse(Auditoria.objects.filter(tipo_accion='CREAR_CUENTA_ESTUDIANTE').exists())

    def test_codigos_limita_la_creacion(self):
        salida = self._ejecutar('--codigos', '1151002', '9999999')

        self.assertEqual(list(Usuario.objects.filter(rol='ESTUDIANTE').values_list('correo', flat=True)),
                         ['luis.gomez@ufps.edu.co'])
        self.assertIn('9999999: no existe el estudiante', salida)


# ---------------------------------------------------------------------------
# GET /api/portal/riesgo/
# ---------------------------------------------------------------------------

class RiesgoPropioTests(TestCase):
    def setUp(self):
        self.url = reverse('portal-riesgo')
        usuario_docente = Usuario.objects.create(nombre='Docente', correo='doc@ufps.edu.co', rol='DOCENTE')
        docente = Docente.objects.create(codigo='D1', nombre='Docente', tipo_vinculacion='Planta', usuario=usuario_docente)
        self.calculo = Materia.objects.create(codigo='1150101', nombre='Cálculo I', creditos=4, semestre=1)
        self.fisica = Materia.objects.create(codigo='1150102', nombre='Física I', creditos=3, semestre=1)
        self.curso_calculo = Curso.objects.create(materia=self.calculo, grupo='A', docente=docente)
        self.curso_fisica = Curso.objects.create(materia=self.fisica, grupo='A', docente=docente)
        self.p1 = Periodo.objects.create(anio=2025, semestre=1)
        self.p2 = Periodo.objects.create(anio=2025, semestre=2)

        self.cuenta = _cuenta_estudiante('ana@ufps.edu.co')
        self.estudiante = _estudiante('1151001', 'Ana Pérez', 'ana@ufps.edu.co', usuario=self.cuenta)
        self.otro = _estudiante('1151002', 'Otro', 'otro@ufps.edu.co')

        self.regla = Regla.objects.create(
            nombre='Promedio Bajo', tipo='PROMEDIO', operador='<', valor_umbral=Decimal('3.0'),
            nivel='medium', prioridad=20, descripcion='Nota interna del comité',
        )

    def _notas_en_riesgo(self):
        # 2025-1: Física 2.0 (perdida). 2025-2: Cálculo 3.5 (aprobada) → PPA 2.86 < 3.0
        Nota.objects.create(estudiante=self.estudiante, curso=self.curso_fisica, periodo=self.p1, definitiva=Decimal('2.0'))
        Nota.objects.create(estudiante=self.estudiante, curso=self.curso_calculo, periodo=self.p2, definitiva=Decimal('3.5'))
        # Notas del otro estudiante: no deben influir en nada
        Nota.objects.create(estudiante=self.otro, curso=self.curso_calculo, periodo=self.p2, definitiva=Decimal('5.0'))
        calcular_y_guardar_riesgo_por_periodos(self.estudiante)

    def test_estudiante_obtiene_su_propio_riesgo(self):
        self._notas_en_riesgo()
        resp = self.client.get(self.url, **_auth(self.cuenta))

        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.json()
        self.assertEqual(data['estudiante']['codigo'], '1151001')
        riesgo_guardado = RiesgoEstudiantePeriodo.objects.get(estudiante=self.estudiante, periodo=self.p2)
        self.assertEqual(data['riesgo']['nivel'], 'medium')
        self.assertEqual(data['riesgo']['nivel_texto'], 'Medio')
        self.assertEqual(data['riesgo']['periodo'], '2025-2')
        self.assertEqual(data['riesgo']['fecha_calculo'], riesgo_guardado.fecha_calculo.isoformat())

        self.assertEqual(len(data['causas']), 1)
        causa = data['causas'][0]
        self.assertEqual(causa['regla'], 'Promedio Bajo')
        self.assertEqual(causa['tipo'], 'PROMEDIO')
        self.assertEqual(causa['operador'], '<')
        self.assertEqual(causa['umbral'], 3.0)
        self.assertAlmostEqual(causa['valor'], 2.86, places=2)

        indicadores = data['indicadores']
        self.assertAlmostEqual(indicadores['ppa'], 2.86, places=2)
        self.assertEqual(indicadores['pps'], 3.5)
        self.assertEqual(indicadores['periodo_pps'], '2025-2')
        self.assertEqual(indicadores['materias_reprobadas'], 1)
        self.assertEqual(indicadores['lista_materias_reprobadas'], ['Física I'])
        self.assertEqual(indicadores['creditos_aprobados'], 4)

    def test_no_crea_ni_modifica_alertas(self):
        from alertas.models import Alerta
        self._notas_en_riesgo()
        antes = list(Alerta.objects.values_list('id', 'estado'))
        self.client.get(self.url, **_auth(self.cuenta))
        self.assertEqual(list(Alerta.objects.values_list('id', 'estado')), antes)

    def test_sin_calculo_responde_nivel_null_con_mensaje(self):
        resp = self.client.get(self.url, **_auth(self.cuenta))

        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIsNone(data['riesgo']['nivel'])
        self.assertTrue(data['riesgo']['mensaje'])
        self.assertEqual(data['causas'], [])

    def test_cuenta_sin_estudiante_asociado_recibe_403_y_queda_auditado(self):
        huerfana = _cuenta_estudiante('huerfana@ufps.edu.co')
        resp = self.client.get(self.url, **_auth(huerfana))

        self.assertEqual(resp.status_code, 403)
        registro = Auditoria.objects.get(usuario=huerfana, tipo_accion='ACCESO_DENEGADO')
        self.assertIn('sin estudiante asociado', registro.detalle)

    def test_sin_token_recibe_401(self):
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_personal_recibe_403_en_el_portal(self):
        admin = Usuario.objects.create(nombre='Admin', correo='admin@ufps.edu.co', rol='ADMINISTRADOR')
        resp = self.client.get(self.url, **_auth(admin))
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(Auditoria.objects.filter(usuario=admin, tipo_accion='ACCESO_DENEGADO').count(), 1)

    def test_ignora_codigo_en_parametros(self):
        """El estudiante sale del token: un ?codigo= de otro estudiante no cambia la respuesta."""
        self._notas_en_riesgo()
        resp = self.client.get(self.url, {'codigo': self.otro.codigo}, **_auth(self.cuenta))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['estudiante']['codigo'], self.estudiante.codigo)

    def test_respuesta_sin_campos_internos(self):
        self._notas_en_riesgo()
        data = self.client.get(self.url, **_auth(self.cuenta)).json()

        def claves(valor):
            if isinstance(valor, dict):
                for k, v in valor.items():
                    yield k
                    yield from claves(v)
            elif isinstance(valor, list):
                for v in valor:
                    yield from claves(v)

        prohibidas = {
            'id', 'usuario', 'usuario_id', 'usuario_rol', 'docente', 'observaciones', 'anotaciones',
            'evidencias', 'evidencia', 'metadata', 'detalle', 'descripcion', 'auditoria', 'fecha_hora',
            'tipo_accion', 'numero_documento', 'tipo_documento', 'correo', 'email_personal',
            'email_institucional', 'celular', 'prioridad', 'parametros', 'reglas_aplicadas',
        }
        presentes = set(claves(data)) & prohibidas
        self.assertEqual(presentes, set())
        self.assertNotIn('Nota interna del comité', json.dumps(data, ensure_ascii=False))

    def test_causa_de_inasistencia_incluye_materias_y_umbral(self):
        RiesgoEstudiantePeriodo.objects.create(
            estudiante=self.estudiante, periodo=self.p2, nivel_riesgo='high',
            reglas_aplicadas=[{
                'id': None, 'nombre': 'Inasistencia', 'nivel': 'high', 'valor': 30.0, 'tipo': 'INASISTENCIA',
                'cursos': [
                    {'curso_id': self.curso_calculo.pk, 'materia_codigo': '1150101', 'grupo': 'A',
                     'porcentaje': 30.0, 'umbral': 25.0},
                    {'curso_id': self.curso_fisica.pk, 'materia_codigo': '1150102', 'grupo': 'A',
                     'porcentaje': 22.0, 'umbral': 20.0},
                ],
            }],
        )
        data = self.client.get(self.url, **_auth(self.cuenta)).json()

        causa = data['causas'][0]
        self.assertEqual(causa['tipo'], 'INASISTENCIA')
        self.assertEqual(causa['valor'], 30.0)
        self.assertEqual(causa['umbral'], 25.0)
        self.assertEqual([m['materia'] for m in causa['materias']], ['Cálculo I', 'Física I'])
        self.assertNotIn('curso_id', causa['materias'][0])
