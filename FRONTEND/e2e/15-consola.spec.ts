import { expect, test } from '@playwright/test';
import { sesion } from './datos';

test.use({ storageState: sesion('admin') });

// SDAT-336: sin avisos de React (NaN en value, refs en diálogos, keys) en reglas y confirmaciones
test('reglas y diálogos de confirmación no escriben avisos en la consola', async ({ page }) => {
  const avisos: string[] = [];
  page.on('console', m => { if (['warning', 'error'].includes(m.type())) avisos.push(m.text().slice(0, 300)); });

  await page.goto('/dashboard/admin/risk-rules');
  await page.locator('button[aria-label^="Eliminar regla"]').first().click();
  await page.getByRole('button', { name: 'Cancelar' }).click();

  await page.locator('button[title="Haz clic para editar el umbral"]').first().click();
  await page.locator('input[type=number]').first().fill('');

  await page.getByRole('button', { name: /añadir regla/i }).click();
  await page.locator('input[type=number][step="0.01"]').fill('');
  await page.waitForTimeout(300);

  expect(avisos).toEqual([]);
});
