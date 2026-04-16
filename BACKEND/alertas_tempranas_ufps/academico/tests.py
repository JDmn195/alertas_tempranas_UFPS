from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from .models import Estudiante
import io
import pandas as pd

class ImportEstudiantesTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse('import-students-dirplan')

    def test_importar_estudiantes_full_mapping_csv(self):
        # Archivo CSV con el formato exacto del usuario
        csv_content = (
            "Codigo,Nombre Alumno,Tipo Doc,Documento,Semestre,Pensum,Ingreso,Promedio,Estado Matricula,Celular,Email,Email Institucional,Colegio Egresado,Municipio Nacimiento\n"
            "1150001,Juan Perez,CC,123456,3,115,2026-1,4.5,MATRICULADO,3001234567,juan@gmail.com,juan@ufps.edu.co,Colegio Central,Cucuta\n"
        )
        file = SimpleUploadedFile("test.csv", csv_content.encode('utf-8'), content_type="text/csv")
        
        response = self.client.post(self.url, {'file': file})
        
        # Verificar respuesta JSON
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        
        # Verificar que existen en la DB con todos los datos
        est = Estudiante.objects.get(codigo='1150001')
        self.assertEqual(est.nombre, 'Juan Perez')
        self.assertEqual(est.tipo_documento, 'CC')
        self.assertEqual(est.anio_ingreso, 2026)
        self.assertEqual(est.semestre_ingreso, 1)
        self.assertEqual(est.celular, '3001234567')
        self.assertEqual(est.email_institucional, 'juan@ufps.edu.co')
        
        # VERIFICAR USUARIO CREADO
        self.assertIsNotNone(est.usuario)
        self.assertEqual(est.usuario.correo, 'juan@ufps.edu.co')
        self.assertEqual(est.usuario.rol, 'ESTUDIANTE')

    def test_importar_archivo_invalido(self):
        # Archivo que no es de DIRPLAN (le faltan columnas clave)
        csv_content = "Columna1,Columna2\nValor1,Valor2\n"
        file = SimpleUploadedFile("incorrecto.csv", csv_content.encode('utf-8'), content_type="text/csv")
        
        response = self.client.post(self.url, {'file': file})
        
        self.assertEqual(response.status_code, 400)
        self.assertIn("no parece ser un reporte de DIRPLAN válido", response.json()['error'])
