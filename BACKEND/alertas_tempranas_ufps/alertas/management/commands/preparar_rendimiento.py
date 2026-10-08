"""
Base con volumen realista para las pruebas de rendimiento (pruebas_rendimiento/).

Solo corre con E2E=True (base aislada, sin el .env). Genera una carrera completa
con datos deterministas (semilla fija) y mide cuánto tardan los procesos por lotes
que en producción corren sobre toda la población:

  - re-evaluación completa del riesgo (HU-29, la ejecución nocturna)
  - alertas por corte del periodo actual (HU-32)
  - alertas por inasistencia del periodo actual (HU-36)

    E2E=True E2E_DATABASE_URL=postgres://postgres:postgres@localhost:5433/sat \\
        python manage.py preparar_rendimiento --estudiantes 2000
"""
import io
import json
import random
import time
from datetime import date, timedelta
from decimal import Decimal

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connection

from ._entorno_pruebas import crear_usuario, recrear_base

SEMILLA = 2026
SEMESTRES = 10
MATERIAS_POR_SEMESTRE = 5
GRUPOS = ('A', 'B')
DOCENTES = 40
# Periodos cursados antes del actual, del más antiguo al más reciente
PERIODOS_ANTERIORES = [(2023, 1), (2023, 2), (2024, 1), (2024, 2), (2025, 1), (2025, 2), (2026, 1)]
PERIODO_ACTUAL = (2026, 2)
# Clases semanales ya dictadas en el periodo actual
PRIMERA_CLASE = date(2026, 8, 4)
CLASES = 9


def _nota(rng, media):
    return Decimal(str(round(min(5.0, max(0.0, rng.gauss(media, 0.7))), 1)))


