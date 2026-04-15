import pandas as pd
import io
from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from academico.models import Curso, Docente

class ImportViewsTestCase(TestCase):
    def setUp(self):
        self.client = Client()

    def generate_excel_file(self, data):
        output = io.BytesIO()
        df = pd.DataFrame(data)
        # Usamos openpyxl como engine para escribir el archivo Excel
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        output.seek(0)
        return output.getvalue()

    def test_importar_estadisticas_carga_success(self):
        """Prueba la importación exitosa de estadísticas de carga (HU-04)."""
        url = reverse('import-load-stats')
        data = {
            "Materia": ["CUR001", "CUR002"],
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
        self.assertEqual(json_data['cursos_creados'], 2)
        self.assertEqual(json_data['docentes_creados'], 2)
        self.assertEqual(json_data['cursos_actualizados'], 0)
        
        # Verificar en base de datos
        self.assertEqual(Curso.objects.count(), 2)
        self.assertEqual(Docente.objects.count(), 2)
        
        curso = Curso.objects.get(codigo="CUR001")
        self.assertEqual(curso.nombre, "Matematicas I")
        self.assertEqual(curso.docente.nombre, "Juan Perez")
        self.assertEqual(curso.num_matriculados, 30)

    def test_importar_estadisticas_carga_update(self):
        """Prueba la actualización de cursos existentes (HU-04)."""
        # Crear datos iniciales
        docente = Docente.objects.create(
            codigo="DOC100", 
            nombre="Docente Original", 
            tipo_vinculacion="DOCENTE CATEDRA"
        )
        Curso.objects.create(
            codigo="CUR100", 
            nombre="Nombre Original", 
            docente=docente,
            num_matriculados=10
        )
        
        url = reverse('import-load-stats')
        data = {
            "Materia": ["CUR100"],
            "Nombre": ["Nombre Actualizado"],
            "Horario": ["Viernes 14-16"],
            "# Matriculados": [20],
            "Código Docente": ["DOC100"],
            "Nombre Docente": ["Docente Original"]
        }
        excel_content = self.generate_excel_file(data)
        excel_file = SimpleUploadedFile(
            "update.xlsx", 
            excel_content, 
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        response = self.client.post(url, {'file': excel_file})
        
        self.assertEqual(response.status_code, 200)
        json_data = response.json()
        self.assertEqual(json_data['cursos_actualizados'], 1)
        self.assertEqual(json_data['cursos_creados'], 0)
        
        # Verificar actualización
        curso = Curso.objects.get(codigo="CUR100")
        self.assertEqual(curso.nombre, "Nombre Actualizado")
        self.assertEqual(curso.num_matriculados, 20)
        self.assertEqual(curso.horario, "Viernes 14-16")

    def test_importar_estadisticas_carga_no_file(self):
        """Prueba el error cuando no se envía archivo."""
        url = reverse('import-load-stats')
        response = self.client.post(url)
        self.assertEqual(response.status_code, 400)
        self.assertIn("No se envió archivo", response.json()['error'])

    def test_placeholder_views(self):
        """Verifica que las vistas pendientes (HU-01, HU-02, HU-03) retornen el template."""
        placeholders = [
            'import-students-dirplan',
            'import-history-individual',
            'import-academic-offering'
        ]
        for name in placeholders:
            url = reverse(name)
            # Estas vistas actualmente aceptan GET y retornan el mensaje de template
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['status'], 'template')
            self.assertIn("pendiente de implementación", response.json()['message'])
