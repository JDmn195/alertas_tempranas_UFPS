"""
Casos de referencia de las reglas de riesgo académico.

Cada caso es un estudiante ficticio con su resultado esperado calculado a mano,
antes de ejecutar el sistema. La explicación de cada cálculo está en
docs/Casos_Referencia_Riesgo.md. Si un caso deja de coincidir, primero se revisa
con el equipo: las reglas son decisiones acordadas, no se ajusta el esperado.

Reglas generales de referencia: las que carga el comando reset_reglas.
Reglas de corte e inasistencia: las que crean las migraciones 0016 y 0018.
"""
from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase

from academico.asistencia import calcular_inasistencia, supera_umbral
from academico.models import Asistencia, Curso, Docente, EquivalenciaMateria, Estudiante, Materia, Nota, Periodo
from academico.views.import_views import calcular_definitiva
from alertas.alertas_corte import calcular_nota_necesaria, evaluar_cortes_nota
from alertas.alertas_inasistencia import obtener_regla_inasistencia, supera_umbral_regla
from alertas.evaluacion import calcular_indicadores, nivel_de_riesgo
from alertas.models import Alerta, Regla, alertas_abiertas
from usuarios.models import Usuario

# (nombre, tipo, operador, umbral, nivel): las mismas de reset_reglas
REGLAS_GENERALES = [
    ('Promedio Crítico', 'PROMEDIO', '<', 2.5, 'high'),
    ('Promedio Bajo', 'PROMEDIO', '<', 3.0, 'medium'),
    ('Promedio En Riesgo', 'PROMEDIO', '<', 3.5, 'low'),
    ('Múltiples Reprobadas Crítico', 'REPROBACION', '>=', 4, 'high'),
    ('Reprobadas Moderado', 'REPROBACION', '>=', 2, 'medium'),
    ('Una Reprobada', 'REPROBACION', '>=', 1, 'low'),
    ('Atraso Severo', 'ATRASO', '>=', 3, 'high'),
    ('Atraso Moderado', 'ATRASO', '>=', 2, 'medium'),
    ('Atraso Leve', 'ATRASO', '>=', 1, 'low'),
]

# Pensum de referencia: código -> (semestre, tipo). Todas de 3 créditos.
PENSUM = {
    'L11': (1, 'linea'), 'L12': (1, 'linea'), 'L21': (2, 'linea'), 'L22': (2, 'linea'), 'L31': (3, 'linea'),
    'P11': (1, 'profesional'),  # no es de línea: no cuenta para el atraso
    'E11': (None, 'profesional'),  # equivale a L11
}

