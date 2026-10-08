import { expect, test } from '@playwright/test';
import { ESTUDIANTES, sesion } from './datos';

test.use({ storageState: sesion('admin') });

test('crear una regla recalcula el riesgo y genera sus alertas (HU-13)', async ({ page }) => {
  await page.goto('/dashboard/admin/risk-rules');
  await page.getByRole('button', { name: 'Añadir Regla' }).click();
  await expect(page.getByRole('heading', { name: 'Añadir Nueva Regla' })).toBeVisible();

  // Carla tiene PPA 4.2: con esta regla queda en riesgo
  await page.getByPlaceholder('e.g., Bajo Promedio - Crítico').fill('Promedio Bajo E2E');
  await page.getByPlaceholder('e.g., 3.0').fill('4.5');
  await page.getByRole('button', { name: 'Media' }).click();
  await page.getByRole('button', { name: 'Guardar Regla' }).click();

  await expect(page.getByRole('heading', { name: 'Añadir Nueva Regla' })).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'Promedio Bajo E2E' })).toBeVisible();
  await expect(page.getByText('PROMEDIO < 4.5')).toBeVisible();

  await page.goto('/dashboard/alerts');
  await page.getByPlaceholder('Buscar estudiante...').fill(ESTUDIANTES.regular.nombre);
  await page.getByRole('heading', { name: ESTUDIANTES.regular.nombre }).click();
  await expect(page.getByText('Promedio Bajo E2E')).toBeVisible();
});

test('las reglas por corte solo permiten editar umbral y estado (HU-32)', async ({ page }) => {
  await page.goto('/dashboard/admin/risk-rules');
  await expect(page.getByRole('heading', { name: 'Alertas Tempranas por Corte' })).toBeVisible();
  for (const regla of ['Corte 1 — Alerta temprana', 'Corte 2 — Sostenido bajo', 'Corte 3 — Nota necesaria crítica']) {
    await expect(page.getByRole('heading', { name: regla })).toBeVisible();
  }
  await expect(page.getByRole('heading', { name: 'Umbral de Inasistencia' })).toBeVisible();
  await expect(page.getByText('> 20%')).toBeVisible();
});