class Command(BaseCommand):
    help = 'Recrea la base de pruebas con volumen realista y mide los procesos por lotes (solo con E2E=True).'

    def add_arguments(self, parser):
        parser.add_argument('--estudiantes', type=int, default=2000)
        parser.add_argument('--salida', help='Archivo JSON donde guardar los tiempos medidos.')

    def handle(self, *args, **options):
        inicio = time.perf_counter()
        recrear_base()
        # Las 9 reglas generales de referencia (PROMEDIO, REPROBACION, ATRASO)
        call_command('reset_reglas', stdout=io.StringIO())
        conteos = self._generar(options['estudiantes'])
        conteos['segundos_generacion'] = round(time.perf_counter() - inicio, 1)
        self.stdout.write(
            f"Generados en {conteos['segundos_generacion']} s: {conteos['estudiantes']} estudiantes, "
            f"{conteos['notas']} notas, {conteos['asistencias']} registros de asistencia."
        )

        tiempos = self._medir_procesos(conteos['estudiantes'])
        resultado = {'motor': connection.vendor, 'volumen': conteos, 'procesos': tiempos}
        if options['salida']:
            with open(options['salida'], 'w', encoding='utf-8') as f:
                json.dump(resultado, f, indent=2, ensure_ascii=False)
        self.stdout.write(self.style.SUCCESS('Base de rendimiento lista.'))

    # ------------------------------------------------------------------

    def _generar(self, total_estudiantes):
        from academico.models import Asistencia, Curso, Docente, Estudiante, Materia, Nota, Periodo

        rng = random.Random(SEMILLA)

        crear_usuario('Admin Rendimiento', 'admin@ufps.edu.co', 'ADMINISTRADOR')
        crear_usuario('Director Rendimiento', 'director@ufps.edu.co', 'DIRECTOR')
        for i in (1, 2):
            crear_usuario(f'Bienestar {i}', f'bienestar{i}@ufps.edu.co', 'BIENESTAR')
        docentes = [
            Docente.objects.create(
                codigo=f'D{i:03d}', nombre=f'Docente {i:02d}', tipo_vinculacion='Planta',
                usuario=crear_usuario(f'Docente {i:02d}', f'docente{i:02d}@ufps.edu.co', 'DOCENTE'),
            )
            for i in range(1, DOCENTES + 1)
        ]

        materias = {}  # semestre -> [Materia]
        for s in range(1, SEMESTRES + 1):
            materias[s] = Materia.objects.bulk_create([
                Materia(codigo=f'115{s:02d}{m:02d}', nombre=f'Materia {s}.{m}', creditos=3, semestre=s)
                for m in range(1, MATERIAS_POR_SEMESTRE + 1)
            ])
        cursos = {}  # (codigo_materia, grupo) -> Curso
        i = 0
        for lista in materias.values():
            for materia in lista:
                for grupo in GRUPOS:
                    cursos[(materia.codigo, grupo)] = Curso(materia=materia, grupo=grupo, docente=docentes[i % DOCENTES])
                    i += 1
        Curso.objects.bulk_create(cursos.values())
        cursos = {(c.materia_id, c.grupo): c for c in Curso.objects.all()}

        anteriores = [Periodo.objects.create(anio=a, semestre=s) for a, s in PERIODOS_ANTERIORES]
        actual = Periodo.objects.create(anio=PERIODO_ACTUAL[0], semestre=PERIODO_ACTUAL[1])
        fechas = [PRIMERA_CLASE + timedelta(weeks=k) for k in range(CLASES)]

        estudiantes, notas, asistencias = [], [], []
        for n in range(total_estudiantes):
            semestre = n % SEMESTRES + 1
            est = Estudiante(
                codigo=f'1{semestre:02d}{n:05d}', nombre=f'Estudiante {n:05d}', tipo_documento='CC',
                numero_documento=f'{1000000000 + n}', semestre=semestre, estado_matricula='ACTIVO',
                email_institucional=f'est{n:05d}@ufps.edu.co',
            )
            estudiantes.append(est)
            # ~15 % con bajo rendimiento y ~10 % con muchas faltas
            media = 2.6 if rng.random() < 0.15 else 3.6
            prob_falta = 0.3 if rng.random() < 0.10 else 0.05
            grupo = GRUPOS[(n // SEMESTRES) % len(GRUPOS)]  # mitad del semestre en cada grupo

            cursados = anteriores[-(semestre - 1):] if semestre > 1 else []
            for nivel, periodo in enumerate(cursados, start=semestre - len(cursados)):
                for materia in materias[nivel]:
                    notas.append(Nota(estudiante=est, curso=cursos[(materia.codigo, grupo)], periodo=periodo,
                                      definitiva=_nota(rng, media)))
            # Periodo actual: cortes 1 y 2 registrados, sin definitiva
            for materia in materias[semestre]:
                curso = cursos[(materia.codigo, grupo)]
                notas.append(Nota(estudiante=est, curso=curso, periodo=actual,
                                  corte1=_nota(rng, media), corte2=_nota(rng, media)))
                for fecha in fechas:
                    asistencias.append(Asistencia(
                        estudiante=est, curso=curso, periodo=actual, fecha_clase=fecha,
                        estado='FALTA' if rng.random() < prob_falta else 'ASISTIO',
                    ))

        Estudiante.objects.bulk_create(estudiantes, batch_size=1000)
        Nota.objects.bulk_create(notas, batch_size=2000)
        Asistencia.objects.bulk_create(asistencias, batch_size=2000)
        return {
            'estudiantes': len(estudiantes), 'notas': len(notas), 'asistencias': len(asistencias),
            'cursos': len(cursos), 'docentes': DOCENTES,
        }

    def _medir_procesos(self, total_estudiantes):
        from alertas.alertas_corte import evaluar_cortes_periodo_actual
        from alertas.alertas_inasistencia import evaluar_inasistencia_periodo_actual
        from alertas.models import Alerta, NotificacionHistorial
        from alertas.reevaluacion import ejecutar_reevaluacion

        tiempos = {}

        def medir(nombre, funcion):
            correos_antes = NotificacionHistorial.objects.count()
            t = time.perf_counter()
            funcion()
            seg = round(time.perf_counter() - t, 2)
            tiempos[nombre] = {
                'segundos': seg,
                'ms_por_estudiante': round(seg * 1000 / total_estudiantes, 1),
                'alertas_abiertas': Alerta.objects.exclude(estado__in=['cerrada', 'closed']).count(),
                # Envíos de correo intentados: sin BREVO_API_KEY fallan al instante; en producción
                # cada uno es una llamada HTTP síncrona dentro de este mismo proceso
                'correos_intentados': NotificacionHistorial.objects.count() - correos_antes,
            }
            self.stdout.write(
                f'  {nombre}: {seg} s ({tiempos[nombre]["ms_por_estudiante"]} ms/estudiante, '
                f'{tiempos[nombre]["correos_intentados"]} correos)'
            )

        self.stdout.write('Procesos por lotes:')
        medir('reevaluacion_completa', lambda: ejecutar_reevaluacion(origen='MANUAL', max_intentos=1))
        medir('alertas_por_corte', evaluar_cortes_periodo_actual)
        medir('alertas_por_inasistencia', evaluar_inasistencia_periodo_actual)
        # Segunda pasada: el caso diario real, sin cambios en los datos (no debe duplicar alertas)
        medir('reevaluacion_sin_cambios', lambda: ejecutar_reevaluacion(origen='MANUAL', max_intentos=1))
        return tiempos
