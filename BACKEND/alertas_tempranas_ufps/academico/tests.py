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


from django.utils import timezone
from datetime import timedelta
from alertas.models import Alerta, Regla, Intervencion

class StudentInterventionsTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        # Create student
        self.estudiante = Estudiante.objects.create(
            codigo="1150003",
            nombre="Pedro Perez",
            tipo_documento="CC",
            numero_documento="123456",
            semestre=3,
            promedio=3.5,
            estado_matricula="Matriculado"
        )
        
        # Create coordinator/user
        self.coordinador = Usuario.objects.create(
            nombre="Coordinador Academico",
            correo="coordinador@ufps.edu.co",
            rol="DIRECTOR",
            contrasena="123456"
        )
        
        # Create rule and alert
        self.regla = Regla.objects.create(
            nombre="Promedio Bajo",
            tipo="PROMEDIO",
            valor_umbral=3.0,
            operador="<",
            nivel="medium",
            activo=True
        )
        
        self.alerta = Alerta.objects.create(
            estudiante=self.estudiante,
            regla=self.regla,
            estado="activa",
            valor_causa=2.8
        )

    def test_get_interventions_empty(self):
        """Escenario 2: Estudiante sin intervenciones registradas."""
        url = reverse('student-interventions', kwargs={'codigo': self.estudiante.codigo})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['codigo'], self.estudiante.codigo)
        self.assertEqual(data['intervenciones'], [])

    def test_get_interventions_sorted_desc(self):
        """Escenario 1: Consulta exitosa del historial, ordenadas por fecha descendente."""
        i1 = Intervencion.objects.create(
            alerta=self.alerta,
            usuario=self.coordinador,
            tipo="TUTORIA",
            observaciones="Primera intervencion",
        )
        i2 = Intervencion.objects.create(
            alerta=self.alerta,
            usuario=self.coordinador,
            tipo="CITACION",
            observaciones="Segunda intervencion",
        )
        
        # Modificar fechas manualmente para verificar el orden descendente
        i1.fecha = timezone.now() - timedelta(days=2)
        i1.save()
        
        i2.fecha = timezone.now() - timedelta(days=1)
        i2.save()

        url = reverse('student-interventions', kwargs={'codigo': self.estudiante.codigo})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        intervenciones = data['intervenciones']
        self.assertEqual(len(intervenciones), 2)
        
        # i2 (más reciente) debe estar primero, i1 después
        self.assertEqual(intervenciones[0]['id'], i2.id)
        self.assertEqual(intervenciones[0]['tipo'], "Tutoría" if i2.tipo == 'TUTORIA' else "Citación")
        self.assertEqual(intervenciones[0]['tipo_raw'], "CITACION")
        self.assertEqual(intervenciones[0]['observaciones'], "Segunda intervencion")
        self.assertEqual(intervenciones[0]['usuario'], self.coordinador.nombre)
        self.assertEqual(intervenciones[0]['alerta_causa'], self.regla.nombre)

        self.assertEqual(intervenciones[1]['id'], i1.id)
        self.assertEqual(intervenciones[1]['tipo_raw'], "TUTORIA")
        self.assertEqual(intervenciones[1]['observaciones'], "Primera intervencion")

