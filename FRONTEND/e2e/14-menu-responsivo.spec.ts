import { expect, test } from '@playwright/test';
import { sesion } from './datos';

test.use({ storageState: sesion('admin'), viewport: { width: 390, height: 844 } });

test('el menú móvil se abre, se cierra con Esc y al navegar', async ({ page }) => {
  await page.goto('/dashboard/admin/import');
  const abrir = page.getByRole('button', { name: 'Abrir menú' });
  await expect(abrir).toBeVisible();
  const menu = page.getByRole('complementary', { name: 'Menú principal' });
  await expect(menu).not.toBeInViewport();

  await abrir.click();
  await expect(menu).toBeInViewport();
  await expect(menu).toContainText('Importar Módulo');

  await page.keyboard.press('Escape');
  await expect(menu).not.toBeInViewport();

  await abrir.click();
  await menu.getByRole('link', { name: 'Reglas de Riesgo' }).click();
  await expect(page).toHaveURL(/\/dashboard\/admin\/risk-rules$/);
  await expect(menu).not.toBeInViewport();
});