# Estudiantes de tercer semestre. notas: (materia, periodo, definitiva).
# Esperado: PPA, materias reprobadas pendientes, atraso, nivel y reglas que aplican.
CASOS_RIESGO = [
    dict(id='R01', descripcion='Buen rendimiento',
         notas=[('L11', 1, 4.0), ('L12', 1, 4.0), ('L21', 2, 4.0), ('L22', 2, 4.0)],
         ppa=4.0, reprobadas=0, atraso=0, nivel='low', reglas=[]),
    dict(id='R02', descripcion='Promedio 3.40: por debajo de 3.5',
         notas=[('L11', 1, 3.4), ('L12', 1, 3.4), ('L21', 2, 3.4), ('L22', 2, 3.4)],
         ppa=3.4, reprobadas=0, atraso=0, nivel='low', reglas=['Promedio En Riesgo']),
    dict(id='R03', descripcion='Límite: promedio exactamente 3.50 no dispara la regla',
         notas=[('L11', 1, 3.5), ('L12', 1, 3.5), ('L21', 2, 3.5), ('L22', 2, 3.5)],
         ppa=3.5, reprobadas=0, atraso=0, nivel='low', reglas=[]),
    dict(id='R04', descripcion='Promedio 2.95 con una materia de línea perdida',
         notas=[('L11', 1, 3.0), ('L12', 1, 3.0), ('L21', 2, 2.8), ('L22', 2, 3.0)],
         ppa=2.95, reprobadas=1, atraso=1, nivel='medium',
         reglas=['Promedio Bajo', 'Promedio En Riesgo', 'Una Reprobada', 'Atraso Leve']),
    dict(id='R05', descripcion='Promedio 2.45, tres perdidas y tres materias de línea atrasadas',
         notas=[('L11', 1, 2.0), ('L12', 1, 2.0), ('L21', 2, 3.0), ('L22', 2, 2.8)],
         ppa=2.45, reprobadas=3, atraso=3, nivel='high',
         reglas=['Promedio Crítico', 'Promedio Bajo', 'Promedio En Riesgo', 'Reprobadas Moderado',
                 'Una Reprobada', 'Atraso Severo', 'Atraso Moderado', 'Atraso Leve']),
    dict(id='R06', descripcion='Sin historial y sin promedio: no hay datos',
         notas=[], ppa=None, reprobadas=None, atraso=None, nivel='unknown', reglas=[]),
    dict(id='R07', descripcion='Sin historial, con promedio importado 2.40',
         promedio_importado=2.4, notas=[], ppa=2.4, reprobadas=None, atraso=None, nivel='high',
         reglas=['Promedio Crítico', 'Promedio Bajo', 'Promedio En Riesgo']),
    dict(id='R08', descripcion='Perdió L11 y la recuperó: ya no está pendiente',
         notas=[('L11', 1, 2.0), ('L11', 2, 3.5), ('L12', 1, 4.0), ('L21', 2, 4.0), ('L22', 2, 4.0)],
         ppa=3.5, reprobadas=0, atraso=0, nivel='low', reglas=[]),
    dict(id='R09', descripcion='No ha cursado las dos materias de línea de segundo semestre',
         notas=[('L11', 1, 4.0), ('L12', 1, 4.0)],
         ppa=4.0, reprobadas=0, atraso=2, nivel='medium', reglas=['Atraso Moderado', 'Atraso Leve']),
    dict(id='R10', descripcion='Una materia que no es de línea sin cursar no cuenta como atraso',
         notas=[('L11', 1, 4.0), ('L12', 1, 4.0), ('L21', 2, 4.0), ('L22', 2, 4.0)],
         ppa=4.0, reprobadas=0, atraso=0, nivel='low', reglas=[]),
    dict(id='R11', descripcion='Materia en curso sin definitiva: ni suma al promedio ni cuenta como perdida',
         notas=[('L11', 1, 4.0), ('L12', 1, 4.0), ('L21', 2, 4.0), ('L22', 2, 4.0), ('L31', 3, None)],
         ppa=4.0, reprobadas=0, atraso=0, nivel='low', reglas=[]),
    dict(id='R12', descripcion='Perdió L11 y aprobó su equivalente E11',
         notas=[('L11', 1, 2.0), ('E11', 2, 4.0), ('L12', 1, 4.0), ('L21', 2, 4.0), ('L22', 2, 4.0)],
         ppa=3.6, reprobadas=0, atraso=0, nivel='low', reglas=[]),
    dict(id='R13', descripcion='Cuatro materias perdidas con promedio 2.90',
         notas=[('L11', 1, 2.9), ('L12', 1, 2.9), ('L21', 2, 2.9), ('L22', 2, 2.9)],
         ppa=2.9, reprobadas=4, atraso=4, nivel='high',
         reglas=['Promedio Bajo', 'Promedio En Riesgo', 'Múltiples Reprobadas Crítico', 'Reprobadas Moderado',
                 'Una Reprobada', 'Atraso Severo', 'Atraso Moderado', 'Atraso Leve']),
    dict(id='R14', descripcion='Buen promedio (3.70) con dos perdidas: el riesgo no depende solo del promedio',
         notas=[('L11', 1, 2.9), ('L12', 1, 2.9), ('L21', 2, 4.5), ('L22', 2, 4.5)],
         ppa=3.7, reprobadas=2, atraso=2, nivel='medium',
         reglas=['Reprobadas Moderado', 'Una Reprobada', 'Atraso Moderado', 'Atraso Leve']),
]

