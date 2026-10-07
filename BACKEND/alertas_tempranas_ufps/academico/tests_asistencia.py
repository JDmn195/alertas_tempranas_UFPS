"""
HU-33: Registro de asistencia manual y por archivo, y matrícula sin notas en el historial.
"""
import io
import json
from datetime import date, datetime, timedelta, timezone

import jwt
import pandas as pd
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, Client
from django.urls import reverse

from academico.models import Asistencia, BitacoraImportacion, Curso, Docente, Estudiante, Materia, Nota, Periodo
from usuarios.models import Usuario


XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class AsistenciaBaseTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = Usuario.objects.create(nombre="Admin", correo="admin@ufps.edu.co", rol="ADMINISTRADOR", contrasena="123", activo=True)
        self.user_docente = Usuario.objects.create(nombre="Docente", correo="docente@ufps.edu.co", rol="DOCENTE", contrasena="123", activo=True)
        self.user_ajeno = Usuario.objects.create(nombre="Ajeno", correo="ajeno@ufps.edu.co", rol="DOCENTE", contrasena="123", activo=True)
        self.docente = Docente.objects.create(codigo="00001", nombre="Docente", tipo_vinculacion="PLANTA", usuario=self.user_docente)
        self.docente_ajeno = Docente.objects.create(codigo="00002", nombre="Ajeno", tipo_vinculacion="PLANTA", usuario=self.user_ajeno)

        self.periodo_anterior = Periodo.objects.create(anio=2026, semestre=1)
        self.periodo = Periodo.objects.create(anio=2026, semestre=2)

        self.materia = Materia.objects.create(codigo="1155501", nombre="Programacion Web", creditos=3, semestre=5)
        self.curso = Curso.objects.create(materia=self.materia, grupo="A", docente=self.docente)
        self.curso_ajeno = Curso.objects.create(materia=self.materia, grupo="B", docente=self.docente_ajeno)

        self.estudiantes = []
        for i in range(1, 4):
            est = Estudiante.objects.create(codigo=f"115200{i}", nombre=f"Estudiante {i}", semestre=5, numero_documento=f"DOC{i}")
            Nota.objects.create(estudiante=est, curso=self.curso, periodo=self.periodo)
            self.estudiantes.append(est)
        self.no_matriculado = Estudiante.objects.create(codigo="1152009", nombre="Sin Matricula", semestre=5, numero_documento="DOC9")
        Nota.objects.create(estudiante=self.no_matriculado, curso=self.curso_ajeno, periodo=self.periodo)

        self.ayer = date.today() - timedelta(days=1)

    def auth(self, usuario):
        payload = {
            'user_id': usuario.id,
            'exp': datetime.now(timezone.utc) + timedelta(days=1),
            'iat': datetime.now(timezone.utc),
        }
        return f"Bearer {jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')}"

    def excel(self, data, nombre="asistencia.xlsx"):
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            pd.DataFrame(data).to_excel(writer, index=False)
        return SimpleUploadedFile(nombre, output.getvalue(), content_type=XLSX)


class MatriculaSinNotasTests(AsistenciaBaseTestCase):
    """Historial: las filas sin notas son matrícula solo en el periodo más reciente."""

    def _importar(self, periodo):
        data = {
            "Periodo": [periodo], "Materia Base": ["1155501"], "Codigo Materia": ["1155501A"],
            "Nombre Materia": ["Programacion Web"], "Corte 1": [""], "Corte 2": [""], "Corte 3": [""],
            "Examen Final": [""], "Definitiva": [""],
        }
        archivo = self.excel(data, nombre=f"historial_{self.no_matriculado.codigo}.xlsx")
        return self.client.post(reverse('import-history-individual'), {'file': archivo}, HTTP_AUTHORIZATION=self.auth(self.admin))

    def test_fila_sin_notas_se_acepta_en_periodo_actual(self):
        response = self._importar("2026-2")
        self.assertEqual(response.status_code, 200, response.json())
        nota = Nota.objects.get(estudiante=self.no_matriculado, curso=self.curso, periodo=self.periodo)
        self.assertIsNone(nota.corte1)
        self.assertIsNone(nota.corte2)
        self.assertIsNone(nota.corte3)
        self.assertIsNone(nota.examen_final)
        self.assertIsNone(nota.definitiva)

    def test_fila_sin_notas_se_rechaza_en_periodo_anterior(self):
        response = self._importar("2026-1")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["errores"][0]["mensaje"], "Fila sin notas.")
        self.assertFalse(Nota.objects.filter(estudiante=self.no_matriculado, curso=self.curso).exists())


