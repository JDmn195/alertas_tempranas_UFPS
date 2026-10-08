import { defineConfig, devices } from '@playwright/test';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Pruebas e2e: levantan el backend en modo E2E (SQLite propio, sin el .env) y el
// frontend apuntando a él. Puertos distintos a los de desarrollo para no chocar.
const BACKEND_PORT = 8001;
const FRONTEND_PORT = 5174;
const BACKEND_DIR = path.resolve(__dirname, '../BACKEND/alertas_tempranas_ufps');
const PYTHON = process.env.E2E_PYTHON
  ?? path.join(BACKEND_DIR, 'env', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');

export default defineConfig({
  testDir: './e2e',
  // Las pruebas comparten una sola base: en serie y en el orden de los archivos
  fullyParallel: false,
  workers: 1,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: `http://localhost:${FRONTEND_PORT}`,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    locale: 'es-CO',
    timezoneId: 'America/Bogota',
  },
  projects: [
    { name: 'setup', testMatch: /auth\.setup\.ts/ },
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
      dependencies: ['setup'],
    },
  ],
  webServer: [
    {
      // Recrea la base e2e en cada corrida y sirve la API
      command: `"${PYTHON}" manage.py preparar_e2e && "${PYTHON}" manage.py runserver 127.0.0.1:${BACKEND_PORT} --noreload`,
      cwd: BACKEND_DIR,
      url: `http://127.0.0.1:${BACKEND_PORT}/admin/login/`,
      env: { E2E: 'True', DEBUG: 'True', PYTHONIOENCODING: 'utf-8' },
      reuseExistingServer: false,
      timeout: 120_000,
    },
    {
      command: `npx vite --port ${FRONTEND_PORT} --strictPort`,
      url: `http://localhost:${FRONTEND_PORT}`,
      env: { VITE_API_URL: `http://127.0.0.1:${BACKEND_PORT}` },
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
