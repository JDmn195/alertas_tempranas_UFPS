import { expect, test } from '@playwright/test';
import { CONTRASENA, USUARIOS, sesion } from './datos';

test.describe('Inicio de sesión', () => {
  test('credenciales incorrectas muestran el error y no dan acceso', async ({ page }) => {
    await page.goto('/login');
    await page.getByLabel('Correo electrónico').fill(USUARIOS.director.correo);
    await page.getByLabel('Contraseña').fill('incorrecta');
    await page.getByRole('button', { name: 'Iniciar sesión' }).click();

    await expect(page.locator('form .bg-red-100')).toBeVisible();
    await expect(page).toHaveURL(/\/login$/);
  });

  for (const [rol, destino] of [
    ['admin', '/dashboard/admin/import'],
    ['docente', '/dashboard/teacher'],
    ['director', '/dashboard/students'],
    ['bienestar', '/dashboard/students'],
  ] as const) {
    test(`${rol} entra a su pantalla de inicio`, async ({ page }) => {
      await page.goto('/login');
      await page.getByLabel('Correo electrónico').fill(USUARIOS[rol].correo);
      await page.getByLabel('Contraseña').fill(CONTRASENA);
      await page.getByRole('button', { name: 'Iniciar sesión' }).click();

      await expect(page).toHaveURL(destino);
      await expect(page.getByText(USUARIOS[rol].nombre).first()).toBeVisible();
    });
  }

  test('sin sesión las rutas protegidas vuelven al login', async ({ page }) => {
    await page.goto('/dashboard/alerts');
    await expect(page).toHaveURL(/\/login$/);
  });
});

test.describe('Sesión iniciada', () => {
  test.use({ storageState: sesion('docente') });

  test('el docente no entra a pantallas de administrador', async ({ page }) => {
    await page.goto('/dashboard/admin/users');
    await expect(page).not.toHaveURL(/admin\/users/);
    await expect(page.getByRole('heading', { name: 'Gestión de Usuarios' })).toHaveCount(0);
  });

  test('el menú solo muestra las opciones del rol', async ({ page }) => {
    await page.goto('/dashboard/teacher');
    const menu = page.getByRole('navigation');
    await expect(menu.getByRole('link', { name: 'Gestión de Alertas' })).toBeVisible();
    await expect(menu.getByRole('link', { name: 'Reglas de Riesgo' })).toHaveCount(0);
    await expect(menu.getByRole('link', { name: 'Gestión de Usuarios' })).toHaveCount(0);
  });

  test('cerrar sesión borra la sesión local', async ({ page }) => {
    await page.goto('/dashboard/teacher');
    await page.getByRole('button', { name: 'Cerrar Sesión' }).click();
    await expect(page).toHaveURL(/\/(login)?$/);

    await page.goto('/dashboard/teacher');
    await expect(page).toHaveURL(/\/login$/);
  });
});
