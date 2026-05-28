import pandas as pd
import io
import jwt
from datetime import datetime, timedelta, timezone
from django.test import TestCase, Client
from django.urls import reverse
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from academico.models import Curso, Docente, Materia, Estudiante, Periodo, Nota
from alertas.models import RiesgoEstudiante, Alerta, Regla
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
