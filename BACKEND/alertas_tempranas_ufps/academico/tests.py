import pandas as pd
import io
import jwt
from datetime import datetime, timedelta, timezone
from django.test import TestCase, Client
from django.urls import reverse
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from academico.models import Curso, Docente, Materia, Estudiante, Periodo, Nota
from alertas.models import RiesgoEstudiante, RiesgoEstudiantePeriodo, Alerta, Regla
from usuarios.models import Usuario

class ImportViewsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        # Admin user
        self.admin_user = Usuario.objects.create(
            nombre="Admin",
            correo="admin@ufps.edu.co",
            rol="ADMINISTRADOR",
            contrasena="123",
            activo=True
        )
        self.admin_token = self.get_auth_header(self.admin_user)

        # Docente user
        self.docente_user = Usuario.objects.create(
            nombre="Carlos Docente",
            correo="carlos@ufps.edu.co",
            rol="DOCENTE",
            contrasena="123",
            activo=True
        )
        self.docente_token = self.get_auth_header(self.docente_user)

    def get_auth_header(self, usuario):
        payload = {
            'user_id': usuario.id,
            'exp': datetime.now(timezone.utc) + timedelta(days=1),
            'iat': datetime.now(timezone.utc)
        }
        token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')
        return f"Bearer {token}"

    def generate_excel_file(self, data):
        output = io.BytesIO()
        df = pd.DataFrame(data)
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        output.seek(0)
        return output.getvalue()

    def test_importar_docentes_success(self):
        """Prueba la importación exitosa de docentes con normalización de códigos."""
        url = reverse('import-teachers')
        data = {
            "Código Docente": [1713.0, "01714.0", "01715"],
            "Nombre Docente": ["Juan Perez", "Maria Garcia", "Pedro Gomez"],
            "Tipo Vinculación": ["Planta", "Cátedra", "Planta"],
            "Departamento": ["Sistemas", "Sistemas", "Sistemas"],
            "Correo Personal": ["juan@gmail.com", "maria@gmail.com", "pedro@gmail.com"],
            "Correo Institucional": ["juan@ufps.edu.co", "maria@ufps.edu.co", "pedro@ufps.edu.co"],
            "Celular": ["123", "456", "789"]
        }
        excel_content = self.generate_excel_file(data)
        excel_file = SimpleUploadedFile(
            "docentes.xlsx", 
            excel_content, 
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        response = self.client.post(
            url, 
            {'file': excel_file}, 
            HTTP_AUTHORIZATION=self.admin_token
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Verificar en base de datos que se guardó como 01713 y no 1713.0
        doc1 = Docente.objects.get(correo_institucional="juan@ufps.edu.co")
        self.assertEqual(doc1.codigo, "01713")
        
        doc2 = Docente.objects.get(correo_institucional="maria@ufps.edu.co")
        self.assertEqual(doc2.codigo, "01714")

        doc3 = Docente.objects.get(correo_institucional="pedro@ufps.edu.co")
        self.assertEqual(doc3.codigo, "01715")

    def test_importar_estudiantes_dirplan_success(self):
        """Prueba la importación exitosa de estudiantes (HU-01)."""
        url = reverse('import-students-dirplan')
        data = {
            "Codigo": ["1150001", "1150002"],
            "Nombre Alumno": ["Estudiante Uno", "Estudiante Dos"],
            "Documento": ["10001", "10002"],
            "Ingreso": ["2024-1", "2024-2"],
            "Promedio": [4.5, 3.8],
            "Semestre": [1, 2]
        }
        excel_content = self.generate_excel_file(data)
        excel_file = SimpleUploadedFile(
            "students.xlsx",
            excel_content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        response = self.client.post(
            url, 
            {'file': excel_file}, 
            HTTP_AUTHORIZATION=self.admin_token
        )
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertEqual(json_data['detalles']['total_procesados'], 2)
        
        # Verificar en BD
        est = Estudiante.objects.get(codigo="1150001")
        self.assertEqual(est.nombre, "Estudiante Uno")

    def test_teacher_dashboard_view(self):
        """Prueba la vista del panel del docente."""
        # Configurar docente
        docente = Docente.objects.create(
            codigo="01713",
            nombre="Carlos Docente",
            tipo_vinculacion="Planta",
            correo_personal="carlos@gmail.com",
            correo_institucional="carlos@ufps.edu.co",
            usuario=self.docente_user
        )

        # Configurar materia, periodo y curso
        materia = Materia.objects.create(codigo="1150301", nombre="Estructuras de Datos")
        periodo = Periodo.objects.create(anio=2025, semestre=1)
        curso = Curso.objects.create(
            materia=materia,
            docente=docente,
            grupo="A",
            cantidad_matriculados=2
        )

        # Configurar estudiantes, nota, riesgo y alerta
        est1 = Estudiante.objects.create(codigo="1151234", nombre="Estudiante Riesgo Alto", semestre=4, numero_documento="DOC1")
        est2 = Estudiante.objects.create(codigo="1151235", nombre="Estudiante Estable", semestre=4, numero_documento="DOC2")

        Nota.objects.create(estudiante=est1, curso=curso, periodo=periodo, definitiva=2.3)
        Nota.objects.create(estudiante=est2, curso=curso, periodo=periodo, definitiva=4.5)

        RiesgoEstudiante.objects.create(estudiante=est1, nivel_riesgo="high")
        RiesgoEstudiante.objects.create(estudiante=est2, nivel_riesgo="low")
        # El panel del docente lee el riesgo del último periodo (RiesgoEstudiantePeriodo)
        RiesgoEstudiantePeriodo.objects.create(estudiante=est1, periodo=periodo, nivel_riesgo="high")
        RiesgoEstudiantePeriodo.objects.create(estudiante=est2, periodo=periodo, nivel_riesgo="low")

        regla = Regla.objects.create(nombre="Prueba", tipo="PROMEDIO", valor_umbral=3.0, operador="<", nivel="high")
        Alerta.objects.create(estudiante=est1, regla=regla, estado="activa")

        # Petición a la vista
        url = reverse('teacher-dashboard')
        response = self.client.get(
            url, 
            {'page': 1, 'page_size': 10, 'periodo_anio': '2025', 'periodo_semestre': '1'},
            HTTP_AUTHORIZATION=self.docente_token
        )

        self.assertEqual(response.status_code, 200)
        json_data = response.json()

        # Verificar datos devueltos
        self.assertEqual(json_data['nombre_docente'], "Carlos Docente")
        self.assertEqual(len(json_data['cursos']), 1)
        self.assertEqual(json_data['cursos'][0]['materia'], "Estructuras de Datos")
        self.assertEqual(json_data['cursos'][0]['en_riesgo'], 1)
        self.assertEqual(json_data['cursos'][0]['estado'], 'CRÍTICO') # Tasa de reprobación 50% >= 30%

        self.assertEqual(len(json_data['estudiantes_en_riesgo']), 1)
        self.assertEqual(json_data['estudiantes_en_riesgo'][0]['nombre'], "Estudiante Riesgo Alto")
        self.assertEqual(json_data['estudiantes_en_riesgo'][0]['nivel_riesgo'], "high")
        self.assertEqual(json_data['estudiantes_en_riesgo'][0]['alertas_activas'], 1)
        self.assertEqual(json_data['total_en_riesgo'], 1)

    def test_teacher_course_students_view(self):
        """Prueba el endpoint de estudiantes en riesgo por curso para el docente."""
        docente = Docente.objects.create(
            codigo="01713",
            nombre="Carlos Docente",
            tipo_vinculacion="Planta",
            correo_personal="carlos@gmail.com",
            correo_institucional="carlos@ufps.edu.co",
            usuario=self.docente_user
        )
        materia = Materia.objects.create(codigo="1150301", nombre="Estructuras de Datos")
        periodo = Periodo.objects.create(anio=2025, semestre=1)
        curso = Curso.objects.create(
            materia=materia,
            docente=docente,
            grupo="A",
            cantidad_matriculados=2
        )
        est1 = Estudiante.objects.create(codigo="1151234", nombre="Estudiante Riesgo Alto", semestre=4, numero_documento="DOC1")
        Nota.objects.create(estudiante=est1, curso=curso, periodo=periodo, definitiva=2.3)
        RiesgoEstudiante.objects.create(estudiante=est1, nivel_riesgo="high")
        regla = Regla.objects.create(nombre="Prueba", tipo="PROMEDIO", valor_umbral=3.0, operador="<", nivel="high")
        Alerta.objects.create(estudiante=est1, regla=regla, estado="activa")

        url = reverse('teacher-course-students', kwargs={'curso_id': curso.id})
        response = self.client.get(
            url,
            {'periodo_anio': '2025', 'periodo_semestre': '1'},
            HTTP_AUTHORIZATION=self.docente_token
        )
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertEqual(json_data['curso']['materia'], "Estructuras de Datos")
        self.assertEqual(len(json_data['estudiantes']), 1)
        self.assertEqual(json_data['estudiantes'][0]['codigo'], "1151234")

    def test_course_detail_view(self):
        """Prueba el detalle de curso para roles autorizados (HU-11)."""
        docente = Docente.objects.create(
            codigo="01713",
            nombre="Carlos Docente",
            tipo_vinculacion="Planta",
            correo_personal="carlos@gmail.com",
            correo_institucional="carlos@ufps.edu.co",
            usuario=self.docente_user
        )
        materia = Materia.objects.create(codigo="1150301", nombre="Estructuras de Datos")
        periodo = Periodo.objects.create(anio=2025, semestre=1)
        curso = Curso.objects.create(
            materia=materia,
            docente=docente,
            grupo="A",
            cantidad_matriculados=1
        )
        est1 = Estudiante.objects.create(codigo="1151234", nombre="Estudiante Riesgo Alto", semestre=4, numero_documento="DOC1")
        Nota.objects.create(estudiante=est1, curso=curso, periodo=periodo, definitiva=2.3)

        url = reverse('course-detail', kwargs={'curso_id': curso.id})
        response = self.client.get(
            url,
            HTTP_AUTHORIZATION=self.admin_token
        )
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertEqual(json_data['materia'], "Estructuras de Datos")
        self.assertEqual(json_data['docente'], "Carlos Docente")
        self.assertEqual(len(json_data['estudiantes']), 1)
        self.assertEqual(json_data['estudiantes'][0]['codigo'], "1151234")

    def test_docente_alerts_filtering(self):
        """Prueba que el listado de alertas filtre solo las de los alumnos del docente."""
        docente_propio = Docente.objects.create(
            codigo="01713",
            nombre="Carlos Docente",
            tipo_vinculacion="Planta",
            correo_personal="carlos@gmail.com",
            correo_institucional="carlos@ufps.edu.co",
            usuario=self.docente_user
        )
        
        materia = Materia.objects.create(codigo="1150301", nombre="Estructuras de Datos")
        periodo = Periodo.objects.create(anio=2025, semestre=1)
        
        # Curso propio del docente
        curso_propio = Curso.objects.create(
            materia=materia,
            docente=docente_propio,
            grupo="A",
            cantidad_matriculados=1
        )
        
        # Estudiante propio del docente
        est_propio = Estudiante.objects.create(codigo="1151234", nombre="Estudiante Propio", semestre=4, numero_documento="DOC1")
        Nota.objects.create(estudiante=est_propio, curso=curso_propio, periodo=periodo, definitiva=2.0)
        
        # Estudiante ajeno del docente
        est_ajeno = Estudiante.objects.create(codigo="1159999", nombre="Estudiante Ajeno", semestre=4, numero_documento="DOC99")
        
        regla = Regla.objects.create(nombre="Prueba", tipo="PROMEDIO", valor_umbral=3.0, operador="<", nivel="high")
        
        # Crear alerta propia
        alerta_propia = Alerta.objects.create(estudiante=est_propio, regla=regla, estado="activa")
        # Crear alerta ajena
        alerta_ajena = Alerta.objects.create(estudiante=est_ajeno, regla=regla, estado="activa")
        
        response = self.client.get(
            '/api/alertas/?estado=activa',
            HTTP_AUTHORIZATION=self.docente_token
        )
        
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        
        # Debe retornar solo la alerta propia (1 alerta)
        self.assertEqual(len(json_data['alertas']), 1)
        self.assertEqual(json_data['alertas'][0]['studentCode'], "1151234")
        self.assertEqual(json_data['conteos']['activa'], 1)

    def test_importar_pensum_success(self):
        url = reverse('import-pensum')
        data = {
            "Codigo": ["1155101.0", "1155102", "1155103"],
            "Nombre": ["Matematicas I", "Programacion I", "Electiva"],
            "Creditos": [4, 4, 3],
            "Semestre": [1, 1, ""],
            "Tipo": ["linea", "linea", "profesional"],
            "Equivale A": ["", "", ""]
        }
        excel_content = self.generate_excel_file(data)
        excel_file = SimpleUploadedFile("pensum.xlsx", excel_content, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response = self.client.post(url, {'file': excel_file}, HTTP_AUTHORIZATION=self.admin_token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Materia.objects.count(), 3)
        self.assertEqual(Materia.objects.get(codigo="1155101").nombre, "Matematicas I")

    def test_importar_pensum_actualiza_existente(self):
        Materia.objects.create(codigo="1155101", nombre="Matematicas I", creditos=3, tipo="linea")
        url = reverse('import-pensum')
        data = {
            "Codigo": ["1155101"],
            "Nombre": ["Matematicas 1",],
            "Creditos": [4],
            "Semestre": [1],
            "Tipo": ["linea"],
            "Equivale A": [""]
        }
        excel_content = self.generate_excel_file(data)
        excel_file = SimpleUploadedFile("pensum2.xlsx", excel_content, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response = self.client.post(url, {'file': excel_file}, HTTP_AUTHORIZATION=self.admin_token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Materia.objects.count(), 1)
        self.assertEqual(Materia.objects.get(codigo="1155101").creditos, 4)

    def test_importar_pensum_con_equivalencia_y_orden(self):
        url = reverse('import-pensum')
        data = {
            "Codigo": ["1155201", "1155101"],
            "Nombre": ["Materia equivalente", "Materia original"],
            "Creditos": [4, 4],
            "Semestre": [2, 1],
            "Tipo": ["linea", "linea"],
            "Equivale A": ["1155101", ""]
        }
        excel_content = self.generate_excel_file(data)
        excel_file = SimpleUploadedFile("pensum_equiv.xlsx", excel_content, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response = self.client.post(url, {'file': excel_file}, HTTP_AUTHORIZATION=self.admin_token)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Materia.objects.filter(codigo="1155101").exists())
        self.assertTrue(Materia.objects.filter(codigo="1155201").exists())
        self.assertEqual(Materia.objects.get(codigo="1155101").equivalencias_entrantes.count(), 1)

    def test_importar_pensum_error_tipo_invalido(self):
        url = reverse('import-pensum')
        data = {
            "Codigo": ["1155101"],
            "Nombre": ["Matematicas I"],
            "Creditos": [4],
            "Semestre": [1],
            "Tipo": ["invalido"],
            "Equivale A": [""]
        }
        excel_content = self.generate_excel_file(data)
        excel_file = SimpleUploadedFile("pensum_err.xlsx", excel_content, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response = self.client.post(url, {'file': excel_file}, HTTP_AUTHORIZATION=self.admin_token)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Materia.objects.count(), 0)

    def test_importar_pensum_rol_denegado(self):
        url = reverse('import-pensum')
        data = {
            "Codigo": ["1155101"],
            "Nombre": ["Matematicas I"],
            "Creditos": [4],
            "Semestre": [1],
            "Tipo": ["linea"],
            "Equivale A": [""]
        }
        excel_content = self.generate_excel_file(data)
        excel_file = SimpleUploadedFile("pensum_denied.xlsx", excel_content, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response = self.client.post(url, {'file': excel_file}, HTTP_AUTHORIZATION=self.docente_token)
        self.assertEqual(response.status_code, 403)

    def test_importar_historial_cuatro_notas_definitiva_calculada(self):
        """Fila con las cuatro notas: definitiva calculada (3.5, 4.0, 3.2 y 3.6 deben dar 3.6)."""
        est = Estudiante.objects.create(codigo="1152001", nombre="Alumno Test", semestre=2, numero_documento="DOC_T1")
        Materia.objects.create(codigo="1155101", nombre="Calculo I", creditos=4, tipo="linea", semestre=1)
        url = reverse('import-history-individual')
        data = {
            "Periodo": ["2025-1"],
            "Materia Base": ["1155101"],
            "Codigo Materia": ["1155101A"],
            "Nombre Materia": ["Calculo I"],
            "Corte 1": [3.5],
            "Corte 2": [4.0],
            "Corte 3": [3.2],
            "Examen Final": [3.6],
            "Definitiva": [""]
        }
        excel_content = self.generate_excel_file(data)
        excel_file = SimpleUploadedFile("historial_1152001.xlsx", excel_content, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response = self.client.post(url, {'file': excel_file}, HTTP_AUTHORIZATION=self.admin_token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Nota.objects.filter(estudiante=est).count(), 1)
        nota = Nota.objects.get(estudiante=est)
        self.assertEqual(float(nota.corte1), 3.5)
        self.assertEqual(float(nota.corte2), 4.0)
        self.assertEqual(float(nota.corte3), 3.2)
        self.assertEqual(float(nota.examen_final), 3.6)
        self.assertEqual(float(nota.definitiva), 3.6)

    def test_importar_historial_periodo_antiguo_solo_definitiva(self):
        """Fila de periodo antiguo solo con definitiva: se guarda la del archivo."""
        est = Estudiante.objects.create(codigo="1152002", nombre="Alumno Antiguo", semestre=5, numero_documento="DOC_T2")
        Materia.objects.create(codigo="1155102", nombre="Algebra Lineal", creditos=3, tipo="linea", semestre=1)
        url = reverse('import-history-individual')
        data = {
            "Periodo": ["2022-1"],
            "Materia Base": ["1155102"],
            "Codigo Materia": ["1155102"],
            "Nombre Materia": ["Algebra Lineal"],
            "Corte 1": [""],
            "Corte 2": [""],
            "Corte 3": [""],
            "Examen Final": [""],
            "Definitiva": [4.2]
        }
        excel_content = self.generate_excel_file(data)
        excel_file = SimpleUploadedFile("historial_1152002.xlsx", excel_content, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response = self.client.post(url, {'file': excel_file}, HTTP_AUTHORIZATION=self.admin_token)
        self.assertEqual(response.status_code, 200)
        nota = Nota.objects.get(estudiante=est)
        self.assertIsNone(nota.corte1)
        self.assertIsNone(nota.corte2)
        self.assertIsNone(nota.corte3)
        self.assertIsNone(nota.examen_final)
        self.assertEqual(float(nota.definitiva), 4.2)

    def test_importar_historial_cortes_parciales_definitiva_vacia(self):
        """Fila con cortes parciales y definitiva vacía: se importa con definitiva null."""
        est = Estudiante.objects.create(codigo="1152003", nombre="Alumno Curso", semestre=1, numero_documento="DOC_T3")
        Materia.objects.create(codigo="1155103", nombre="Quimica", creditos=3, tipo="linea", semestre=1)
        url = reverse('import-history-individual')
        data = {
            "Periodo": ["2025-1"],
            "Materia Base": ["1155103"],
            "Codigo Materia": ["1155103A"],
            "Nombre Materia": ["Quimica"],
            "Corte 1": [4.0],
            "Corte 2": [3.5],
            "Corte 3": [""],
            "Examen Final": [""],
            "Definitiva": [""]
        }
        excel_content = self.generate_excel_file(data)
        excel_file = SimpleUploadedFile("historial_1152003.xlsx", excel_content, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response = self.client.post(url, {'file': excel_file}, HTTP_AUTHORIZATION=self.admin_token)
        self.assertEqual(response.status_code, 200)
        nota = Nota.objects.get(estudiante=est)
        self.assertEqual(float(nota.corte1), 4.0)
        self.assertEqual(float(nota.corte2), 3.5)
        self.assertIsNone(nota.corte3)
        self.assertIsNone(nota.examen_final)
        self.assertIsNone(nota.definitiva)

    def test_importar_historial_definitiva_distinta_calculada_genera_advertencia(self):
        """Definitiva del archivo distinta a la calculada: se guarda la calculada y se reporta una advertencia."""
        est = Estudiante.objects.create(codigo="1152004", nombre="Alumno Dif", semestre=2, numero_documento="DOC_T4")
        Materia.objects.create(codigo="1155104", nombre="Fisica I", creditos=4, tipo="linea", semestre=1)
        url = reverse('import-history-individual')
        data = {
            "Periodo": ["2025-1"],
            "Materia Base": ["1155104"],
            "Codigo Materia": ["1155104B"],
            "Nombre Materia": ["Fisica I"],
            "Corte 1": [3.5],
            "Corte 2": [4.0],
            "Corte 3": [3.2],
            "Examen Final": [3.6],
            "Definitiva": [4.5]
        }
        excel_content = self.generate_excel_file(data)
        excel_file = SimpleUploadedFile("historial_1152004.xlsx", excel_content, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response = self.client.post(url, {'file': excel_file}, HTTP_AUTHORIZATION=self.admin_token)
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertIn("advertencias", json_data)
        self.assertTrue(len(json_data["advertencias"]) > 0)
        nota = Nota.objects.get(estudiante=est)
        self.assertEqual(float(nota.definitiva), 3.6)

    def test_importar_historial_materia_no_esta_en_pensum_error(self):
        """Materia que no está en el pensum: error de fila y no se guarda nada."""
        est = Estudiante.objects.create(codigo="1152005", nombre="Alumno No Pensum", semestre=1, numero_documento="DOC_T5")
        url = reverse('import-history-individual')
        data = {
            "Periodo": ["2025-1"],
            "Materia Base": ["9999999"],
            "Codigo Materia": ["9999999A"],
            "Nombre Materia": ["Materia Inexistente"],
            "Corte 1": [4.0],
            "Corte 2": [4.0],
            "Corte 3": [4.0],
            "Examen Final": [4.0],
            "Definitiva": [4.0]
        }
        excel_content = self.generate_excel_file(data)
        excel_file = SimpleUploadedFile("historial_1152005.xlsx", excel_content, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response = self.client.post(url, {'file': excel_file}, HTTP_AUTHORIZATION=self.admin_token)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Nota.objects.filter(estudiante=est).count(), 0)

    def test_importar_historial_nota_fuera_de_rango_error(self):
        """Nota fuera de rango (por ejemplo 5.5): error de fila."""
        est = Estudiante.objects.create(codigo="1152006", nombre="Alumno Fuera Rango", semestre=1, numero_documento="DOC_T6")
        Materia.objects.create(codigo="1155106", nombre="Biologia", creditos=3, tipo="linea", semestre=1)
        url = reverse('import-history-individual')
        data = {
            "Periodo": ["2025-1"],
            "Materia Base": ["1155106"],
            "Codigo Materia": ["1155106"],
            "Nombre Materia": ["Biologia"],
            "Corte 1": [5.5],
            "Corte 2": [3.0],
            "Corte 3": [3.0],
            "Examen Final": [3.0],
            "Definitiva": [3.5]
        }
        excel_content = self.generate_excel_file(data)
        excel_file = SimpleUploadedFile("historial_1152006.xlsx", excel_content, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        response = self.client.post(url, {'file': excel_file}, HTTP_AUTHORIZATION=self.admin_token)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Nota.objects.filter(estudiante=est).count(), 0)

    def test_importar_historial_reimportar_actualiza_sin_duplicar(self):
        """Reimportar el archivo con un corte cambiado: actualiza la nota sin duplicarla."""
        est = Estudiante.objects.create(codigo="1152007", nombre="Alumno Reimportar", semestre=1, numero_documento="DOC_T7")
        Materia.objects.create(codigo="1155107", nombre="Geometria", creditos=3, tipo="linea", semestre=1)
        url = reverse('import-history-individual')
        data_v1 = {
            "Periodo": ["2025-1"],
            "Materia Base": ["1155107"],
            "Codigo Materia": ["1155107A"],
            "Nombre Materia": ["Geometria"],
            "Corte 1": [3.0],
            "Corte 2": [3.0],
            "Corte 3": [3.0],
            "Examen Final": [3.0],
            "Definitiva": [""]
        }
        excel_v1 = SimpleUploadedFile("historial_1152007.xlsx", self.generate_excel_file(data_v1), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        resp1 = self.client.post(url, {'file': excel_v1}, HTTP_AUTHORIZATION=self.admin_token)
        self.assertEqual(resp1.status_code, 200)
        self.assertEqual(Nota.objects.filter(estudiante=est).count(), 1)
        self.assertEqual(float(Nota.objects.get(estudiante=est).corte1), 3.0)

        # Cambiamos Corte 1 a 4.5
        data_v2 = {
            "Periodo": ["2025-1"],
            "Materia Base": ["1155107"],
            "Codigo Materia": ["1155107A"],
            "Nombre Materia": ["Geometria"],
            "Corte 1": [4.5],
            "Corte 2": [3.0],
            "Corte 3": [3.0],
            "Examen Final": [3.0],
            "Definitiva": [""]
        }
        excel_v2 = SimpleUploadedFile("historial_1152007.xlsx", self.generate_excel_file(data_v2), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        resp2 = self.client.post(url, {'file': excel_v2}, HTTP_AUTHORIZATION=self.admin_token)
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(Nota.objects.filter(estudiante=est).count(), 1)
        self.assertEqual(float(Nota.objects.get(estudiante=est).corte1), 4.5)

    def test_atraso_electiva_con_semestre_no_cuenta_como_atrasada(self):
        """ATRASO: una electiva con semestre asignado no cuenta como materia atrasada."""
        from alertas.views.alert_generation_views import evaluar_reglas_estudiante
        est = Estudiante.objects.create(codigo="1152008", nombre="Alumno Atraso", semestre=3, numero_documento="DOC_T8")
        periodo = Periodo.objects.create(anio=2024, semestre=1)
        
        # Materia de línea de semestre 1 (aprobada)
        docente = Docente.objects.create(
            codigo="01799",
            nombre="Docente Test",
            usuario=self.docente_user
        )
        m1 = Materia.objects.create(codigo="1155108", nombre="Materia Linea 1", creditos=3, tipo="linea", semestre=1)
        curso1 = Curso.objects.create(materia=m1, grupo="A", docente=docente)
        Nota.objects.create(estudiante=est, curso=curso1, periodo=periodo, definitiva=3.5)
        
        # Materia electiva (profesional) con semestre 1 asignado pero sin aprobar
        Materia.objects.create(codigo="1155109", nombre="Electiva I", creditos=3, tipo="profesional", semestre=1)
        
        # Regla de atraso
        regla_atraso = Regla.objects.create(nombre="Atraso > 0", tipo="ATRASO", valor_umbral=0, operador=">", nivel="high")
        
        aplica, val, meta = evaluar_reglas_estudiante(est, [regla_atraso])[regla_atraso.id]
        self.assertEqual(val, 0)
        self.assertFalse(aplica)



