import { expect, test, type Page } from '@playwright/test';
import { ESTUDIANTES, sesion } from './datos';

async function abrirAlertasDe(page: Page, nombre: string) {
  await page.getByPlaceholder('Buscar estudiante...').fill(nombre);
  await page.getByRole('heading', { name: nombre }).click();
}

test.describe('Gestión de alertas', () => {
  test.use({ storageState: sesion('bienestar') });

  test('se filtran por tipo', async ({ page }) => {
    await page.goto('/dashboard/alerts');
    await abrirAlertasDe(page, ESTUDIANTES.enRiesgo.nombre);
    await expect(page.getByText('Promedio Crítico')).toBeVisible();
    await expect(page.getByText(/Dos cortes perdidos/)).toBeVisible();

    await page.getByRole('combobox').selectOption('CORTE');
    await expect(page.getByText(/Dos cortes perdidos/)).toBeVisible();
    await expect(page.getByText('Promedio Crítico')).toHaveCount(0);
  });

  test('registrar una intervención pasa la alerta a seguimiento (HU-19)', async ({ page }) => {
    await page.goto('/dashboard/alerts');
    await expect(page.getByRole('button', { name: 'En Seguimiento 0' })).toBeVisible();
    await abrirAlertasDe(page, ESTUDIANTES.enRiesgo.nombre);

    // Botón "Intervenir" de la tarjeta de la alerta de promedio
    const alerta = page.getByText('Promedio Crítico').locator('xpath=ancestor::div[.//button[normalize-space()="Intervenir"]][1]');
    await alerta.getByRole('button', { name: 'Intervenir' }).click();

    const modal = page.getByRole('heading', { name: 'Registrar Intervención' });
    await expect(modal).toBeVisible();
    await expect(page.getByText('Promedio Crítico').last()).toBeVisible();
    await page.locator('select', { has: page.getByRole('option', { name: 'Tutoría' }) }).selectOption({ label: 'Tutoría' });
    await page.getByPlaceholder('Describe las acciones realizadas...').fill('Tutoría de nivelación agendada con la estudiante.');
    await page.getByRole('button', { name: 'Guardar intervención' }).click();
    await expect(modal).toHaveCount(0);

    await expect(page.getByRole('button', { name: 'En Seguimiento 1' })).toBeVisible();

    // La alerta sale de las activas de Ana (los contadores de las pestañas son globales)
    await page.reload();
    await page.getByPlaceholder('Buscar estudiante...').fill(ESTUDIANTES.enRiesgo.nombre);
    await expect(page.getByText('3 ALERTAS')).toBeVisible();

    await page.getByRole('button', { name: 'En Seguimiento 1' }).click();
    await expect(page.getByText('1 ALERTA', { exact: true })).toBeVisible();
    await page.getByRole('heading', { name: ESTUDIANTES.enRiesgo.nombre }).click();
    await expect(page.getByText('Promedio Crítico')).toBeVisible();
  });
});

test.describe('Alcance del docente', () => {
  test.use({ storageState: sesion('docente') });

  test('ve las alertas de los estudiantes de sus cursos', async ({ page }) => {
    await page.goto('/dashboard/alerts');
    await expect(page.getByRole('heading', { name: ESTUDIANTES.enRiesgo.nombre })).toBeVisible();
  });
});
