import pandas as pd
import io
from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from academico.models import Curso, Docente, Materia, Estudiante, Periodo
from usuarios.models import Usuario

class ImportViewsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        # Mock para Usuario (requerido para Docente en el nuevo esquema)
        self.usuario_mock = Usuario.objects.create(
            nombre="Admin",
            correo="admin@ufps.edu.co",
            rol="DIRECTOR",
            contrasena="123"
        )

    def generate_excel_file(self, data):
        output = io.BytesIO()
        df = pd.DataFrame(data)
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        output.seek(0)
        return output.getvalue()

    def test_importar_estadisticas_carga_success(self):
        """Prueba la importación exitosa de estadísticas de carga (HU-04)."""
        url = reverse('import-load-stats')
        data = {
            "Materia": ["MAT001", "FIS001"],
            "Nombre": ["Matematicas I", "Fisica I"],
            "Horario": ["Lunes 8-10", "Martes 10-12"],
            "# Matriculados": [30, 25],
            "Código Docente": ["DOC001", "DOC002"],
            "Nombre Docente": ["Juan Perez", "Maria Garcia"]
        }
        excel_content = self.generate_excel_file(data)
        excel_file = SimpleUploadedFile(
            "stats.xlsx", 
            excel_content, 
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        response = self.client.post(url, {'file': excel_file})
        
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertEqual(json_data['creados'], 2)
        
        # Verificar en base de datos
        self.assertEqual(Curso.objects.count(), 2)
        self.assertEqual(Docente.objects.count(), 2)
        
        curso = Curso.objects.get(materia__codigo="MAT001")
        self.assertEqual(curso.materia.nombre, "Matematicas I")
        self.assertEqual(curso.docente.nombre, "Juan Perez")
        self.assertEqual(curso.cantidad_matriculados, 30)

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
        
        response = self.client.post(url, {'file': excel_file})
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertEqual(json_data['detalles']['total_procesados'], 2)
        
        # Verificar en BD
        est = Estudiante.objects.get(codigo="1150001")
        self.assertEqual(est.nombre, "Estudiante Uno")
        # 2024-1 -> 2024-02-01 (según mi lógica implementada)
        from datetime import date
        self.assertEqual(est.ingreso, date(2024, 2, 1))

    def test_placeholder_views(self):
        """Verifica que las vistas que aún son placeholders retornen el status template."""
        placeholders = [
            'import-academic-offering'
        ]
        for name in placeholders:
            url = reverse(name)
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            json_data = response.json()
            self.assertEqual(json_data['status'], 'template')
