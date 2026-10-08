import { expect, test } from '@playwright/test';
import { sesion } from './datos';

test.use({ storageState: sesion('admin') });

test.describe('Procesos automáticos', () => {
  test('ejecutar la re-evaluación manual la registra en el historial (HU-29)', async ({ page }) => {
    await page.goto('/dashboard/admin/automatic-processes');
    await expect(page.getByText('Aún no hay ejecuciones registradas.')).toBeVisible();

    await page.getByRole('button', { name: 'Ejecutar ahora' }).click();
    await page.getByRole('button', { name: 'Actualizar' }).first().click();

    await expect(page.getByText('Aún no hay ejecuciones registradas.')).toHaveCount(0);
    await expect(page.getByText('Sin ejecuciones')).toHaveCount(0);
  });

  test('la configuración de recordatorios se guarda (HU-30)', async ({ page }) => {
    await page.goto('/dashboard/admin/automatic-processes');
    await page.getByLabel('Días sin intervención (alerta)').fill('10');
    await page.getByRole('checkbox', { name: 'BIENESTAR' }).check();
    await page.getByRole('button', { name: 'Guardar configuración' }).click();
    await expect(page.getByText('Configuración guardada.')).toBeVisible();

    await page.reload();
    await expect(page.getByLabel('Días sin intervención (alerta)')).toHaveValue('10');
    await expect(page.getByRole('checkbox', { name: 'BIENESTAR' })).toBeChecked();
  });
});
