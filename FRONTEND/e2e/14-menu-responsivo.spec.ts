import { expect, test } from '@playwright/test';
import { sesion } from './datos';

test.use({ storageState: sesion('admin'), viewport: { width: 390, height: 844 } });

test('el menú móvil conserva el foco y se cierra con Esc o al navegar', async ({ page }) => {
  await page.goto('/dashboard/admin/import');
  const abrir = page.getByRole('button', { name: 'Abrir menú' });
  await expect(abrir).toBeVisible();
  await abrir.click();
  const dialogo = page.getByRole('dialog', { name: 'Menú principal' });
  await expect(dialogo).toBeVisible();
  await expect(dialogo).toContainText('Importar Módulo');
  await expect.poll(() => dialogo.evaluate((elemento) => elemento.contains(document.activeElement))).toBe(true);

  await page.keyboard.press('Escape');
  await expect(dialogo).not.toBeVisible();
  await expect(abrir).toBeFocused();

  await abrir.click();
  await dialogo.getByRole('link', { name: 'Reglas de Riesgo' }).click();
  await expect(page).toHaveURL(/\/dashboard\/admin\/risk-rules$/);
  await expect(dialogo).not.toBeVisible();
});