class RegistroManualAsistenciaTests(AsistenciaBaseTestCase):
    def url(self, curso=None):
        return reverse('course-attendance', args=[(curso or self.curso).id])

    def post(self, usuario, body, curso=None):
        return self.client.post(self.url(curso), data=json.dumps(body), content_type="application/json",
                                HTTP_AUTHORIZATION=self.auth(usuario))

    def registros(self, estado="ASISTIO"):
        return [{"codigo_estudiante": e.codigo, "estado": estado} for e in self.estudiantes]

    def test_docente_propio_registra_y_consulta(self):
        body = {"fecha": self.ayer.isoformat(), "registros": self.registros()}
        body["registros"][1] = {"codigo_estudiante": "1152002", "estado": "FALTA_JUSTIFICADA", "observacion": "Incapacidad"}
        response = self.post(self.user_docente, body)
        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["creados"], 3)
        self.assertEqual(Asistencia.objects.filter(curso=self.curso, periodo=self.periodo).count(), 3)
        a = Asistencia.objects.get(estudiante_id="1152002", curso=self.curso, fecha_clase=self.ayer)
        self.assertEqual(a.estado, "FALTA_JUSTIFICADA")
        self.assertEqual(a.observacion, "Incapacidad")
        self.assertEqual(a.registrado_por, self.user_docente)

        response = self.client.get(self.url(), {"fecha": self.ayer.isoformat()}, HTTP_AUTHORIZATION=self.auth(self.user_docente))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["fechas_registradas"], [self.ayer.isoformat()])
        self.assertEqual([e["codigo"] for e in data["estudiantes"]], ["1152001", "1152002", "1152003"])
        self.assertEqual(data["estudiantes"][1]["estado"], "FALTA_JUSTIFICADA")

    def test_administrador_puede_registrar(self):
        response = self.post(self.admin, {"fecha": self.ayer.isoformat(), "registros": self.registros()})
        self.assertEqual(response.status_code, 200)

    def test_docente_ajeno_recibe_403(self):
        response = self.post(self.user_ajeno, {"fecha": self.ayer.isoformat(), "registros": self.registros()})
        self.assertEqual(response.status_code, 403)
        response = self.client.get(self.url(), HTTP_AUTHORIZATION=self.auth(self.user_ajeno))
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Asistencia.objects.exists())

    def test_estudiante_no_matriculado_no_guarda_nada(self):
        registros = self.registros() + [{"codigo_estudiante": self.no_matriculado.codigo, "estado": "FALTA"}]
        response = self.post(self.user_docente, {"fecha": self.ayer.isoformat(), "registros": registros})
        self.assertEqual(response.status_code, 400)
        errores = response.json()["errores"]
        self.assertEqual(len(errores), 1)
        self.assertEqual(errores[0]["codigo_estudiante"], self.no_matriculado.codigo)
        self.assertFalse(Asistencia.objects.exists())

    def test_estado_invalido_no_guarda_nada(self):
        registros = self.registros()
        registros[0]["estado"] = "TARDE"
        response = self.post(self.user_docente, {"fecha": self.ayer.isoformat(), "registros": registros})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["errores"][0]["campo"], "estado")
        self.assertFalse(Asistencia.objects.exists())

    def test_fecha_futura_rechazada(self):
        manana = (date.today() + timedelta(days=1)).isoformat()
        response = self.post(self.user_docente, {"fecha": manana, "registros": self.registros()})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Asistencia.objects.exists())

    def test_correccion_de_fecha_no_duplica(self):
        fecha = self.ayer.isoformat()
        self.post(self.user_docente, {"fecha": fecha, "registros": self.registros()})
        response = self.post(self.user_docente, {"fecha": fecha, "registros": [{"codigo_estudiante": "1152001", "estado": "F"}]})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["actualizados"], 1)
        self.assertEqual(response.json()["creados"], 0)
        self.assertEqual(Asistencia.objects.filter(curso=self.curso, fecha_clase=self.ayer).count(), 3)
        self.assertEqual(Asistencia.objects.get(estudiante_id="1152001", fecha_clase=self.ayer).estado, "FALTA")


