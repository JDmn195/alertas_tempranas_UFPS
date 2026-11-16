import { expect, test } from '@playwright/test';
import { CONTRASENA, sesion } from './datos';

test('administración consulta reglas, procesos y revisión de la interfaz', async ({ browser }) => {
  const contexto = await browser.newContext({ storageState: sesion('admin') });
  const pagina = await contexto.newPage();
  await pagina.goto('/dashboard/ayuda');
  await expect(pagina.getByRole('heading', { name: '¿Cómo funciona?' })).toBeVisible();
  await expect(pagina.getByText('Materia perdida: con tres cortes', { exact: false })).toBeVisible();
  await expect(pagina.getByRole('status')).toContainText(/Última revaluación|Todavía no hay revaluaciones/);
  await expect(pagina.getByText(/Revisión de esta interfaz: [0-9a-f]{7,}/)).toBeVisible();
  await contexto.close();
});

test('el estudiante ve ayuda propia sin información del personal', async ({ browser }) => {
  const contexto = await browser.newContext();
  const pagina = await contexto.newPage();
  await pagina.goto('/login');
  await pagina.getByLabel('Correo electrónico').fill('1152001@ufps.edu.co');
  await pagina.getByLabel('Contraseña').fill(CONTRASENA);
  await pagina.getByRole('button', { name: 'Iniciar sesión' }).click();
  await expect(pagina).toHaveURL(/\/dashboard\/portal$/);
  await pagina.goto('/dashboard/ayuda');
  await expect(pagina.getByRole('heading', { name: '¿Cómo funciona?' })).toBeVisible();
  await expect(pagina.getByRole('navigation', { name: 'Accesos relacionados' }).getByRole('link', { name: 'Mi asistencia' })).toBeVisible();
  await expect(pagina.getByText('Última revaluación:', { exact: false })).toHaveCount(0);
  await expect(pagina.getByRole('heading', { name: 'Notas y alertas de corte' })).toHaveCount(0);
  await contexto.close();
});