# Definitiva = promedio de cortes x 0.7 + examen x 0.3, redondeo a 1 decimal (mitad hacia arriba)
CASOS_DEFINITIVA = [
    # corte 1, corte 2, corte 3, examen, definitiva
    (3.0, 3.0, 3.0, 3.0, 3.0),
    (4.0, 3.5, 3.0, 2.0, 3.1),  # 2.45 + 0.60 = 3.05 -> 3.1
    (2.0, 2.5, 3.0, 4.0, 3.0),  # 1.75 + 1.20 = 2.95 -> 3.0: aprueba por redondeo
    (1.0, 2.0, 3.0, 5.0, 2.9),  # 1.40 + 1.50 = 2.90: pierde con 5.0 en el examen
    (3.3, 3.3, 3.4, 2.2, 3.0),  # 2.3333 + 0.66 = 2.9933 -> 3.0
    (5.0, 5.0, 5.0, 5.0, 5.0),
    (0.0, 0.0, 0.0, 0.0, 0.0),
]

# Nota necesaria en el examen = (3.0 - promedio de cortes x 0.7) / 0.3, a 2 decimales
CASOS_NOTA_NECESARIA = [
    (3.0, 3.0, 3.0, '3.00'),
    (1.5, 2.0, 2.5, '5.33'),   # imposible: materia perdida (C4)
    (2.0, 2.2, 2.2, '5.02'),   # apenas por encima de 5.0 (C4)
    (2.0, 2.0, 2.5, '4.94'),   # apenas por debajo de 5.0 (C3)
    (2.5, 2.6, 2.6, '4.01'),   # apenas por encima de 4.0 (C3)
    (2.6, 2.6, 2.6, '3.93'),   # apenas por debajo de 4.0: sin alerta de examen
    (5.0, 5.0, 5.0, '-1.67'),  # ya aprobó
]

# Cortes registrados en el periodo más reciente -> claves de las alertas que deben quedar abiertas
CASOS_CORTE = [
    dict(id='C01', cortes=(1.9, None, None), alertas={'C1'}),
    dict(id='C02', cortes=(2.0, None, None), alertas=set()),          # límite: 2.0 no es menor que 2.0
    dict(id='C03', cortes=(2.5, 2.9, None), alertas={'C2A'}),         # dos cortes perdidos
    dict(id='C04', cortes=(3.0, 2.9, None), alertas={'C2B'}),         # caída de rendimiento
    dict(id='C05', cortes=(3.0, 3.0, None), alertas=set()),           # límite: 3.0 aprueba
    dict(id='C06', cortes=(1.5, 2.0, None), alertas={'C1', 'C2A'}),
    dict(id='C07', cortes=(1.5, 2.0, 2.5), alertas={'C1', 'C2A', 'C4'}),  # necesita 5.33
    dict(id='C08', cortes=(2.0, 2.5, 2.5), alertas={'C2A', 'C3'}),    # necesita 4.56; C4 no aplica
    dict(id='C09', cortes=(2.6, 2.6, 2.6), alertas={'C2A'}),          # necesita 3.93: sin alerta de examen
    dict(id='C10', cortes=(3.5, 3.5, 3.5), alertas=set()),
    dict(id='C11', cortes=(1.5, 2.0, 2.5), examen=5.0, alertas={'C1', 'C2A'}),  # con examen ya no hay C3/C4
]

# Asistencias (A), faltas (F) y faltas justificadas (J) -> porcentaje y si supera el umbral del 20 %
CASOS_INASISTENCIA = [
    dict(id='I01', a=7, f=2, j=1, porcentaje='20.00', supera=False),  # límite: 20 % no supera 20 %
    dict(id='I02', a=11, f=3, j=0, porcentaje='21.43', supera=True),
    dict(id='I03', a=0, f=0, j=0, porcentaje=None, supera=None),      # sin clases no hay dato
    dict(id='I04', a=2, f=1, j=0, porcentaje='33.33', supera=None),   # 3 clases: menos del mínimo (4)
    dict(id='I05', a=2, f=0, j=2, porcentaje='0.00', supera=False),   # las justificadas no son faltas
    dict(id='I06', a=3, f=1, j=0, porcentaje='25.00', supera=True),   # justo el mínimo de clases
]


