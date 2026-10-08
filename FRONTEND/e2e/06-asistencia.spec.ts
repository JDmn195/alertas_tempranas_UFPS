import { expect, test } from '@playwright/test';
import { ESTUDIANTES, sesion } from './datos';

test.describe('Registro de asistencia (HU-33)', () => {
  test.use({ storageState: sesion('docente') });

  test('el docente toma asistencia de su curso', async ({ page }) => {
    await page.goto('/dashboard/teacher');
    const calculo = page.locator('div', { has: page.getByRole('heading', { name: 'Cálculo I' }) })
      .filter({ has: page.getByRole('button', { name: 'Tomar asistencia' }) }).last();
    await calculo.getByRole('button', { name: 'Tomar asistencia' }).click();

    await expect(page.getByRole('heading', { name: 'Tomar Asistencia: Cálculo I' })).toBeVisible();
    await page.getByRole('button', { name: 'Marcar todos presentes' }).click();
    await page.getByRole('row', { name: new RegExp(ESTUDIANTES.regular.nombre) }).getByText('Falta', { exact: true }).click();
    await expect(page.getByText(/1 faltas? \//)).toBeVisible();

    await page.getByRole('button', { name: 'Guardar Asistencia' }).click();
    await expect(page.getByText(/Asistencia guardada: \d+ nuevos/)).toBeVisible();
  });
});

test.describe('Porcentaje de inasistencia (HU-34)', () => {
  test.use({ storageState: sesion('director') });

  test('la ficha muestra las faltas registradas', async ({ page }) => {
    await page.goto(`/dashboard/students/${ESTUDIANTES.regular.codigo}`);
    await page.getByRole('button', { name: 'Asistencia' }).click();

    await expect(page.getByText('Umbral general: 20%')).toBeVisible();
    const calculo = page.getByRole('row', { name: /Cálculo I/ });
    // Una clase registrada, una falta: 100 %
    await expect(calculo.getByRole('cell')).toContainText([/Cálculo I/, 'A', '1', '1', '0', /100/]);
  });
});
