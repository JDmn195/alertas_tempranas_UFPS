"""
Corre la prueba de carga de punta a punta:
  1. levanta la API con waitress (servidor WSGI multihilo; gunicorn no corre en Windows)
     contra la base de rendimiento, con DEBUG=False como en producción
  2. corre Locust sin interfaz con el escenario de locustfile.py
  3. guarda el reporte HTML y los CSV en pruebas_rendimiento/resultados/<escenario>_*

La base se prepara antes con `manage.py preparar_rendimiento` (ver README.md).

    python pruebas_rendimiento/ejecutar.py --usuarios 50 --duracion 3m --escenario carga
"""
import argparse
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

PROYECTO = Path(__file__).resolve().parent.parent
RESULTADOS = Path(__file__).resolve().parent / 'resultados'


def esperar_servidor(url, segundos=60):
    limite = time.time() + segundos
    while time.time() < limite:
        try:
            urllib.request.urlopen(url, timeout=2)
            return
        except urllib.error.HTTPError:
            return  # responde (p. ej. 401): está arriba
        except OSError:
            time.sleep(0.5)
    raise SystemExit(f'El servidor no respondió en {url}')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--usuarios', type=int, default=50, help='usuarios concurrentes')
    parser.add_argument('--tasa', type=float, default=5, help='usuarios nuevos por segundo al arrancar')
    parser.add_argument('--duracion', default='3m', help='duración (formato de Locust: 90s, 3m...)')
    parser.add_argument('--escenario', default='carga', help='prefijo de los archivos de resultados')
    parser.add_argument('--hilos', type=int, default=8, help='hilos de waitress')
    parser.add_argument('--puerto', type=int, default=8002)
    args = parser.parse_args()

    if not os.environ.get('E2E_DATABASE_URL'):
        print('Aviso: sin E2E_DATABASE_URL se usa SQLite, que no representa la concurrencia de Postgres.')

    entorno = {
        **os.environ,
        'E2E': 'True',
        'DEBUG': 'False',
        'SECRET_KEY': os.environ.get('SECRET_KEY', 'clave-solo-pruebas-de-rendimiento'),
        'ALLOWED_HOSTS': 'localhost,127.0.0.1',
        # Recálculos tras guardar (p. ej. inasistencia) en un hilo aparte, como en producción
        'E2E_TAREAS_EN_SEGUNDO_PLANO': 'True',
    }
    servidor = subprocess.Popen(
        [sys.executable, '-m', 'waitress', f'--threads={args.hilos}', f'--port={args.puerto}',
         '--channel-timeout=120', 'alertas_tempranas_ufps.wsgi:application'],
        cwd=PROYECTO, env=entorno,
    )
    try:
        base = f'http://127.0.0.1:{args.puerto}'
        esperar_servidor(f'{base}/api/usuarios/me/')
        RESULTADOS.mkdir(exist_ok=True)
        prefijo = RESULTADOS / args.escenario
        locust = subprocess.run(
            [sys.executable, '-m', 'locust', '-f', str(Path(__file__).with_name('locustfile.py')),
             '--headless', '--host', base, '-u', str(args.usuarios), '-r', str(args.tasa),
             '--run-time', args.duracion, '--only-summary',
             '--html', f'{prefijo}.html', '--csv', str(prefijo)],
            cwd=PROYECTO, env={**os.environ, 'PYTHONUTF8': '1'},  # CSV y consola en UTF-8 también en Windows
        )
        return locust.returncode
    finally:
        servidor.terminate()
        servidor.wait(timeout=30)


if __name__ == '__main__':
    sys.exit(main())
