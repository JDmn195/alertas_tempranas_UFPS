import { expect, test } from '@playwright/test';
import { sesion } from './datos';

test.use({ storageState: sesion('admin') });

test('los controles de solo icono tienen nombre y el foco de teclado es visible', async ({ page }) => {
  await page.goto('/dashboard/admin/risk-rules');
  await expect(page.getByRole('button', { name: 'Eliminar regla Promedio Crítico' })).toBeVisible();
  await page.keyboard.press('Tab');
  await expect(page.locator(':focus-visible')).toHaveCount(1);
  await expect(page.locator(':focus-visible')).toHaveCSS('outline-style', 'solid');
});
