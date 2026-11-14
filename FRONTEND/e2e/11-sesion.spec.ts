import { expect, test } from '@playwright/test';
import { CONTRASENA, CORREO_CIERRE } from './datos';

test.beforeEach(async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('Correo electrónico').fill(CORREO_CIERRE);
  await page.getByLabel('Contraseña').fill(CONTRASENA);
  await page.getByRole('button', { name: 'Iniciar sesión' }).click();
  await expect(page).toHaveURL(/\/dashboard\/teacher$/, { timeout: 15_000 });
});

test('cerrar sesión revoca el token y permite un nuevo ingreso', async ({ page, request }) => {
  const token = await page.evaluate(() => JSON.parse(localStorage.getItem('user')!).token);
  await page.getByRole('button', { name: 'Cerrar sesión' }).click();
  await expect(page).toHaveURL(/\/login$/, { timeout: 15_000 });
  expect(await page.evaluate(() => localStorage.getItem('user'))).toBeNull();
  const respuesta = await request.get('http://127.0.0.1:8001/api/usuarios/me/', {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(respuesta.status()).toBe(401);
  await page.getByLabel('Correo electrónico').fill(CORREO_CIERRE);
  await page.getByLabel('Contraseña').fill(CONTRASENA);
  await page.getByRole('button', { name: 'Iniciar sesión' }).click();
  await expect(page).toHaveURL(/\/dashboard\/teacher$/, { timeout: 15_000 });
});

test('si logout falla conserva la sesión y permite reintentar', async ({ page }) => {
  await page.route('**/api/usuarios/logout/', ruta => ruta.fulfill({ status: 503, body: 'No disponible' }));
  await page.getByRole('button', { name: 'Cerrar sesión' }).click();
  await expect(page.getByText('No se pudo cerrar la sesión. Inténtalo de nuevo.')).toBeVisible();
  expect(await page.evaluate(() => localStorage.getItem('user'))).not.toBeNull();
  await page.unroute('**/api/usuarios/logout/');
  await page.getByRole('button', { name: 'Cerrar sesión' }).click();
  await expect(page).toHaveURL(/\/login$/, { timeout: 15_000 });
});
