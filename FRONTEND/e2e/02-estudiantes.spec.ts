import { expect, test } from '@playwright/test';
import { ESTUDIANTES, sesion } from './datos';

test.use({ storageState: sesion('director') });

test.describe('Directorio y ficha del estudiante', () => {
  test('el directorio lista y busca estudiantes', async ({ page }) => {
    await page.goto('/dashboard/students');
    await expect(page.getByRole('heading', { name: '3 estudiantes encontrados' })).toBeVisible();

    const ana = page.getByRole('row', { name: new RegExp(ESTUDIANTES.enRiesgo.codigo) });
    await expect(ana).toContainText('ALTO');
    await expect(ana).toContainText('2.00');

    await page.getByPlaceholder('Buscar por nombre o código...').fill('Carla');
    await expect(page.getByRole('row', { name: new RegExp(ESTUDIANTES.regular.nombre) })).toBeVisible();
    await expect(page.getByRole('row', { name: new RegExp(ESTUDIANTES.enRiesgo.nombre) })).toHaveCount(0);
  });

  test('la ficha muestra las notas por corte y las alertas de corte (HU-31, HU-32)', async ({ page }) => {
    await page.goto(`/dashboard/students/${ESTUDIANTES.enRiesgo.codigo}`);
    await expect(page.getByRole('heading', { name: ESTUDIANTES.enRiesgo.nombre, level: 1 })).toBeVisible();

    await page.getByRole('button', { name: '2026-1' }).click();
    const calculo = page.getByRole('row', { name: /Cálculo I/ });
    await expect(calculo.getByRole('cell')).toContainText([
      '1150101', /Cálculo I/, '3', 'A', 'Docente Curso', '1.5', '2.0', '2.5',
    ]);
    await expect(calculo).toContainText('Alerta corte 1 (C1)');
    await expect(calculo).toContainText('Necesita 5.3');
    await expect(calculo).toContainText('En curso');
  });

  test('los indicadores cargan con materias en curso', async ({ page }) => {
    const indicadores = page.waitForResponse((r) => r.url().includes(`/students/${ESTUDIANTES.regular.codigo}/indicators/`));
    await page.goto(`/dashboard/students/${ESTUDIANTES.regular.codigo}`);
    expect((await indicadores).status()).toBe(200);

    // Física I aprobada (4.2); Cálculo I sigue en curso
    await expect(page.getByText('Materias Aprobadas').locator('../..')).toContainText(/^\s*1\s*Materias Aprobadas/);
  });
});
