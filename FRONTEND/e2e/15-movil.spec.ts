import { expect, test } from '@playwright/test';
import { CONTRASENA, sesion, type Rol } from './datos';

const MOVIL = { width: 390, height: 844 };

test.describe('personal en móvil', () => {
  test.use({ storageState: sesion('admin'), viewport: MOVIL });

  test('las tablas principales se ven como tarjetas, sin desborde y con botones de 44 px', async ({ page }) => {
    for (const ruta of ['students', 'courses', 'students/1152001', 'admin/audit-log', 'admin/notifications-history']) {
      await page.goto(`/dashboard/${ruta}`);
      const tabla = page.locator('table.tabla-tarjetas').first();
      await expect(tabla).toBeVisible();
      const celda = tabla.locator('tbody tr').first().locator('td[data-label]').first();
      await expect(celda).toBeVisible();
      expect(await celda.getAttribute('data-label')).toBeTruthy();
      // El ordenamiento conserva controles visibles; los demás encabezados solo los lee el lector de pantalla.
      const ordenar = tabla.locator('thead button');
      if (await ordenar.count()) {
        await ordenar.first().scrollIntoViewIfNeeded();
        await expect(ordenar.first()).toBeInViewport();
        await ordenar.first().click();
        await expect(page).toHaveURL(/sort=(codigo|codigo_materia)/);
      }
      else expect((await tabla.locator('thead').boundingBox())?.width ?? 0).toBeLessThanOrEqual(1);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    }
    await page.goto('/dashboard/students');
    const verPerfil = page.getByRole('button', { name: 'Ver Perfil' }).first();
    await expect(verPerfil).toBeVisible();
    expect((await verPerfil.boundingBox())?.height ?? 0).toBeGreaterThanOrEqual(43.5);
  });

  test('en escritorio la tabla sigue siendo tabla', async ({ page }) => {
    await page.setViewportSize({ width: 1280, height: 800 });
    await page.goto('/dashboard/students');
    await expect(page.getByRole('columnheader', { name: 'Semestre' })).toBeVisible();
  });
});

for (const rol of ['admin', 'director', 'bienestar', 'docente'] as Rol[]) {
  test.describe(`menú móvil: ${rol}`, () => {
    test.use({ storageState: sesion(rol), viewport: MOVIL });

    test('se abre y se cierra', async ({ page }) => {
      await page.goto('/dashboard');
      const abrir = page.getByRole('button', { name: 'Abrir menú' });
      await expect(abrir).toBeVisible();
      const menu = page.getByRole('complementary', { name: 'Menú principal' });
      await expect(menu).not.toBeInViewport();
      await abrir.click();
      await expect(menu).toBeInViewport();
      await expect(menu.getByRole('link', { name: '¿Cómo funciona?' })).toBeVisible();
      await page.keyboard.press('Escape');
      await expect(menu).not.toBeInViewport();
    });
  });
}

test.describe('portal del estudiante en móvil', () => {
  test.use({ viewport: { width: 360, height: 740 } });

  test('la barra inferior cabe y la cabecera muestra el nombre', async ({ page }) => {
    await page.goto('/login');
    await page.getByLabel('Correo electrónico').fill('1152001@ufps.edu.co');
    await page.getByLabel('Contraseña').fill(CONTRASENA);
    await page.getByRole('button', { name: 'Iniciar sesión' }).click();
    await expect(page).toHaveURL(/\/dashboard\/portal$/, { timeout: 15_000 });

    const enlaces = page.locator('nav[aria-label="Secciones del portal"]:visible').getByRole('link');
    await expect(enlaces).toHaveCount(5);
    for (let i = 0; i < 5; i++) {
      const caja = await enlaces.nth(i).boundingBox();
      expect(caja!.x).toBeGreaterThanOrEqual(0);
      expect(caja!.x + caja!.width).toBeLessThanOrEqual(360.5);
      expect(caja!.height).toBeGreaterThanOrEqual(43.5);
    }
    await expect(page.locator('header').getByText('Ana Pérez', { exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
  });
});
