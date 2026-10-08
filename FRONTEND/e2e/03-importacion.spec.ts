import { expect, test } from '@playwright/test';
import path from 'path';
import { fileURLToPath } from 'url';
import { ESTUDIANTES, sesion } from './datos';

const ARCHIVOS = path.join(path.dirname(fileURLToPath(import.meta.url)), 'archivos');

test.use({ storageState: sesion('admin') });

test.describe('Importación de historial académico', () => {
  test('un archivo con columnas faltantes se rechaza', async ({ page }) => {
    await page.goto('/dashboard/admin/import');
    await page.getByRole('combobox').selectOption({ label: 'Reportes Individuales de Estudiantes' });
    await page.locator('input[type=file]').setInputFiles({
      name: `historial_${ESTUDIANTES.sinNotas.codigo}.csv`,
      mimeType: 'text/csv',
      buffer: Buffer.from('Periodo,Definitiva\n2026-1,4.0\n'),
    });

    await expect(page.getByText(/columnas/i).first()).toBeVisible();
    await expect(page.getByRole('heading', { name: '¡Importación Exitosa!' })).toHaveCount(0);
  });

  test('importar el historial de un estudiante calcula su riesgo (HU-02)', async ({ page }) => {
    await page.goto('/dashboard/admin/import');
    await page.getByRole('combobox').selectOption({ label: 'Reportes Individuales de Estudiantes' });
    // Física I perdida (1.8) en 2025-2 y Cálculo I en curso con corte 1 = 3.5
    await page.locator('input[type=file]').setInputFiles(path.join(ARCHIVOS, `historial_${ESTUDIANTES.sinNotas.codigo}.csv`));

    await expect(page.getByRole('heading', { name: '¡Importación Exitosa!' })).toBeVisible();

    await page.goto(`/dashboard/students/${ESTUDIANTES.sinNotas.codigo}`);
    await expect(page.getByRole('heading', { name: ESTUDIANTES.sinNotas.nombre, level: 1 })).toBeVisible();
    await expect(page.getByText('1.80').first()).toBeVisible();
    await expect(page.getByText('Nivel de Riesgo', { exact: true }).first().locator('..')).toContainText('ALTO');
  });
});