class ImportacionAsistenciaTests(AsistenciaBaseTestCase):
    def datos(self, filas):
        return {
            "Periodo": [f[0] for f in filas],
            "Codigo Estudiante": [f[1] for f in filas],
            "Materia": [f[2] for f in filas],
            "Fecha": [f[3] for f in filas],
            "Estado": [f[4] for f in filas],
        }

    def filas_validas(self):
        hace_dos = self.ayer - timedelta(days=1)
        return [
            ("2026-2", 1152001, "1155501A", pd.Timestamp(self.ayer), "A"),
            ("2026-2", 1152002, "1155501A", pd.Timestamp(self.ayer), "f"),
            ("2026-2", 1152003, "1155501A", hace_dos.isoformat(), "fj"),
            ("2026-2", 1152001, "1155501A", hace_dos.isoformat(), "Falta_Justificada"),
        ]

    def importar(self, filas, usuario=None):
        archivo = self.excel(self.datos(filas))
        return self.client.post(reverse('import-attendance'), {'file': archivo},
                                HTTP_AUTHORIZATION=self.auth(usuario or self.user_docente))

    def test_archivo_valido(self):
        response = self.importar(self.filas_validas())
        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["creados"], 4)
        self.assertEqual(response.json()["actualizados"], 0)
        self.assertEqual(Asistencia.objects.count(), 4)
        self.assertEqual(Asistencia.objects.get(estudiante_id="1152002").estado, "FALTA")
        self.assertEqual(Asistencia.objects.get(estudiante_id="1152003").estado, "FALTA_JUSTIFICADA")

    def test_archivo_con_un_error_no_guarda_nada(self):
        filas = self.filas_validas() + [("2026-2", 1152009, "1155501A", self.ayer.isoformat(), "A")]
        response = self.importar(filas)
        self.assertEqual(response.status_code, 400)
        errores = response.json()["errores"]
        self.assertEqual(len(errores), 1)
        self.assertEqual(errores[0]["fila"], 6)
        self.assertFalse(Asistencia.objects.exists())

    def test_errores_por_fila(self):
        manana = (date.today() + timedelta(days=1)).isoformat()
        filas = [
            ("2026-3", 1152001, "1155501A", self.ayer.isoformat(), "A"),
            ("2026-2", 1152001, "9999999A", self.ayer.isoformat(), "A"),
            ("2026-2", 1152001, "1155501A", "07/10/2026", "A"),
            ("2026-2", 1152001, "1155501A", manana, "A"),
            ("2026-2", 1152001, "1155501A", self.ayer.isoformat(), "X"),
            ("2026-2", 1152002, "1155501A", self.ayer.isoformat(), "A"),
            ("2026-2", 1152002, "1155501A", self.ayer.isoformat(), "F"),
        ]
        response = self.importar(filas)
        self.assertEqual(response.status_code, 400)
        por_fila = {e["fila"]: e["campo"] for e in response.json()["errores"]}
        self.assertEqual(por_fila, {2: "Periodo", 3: "Materia", 4: "Fecha", 5: "Fecha", 6: "Estado", 8: "Fila"})
        self.assertFalse(Asistencia.objects.exists())

    def test_reimportacion_sin_duplicados(self):
        self.importar(self.filas_validas())
        filas = self.filas_validas()
        filas[0] = ("2026-2", 1152001, "1155501A", pd.Timestamp(self.ayer), "F")
        response = self.importar(filas)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["creados"], 0)
        self.assertEqual(response.json()["actualizados"], 4)
        self.assertEqual(Asistencia.objects.count(), 4)
        self.assertEqual(Asistencia.objects.get(estudiante_id="1152001", fecha_clase=self.ayer).estado, "FALTA")

    def test_curso_ajeno_del_docente(self):
        filas = [("2026-2", 1152009, "1155501B", self.ayer.isoformat(), "A")]
        response = self.importar(filas)
        self.assertEqual(response.status_code, 400)
        self.assertIn("no está asignado", response.json()["errores"][0]["mensaje"])
        # El administrador sí puede importar ese curso
        response = self.importar(filas, usuario=self.admin)
        self.assertEqual(response.status_code, 200)

    def test_bitacora_tipo_asistencia(self):
        self.importar(self.filas_validas())
        bitacora = BitacoraImportacion.objects.get(tipo="ASISTENCIA")
        self.assertTrue(bitacora.exitoso)
        self.assertEqual(bitacora.total_procesados, 4)
        self.assertEqual(bitacora.usuario, self.user_docente)
