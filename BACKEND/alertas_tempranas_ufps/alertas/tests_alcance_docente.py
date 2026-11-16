"""SDAT-338 (B13): alcance del DOCENTE y reevaluación solo para ADMINISTRADOR."""
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from academico.models import Curso, Docente, Estudiante, Materia, Nota, Periodo
from alertas.models import Alerta, Intervencion, Regla
from alertas.services import NotificationService
from usuarios.models import Auditoria, Usuario
from usuarios.tests_cuentas_estudiante import _auth


class AlcanceDocenteTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.doc = Usuario.objects.create(nombre='Doc', correo='doc338@ufps.edu.co', rol='DOCENTE', contrasena='!')
        cls.otro_doc = Usuario.objects.create(nombre='Otro', correo='otro338@ufps.edu.co', rol='DOCENTE',
                                              contrasena='!')
        cls.bienestar = Usuario.objects.create(nombre='Bien', correo='bien338@ufps.edu.co', rol='BIENESTAR',
                                               contrasena='!')
        cls.admin = Usuario.objects.create(nombre='Adm', correo='adm338@ufps.edu.co', rol='ADMINISTRADOR',
                                           contrasena='!')
        cls.director = Usuario.objects.create(nombre='Dir', correo='dir338@ufps.edu.co', rol='DIRECTOR',
                                              contrasena='!')
        d1 = Docente.objects.create(codigo='D3381', nombre='Doc', tipo_vinculacion='Planta', usuario=cls.doc)
        d2 = Docente.objects.create(codigo='D3382', nombre='Otro', tipo_vinculacion='Planta', usuario=cls.otro_doc)
        periodo = Periodo.objects.create(anio=2026, semestre=2)
        cls.curso1 = Curso.objects.create(materia=Materia.objects.create(codigo='338001', nombre='Propia',
                                          creditos=3, semestre=1), grupo='A', docente=d1)
        cls.curso2 = Curso.objects.create(materia=Materia.objects.create(codigo='338002', nombre='Ajena',
                                          creditos=3, semestre=1), grupo='A', docente=d2)
        cls.est = Estudiante.objects.create(codigo='E3381', nombre='Ana', tipo_documento='CC',
                                            numero_documento='999888', celular='3000000000',
                                            email_personal='ana@gmail.com', email_institucional='ana@ufps.edu.co',
                                            semestre=2, estado_matricula='ACTIVO')
        Nota.objects.create(estudiante=cls.est, curso=cls.curso1, periodo=periodo, definitiva=3.5)
        Nota.objects.create(estudiante=cls.est, curso=cls.curso2, periodo=periodo, definitiva=2.0)
        regla = Regla.objects.create(nombre='R', tipo='PROMEDIO', operador='<', valor_umbral=3, nivel='medium')
        cls.alerta = Alerta.objects.create(estudiante=cls.est, regla=regla, estado='en_seguimiento')
        cls.propia = Intervencion.objects.create(alerta=cls.alerta, usuario=cls.doc, tipo='TUTORIA',
                                                 observaciones='obs del docente')
        cls.de_bienestar = Intervencion.objects.create(alerta=cls.alerta, usuario=cls.bienestar, tipo='CITACION',
                                                       observaciones='obs reservada de Bienestar')

    def get(self, nombre, usuario, *args, **params):
        return self.client.get(reverse(nombre, args=args), params, **_auth(usuario))

    def test_docente_no_recibe_datos_personales_sensibles(self):
        datos = self.get('detail-student', self.doc, 'E3381').json()
        for campo in ('numero_documento', 'celular', 'email_personal'):
            self.assertIsNone(datos[campo], campo)
        self.assertEqual(datos['nombre'], 'Ana')

    def test_otros_roles_siguen_viendo_los_datos_personales(self):
        datos = self.get('detail-student', self.director, 'E3381').json()
        self.assertEqual(datos['numero_documento'], '999888')
        self.assertEqual(datos['celular'], '3000000000')

    def test_docente_solo_ve_las_notas_de_sus_cursos(self):
        historial = self.get('student-history', self.doc, 'E3381').json()['historial']
        materias = [m['materia'] for p in historial for m in p['materias']]
        self.assertEqual(materias, ['Propia'])

    def test_docente_solo_ve_sus_intervenciones_por_estudiante(self):
        textos = [i['observaciones'] for i in
                  self.get('student-interventions', self.doc, 'E3381').json()['intervenciones']]
        self.assertEqual(textos, ['obs del docente'])
        total = self.get('student-interventions', self.bienestar, 'E3381').json()['intervenciones']
        self.assertEqual(len(total), 2)

    def test_docente_solo_ve_sus_intervenciones_por_alerta(self):
        textos = [i['observaciones'] for i in
                  self.get('listar-intervenciones', self.doc, self.alerta.id).json()['intervenciones']]
        self.assertEqual(textos, ['obs del docente'])

    def test_docente_no_abre_anotaciones_de_intervencion_ajena_y_queda_auditado(self):
        antes = Auditoria.objects.filter(tipo_accion='ACCESO_DENEGADO').count()
        r = self.get('gestionar-anotaciones', self.doc, self.de_bienestar.id)
        self.assertEqual(r.status_code, 403)
        self.assertEqual(Auditoria.objects.filter(tipo_accion='ACCESO_DENEGADO').count(), antes + 1)
        self.assertEqual(self.get('gestionar-anotaciones', self.doc, self.propia.id).status_code, 200)

    def test_docente_no_lista_evidencias_de_intervencion_ajena(self):
        self.assertEqual(self.get('listar-evidencias', self.doc, self.de_bienestar.id).status_code, 403)

    def test_reporte_de_intervenciones_del_docente_omite_las_ajenas(self):
        filas = self.get('export-report-data', self.doc, tipo='seguimiento-intervenciones').json()['data']
        self.assertEqual([f['notes'] for f in filas], ['obs del docente'])
        todas = self.get('export-report-data', self.director, tipo='seguimiento-intervenciones').json()['data']
        self.assertEqual(len(todas), 2)


class ReevaluacionSoloAdministradorTests(TestCase):
    def setUp(self):
        patcher = mock.patch.object(NotificationService, 'notificar_alerta')
        patcher.start()
        self.addCleanup(patcher.stop)

    def post(self, rol):
        usuario = Usuario.objects.create(nombre=rol, correo=f'{rol.lower()}338r@ufps.edu.co', rol=rol,
                                         contrasena='!')
        return usuario, self.client.post(reverse('reevaluar-alertas'), **_auth(usuario))

    def test_roles_distintos_de_administrador_reciben_403_y_auditoria(self):
        for rol in ('DOCENTE', 'BIENESTAR', 'DIRECTOR', 'ESTUDIANTE'):
            with self.subTest(rol=rol):
                usuario, r = self.post(rol)
                self.assertEqual(r.status_code, 403)
                self.assertTrue(Auditoria.objects.filter(usuario=usuario, tipo_accion='ACCESO_DENEGADO').exists())

    def test_administrador_puede_reevaluar(self):
        _, r = self.post('ADMINISTRADOR')
        self.assertEqual(r.status_code, 200)