class CasosReferenciaBase(TestCase):

    def setUp(self):
        usuario = Usuario.objects.create(nombre='Doc', correo='doc@ufps.edu.co', rol='DOCENTE', contrasena='x')
        docente = Docente.objects.create(codigo='D1', nombre='Doc', tipo_vinculacion='Planta', usuario=usuario)
        self.periodos = {n: Periodo.objects.create(anio=2025 + (n - 1) // 2, semestre=2 - n % 2) for n in (1, 2, 3)}
        self.cursos = {
            codigo: Curso.objects.create(
                materia=Materia.objects.create(codigo=codigo, nombre=f'Materia {codigo}', creditos=3,
                                               semestre=semestre, tipo=tipo),
                grupo='A', docente=docente,
            )
            for codigo, (semestre, tipo) in PENSUM.items()
        }
        EquivalenciaMateria.objects.create(materia_pensum_id='L11', materia_equivalente_id='E11')

    def _estudiante(self, codigo, promedio=None):
        return Estudiante.objects.create(
            codigo=codigo, nombre=f'Estudiante {codigo}', tipo_documento='CC', numero_documento=codigo, semestre=3,
            promedio=Decimal(str(promedio)) if promedio is not None else None,
        )

    def _nota(self, estudiante, materia, periodo, definitiva=None, **cortes):
        return Nota.objects.create(
            estudiante=estudiante, curso=self.cursos[materia], periodo=self.periodos[periodo],
            definitiva=Decimal(str(definitiva)) if definitiva is not None else None,
            **{campo: Decimal(str(valor)) for campo, valor in cortes.items() if valor is not None},
        )


class RiesgoGeneralTests(CasosReferenciaBase):

    def setUp(self):
        super().setUp()
        self.reglas = [
            Regla.objects.create(nombre=nombre, tipo=tipo, operador=operador, valor_umbral=Decimal(str(umbral)),
                                 nivel=nivel, prioridad=10)
            for nombre, tipo, operador, umbral, nivel in REGLAS_GENERALES
        ]

    def _evaluar(self, estudiante):
        indicadores = calcular_indicadores(estudiante)
        nivel, aplicadas = nivel_de_riesgo(self.reglas, indicadores)
        return indicadores, nivel, [regla['nombre'] for regla in aplicadas]

    def test_casos_de_referencia(self):
        for caso in CASOS_RIESGO:
            with self.subTest(caso=caso['id'], descripcion=caso['descripcion']):
                estudiante = self._estudiante(caso['id'], caso.get('promedio_importado'))
                for materia, periodo, definitiva in caso['notas']:
                    self._nota(estudiante, materia, periodo, definitiva)

                indicadores, nivel, reglas = self._evaluar(estudiante)

                self.assertEqual(indicadores['ppa'], caso['ppa'])
                self.assertEqual(indicadores['reprobadas'], caso['reprobadas'])
                self.assertEqual(indicadores['atraso'], caso['atraso'])
                self.assertEqual(nivel, caso['nivel'])
                self.assertEqual(reglas, caso['reglas'])

    def test_el_riesgo_cambia_cuando_cambian_las_notas(self):
        """R04 recupera la materia perdida: (3.0 + 3.0 + 2.8 + 3.0 + 3.5) / 5 = 3.06, sin pendientes."""
        estudiante = self._estudiante('R15')
        for materia, periodo, definitiva in CASOS_RIESGO[3]['notas']:
            self._nota(estudiante, materia, periodo, definitiva)
        self.assertEqual(self._evaluar(estudiante)[1], 'medium')

        self._nota(estudiante, 'L21', 3, 3.5)

        indicadores, nivel, reglas = self._evaluar(estudiante)
        self.assertEqual((indicadores['ppa'], indicadores['reprobadas'], indicadores['atraso']), (3.06, 0, 0))
        self.assertEqual((nivel, reglas), ('low', ['Promedio En Riesgo']))


class FormulasTests(TestCase):

    def test_definitiva(self):
        for c1, c2, c3, examen, esperada in CASOS_DEFINITIVA:
            with self.subTest(cortes=(c1, c2, c3), examen=examen):
                self.assertEqual(calcular_definitiva(c1, c2, c3, examen), esperada)

    def test_nota_necesaria_en_el_examen(self):
        for c1, c2, c3, esperada in CASOS_NOTA_NECESARIA:
            with self.subTest(cortes=(c1, c2, c3)):
                self.assertEqual(calcular_nota_necesaria(c1, c2, c3), Decimal(esperada))


class AlertasDeCorteTests(CasosReferenciaBase):

    def _claves_abiertas(self, estudiante):
        return {
            alerta.regla.parametros['clave']
            for alerta in alertas_abiertas(Alerta.objects.filter(estudiante=estudiante, regla__tipo='CORTE'))
        }

    def test_casos_de_referencia(self):
        for caso in CASOS_CORTE:
            with self.subTest(caso=caso['id'], cortes=caso['cortes']):
                estudiante = self._estudiante(caso['id'])
                c1, c2, c3 = caso['cortes']
                nota = self._nota(estudiante, 'L31', 3, corte1=c1, corte2=c2, corte3=c3,
                                  examen_final=caso.get('examen'))
                evaluar_cortes_nota(nota)
                self.assertEqual(self._claves_abiertas(estudiante), caso['alertas'])

    def test_no_se_duplica_y_se_cierra_sola_al_mejorar_la_nota(self):
        estudiante = self._estudiante('C12')
        nota = self._nota(estudiante, 'L31', 3, corte1=1.9)
        evaluar_cortes_nota(nota)
        evaluar_cortes_nota(nota)
        self.assertEqual(Alerta.objects.filter(estudiante=estudiante).count(), 1)

        nota.corte1 = Decimal('3.0')
        nota.save()
        evaluar_cortes_nota(nota)

        alerta = Alerta.objects.get(estudiante=estudiante)
        self.assertEqual(self._claves_abiertas(estudiante), set())
        self.assertTrue(alerta.metadata['cierre_automatico'])
        self.assertTrue(alerta.metadata['motivo_cierre'])


class InasistenciaTests(CasosReferenciaBase):

    def test_casos_de_referencia(self):
        regla = obtener_regla_inasistencia()
        self.assertEqual((regla.valor_umbral, regla.parametros['min_clases']), (Decimal('20'), 4))
        for caso in CASOS_INASISTENCIA:
            with self.subTest(caso=caso['id']):
                estudiante = self._estudiante(caso['id'])
                estados = ['ASISTIO'] * caso['a'] + ['FALTA'] * caso['f'] + ['FALTA_JUSTIFICADA'] * caso['j']
                for dia, estado in enumerate(estados):
                    Asistencia.objects.create(
                        estudiante=estudiante, curso=self.cursos['L31'], periodo=self.periodos[3],
                        fecha_clase=date(2026, 2, 2) + timedelta(days=dia), estado=estado,
                    )

                resultado = calcular_inasistencia(estudiante, self.cursos['L31'], self.periodos[3])

                esperado = Decimal(caso['porcentaje']) if caso['porcentaje'] is not None else None
                self.assertEqual(resultado['porcentaje'], esperado)
                self.assertEqual(supera_umbral_regla(regla, resultado, regla.valor_umbral), caso['supera'])

    def test_el_limite_exacto_no_supera_el_umbral(self):
        self.assertFalse(supera_umbral(Decimal('20.00'), Decimal('20')))
        self.assertTrue(supera_umbral(Decimal('20.01'), Decimal('20')))
