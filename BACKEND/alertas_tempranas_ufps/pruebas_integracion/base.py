"""
Base de las pruebas de integración.

A diferencia de las pruebas unitarias de cada app, aquí cada caso recorre el
sistema completo a través de la API: login real (JWT), endpoints, servicios,
señales y base de datos. Solo se simula lo externo: la API de correo (Brevo).

En los tests las tareas "en segundo plano" corren síncronas
(TAREAS_EN_SEGUNDO_PLANO=False), así que al responder un endpoint ya terminó
el recálculo de riesgo y alertas que dispara.
"""
import io
import json
import os
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pandas as pd
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from academico.models import Curso, Docente, Estudiante, Materia
from alertas.models import Regla
from usuarios.models import Usuario

CONTRASENA = 'Clave-Segura-2026'

COLUMNAS_HISTORIAL = [
    'Periodo', 'Materia Base', 'Codigo Materia', 'Nombre Materia',
    'Corte 1', 'Corte 2', 'Corte 3', 'Examen Final', 'Definitiva',
]


def _respuesta_brevo(status=201):
    resp = MagicMock()
    resp.status_code = status
    resp.text = ''
    return resp


# Hash rápido: cada test inicia sesión con varios usuarios y PBKDF2 hace lenta la suite
@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class IntegracionTestCase(TestCase):
    """
    Escenario base:
      - Un usuario por rol, con contraseña real, que inicia sesión por /login/.
      - Un docente con dos cursos (grupo A) de materias del pensum.
      - Un docente sin cursos (para validar el alcance por rol).
      - Un estudiante activo sin notas.
      - Regla PROMEDIO < 2.5 (alto). Las reglas CORTE (C1..C4) las crea la migración 0016.
    """

    def setUp(self):
        cache.clear()  # el bloqueo de login por intentos fallidos vive en la caché

        env = patch.dict(os.environ, {'BREVO_API_KEY': 'clave-prueba'})
        env.start()
        self.addCleanup(env.stop)
        brevo = patch('alertas.services.requests.post', return_value=_respuesta_brevo())
        self.brevo = brevo.start()
        self.addCleanup(brevo.stop)

        self.admin = self._usuario('Admin', 'admin@ufps.edu.co', 'ADMINISTRADOR')
        self.director = self._usuario('Directora', 'director@ufps.edu.co', 'DIRECTOR')
        self.bienestar = self._usuario('Bienestar', 'bienestar@ufps.edu.co', 'BIENESTAR')
        self.usuario_docente = self._usuario('Docente Curso', 'docente@ufps.edu.co', 'DOCENTE')
        self.usuario_otro_docente = self._usuario('Otro Docente', 'otro@ufps.edu.co', 'DOCENTE')

        self.docente = Docente.objects.create(
            codigo='D001', nombre='Docente Curso', tipo_vinculacion='Planta', usuario=self.usuario_docente,
        )
        Docente.objects.create(
            codigo='D002', nombre='Otro Docente', tipo_vinculacion='Planta', usuario=self.usuario_otro_docente,
        )

        self.materia_calculo = Materia.objects.create(codigo='1150101', nombre='Cálculo I', creditos=3, semestre=1)
        self.materia_fisica = Materia.objects.create(codigo='1150102', nombre='Física I', creditos=3, semestre=1)
        self.curso_calculo = Curso.objects.create(materia=self.materia_calculo, grupo='A', docente=self.docente)
        self.curso_fisica = Curso.objects.create(materia=self.materia_fisica, grupo='A', docente=self.docente)

        self.estudiante = Estudiante.objects.create(
            codigo='1152001', nombre='Ana Pérez', tipo_documento='CC', numero_documento='100200300',
            semestre=2, estado_matricula='ACTIVO', email_institucional='ana@ufps.edu.co',
        )

        self.regla_promedio = Regla.objects.create(
            nombre='Promedio Crítico', tipo='PROMEDIO', operador='<', valor_umbral=Decimal('2.5'),
            nivel='high', prioridad=30,
        )

        self._tokens = {}

    # ------------------------------------------------------------------
    # Usuarios y sesión
    # ------------------------------------------------------------------

    def _usuario(self, nombre, correo, rol):
        usuario = Usuario(nombre=nombre, correo=correo, rol=rol)
        usuario.set_password(CONTRASENA)
        usuario.save()
        return usuario

    def login(self, usuario, contrasena=CONTRASENA):
        return self.client.post(
            reverse('login'),
            data=json.dumps({'email': usuario.correo, 'password': contrasena}),
            content_type='application/json',
        )

    def token(self, usuario):
        """Token obtenido por el login real (se reutiliza dentro del test)."""
        if usuario.pk not in self._tokens:
            resp = self.login(usuario)
            self.assertEqual(resp.status_code, 200, resp.content)
            self._tokens[usuario.pk] = resp.json()['token']
        return self._tokens[usuario.pk]

    # ------------------------------------------------------------------
    # Llamadas a la API
    # ------------------------------------------------------------------

    def api(self, metodo, nombre_url, usuario=None, datos=None, args=None, query=None, **extra):
        """
        Llama al endpoint `nombre_url` como `usuario` (sin usuario = anónimo).
        Ejecuta los callbacks on_commit (notificaciones) como en producción.
        """
        url = reverse(nombre_url, args=args or [])
        if usuario is not None:
            extra['HTTP_AUTHORIZATION'] = f'Bearer {self.token(usuario)}'
        kwargs = dict(extra)
        if datos is not None:
            kwargs['data'] = json.dumps(datos)
            kwargs['content_type'] = 'application/json'
        elif query is not None:
            kwargs['data'] = query
        with self.captureOnCommitCallbacks(execute=True):
            return getattr(self.client, metodo)(url, **kwargs)

    def importar_historial(self, filas, usuario=None, codigo=None):
        """Sube un historial académico (Excel) por el endpoint de importación."""
        df = pd.DataFrame(filas, columns=COLUMNAS_HISTORIAL)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        archivo = SimpleUploadedFile(
            f'historial_{codigo or self.estudiante.codigo}.xlsx', buffer.getvalue(),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        with self.captureOnCommitCallbacks(execute=True):
            return self.client.post(
                reverse('import-history-individual'), {'file': archivo},
                HTTP_AUTHORIZATION=f'Bearer {self.token(usuario or self.admin)}',
            )

    # ------------------------------------------------------------------
    # Filas de historial de uso frecuente
    # ------------------------------------------------------------------

    @staticmethod
    def fila(periodo, materia, c1=None, c2=None, c3=None, examen=None, definitiva=None, nombre='Materia'):
        return [periodo, materia, f'{materia}A', nombre, c1, c2, c3, examen, definitiva]

    def historial_en_riesgo(self):
        """
        2025-2: Física I perdida (definitiva 2.0)  → PPA 2.0 < 2.5 (regla PROMEDIO).
        2026-1: Cálculo I en curso con cortes 1.5 / 2.0 / 2.5 y sin examen:
                C1 (corte 1 < 2.0), C2A (dos cortes perdidos) y C4 (necesita 5.33 en el examen).
        """
        return [
            self.fila('2025-2', '1150102', definitiva=2.0, nombre='Física I'),
            self.fila('2026-1', '1150101', c1=1.5, c2=2.0, c3=2.5, nombre='Cálculo I'),
        ]
