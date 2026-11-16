import { expect, test } from '@playwright/test';
import { CONTRASENA, ESTUDIANTES, sesion } from './datos';

// SDAT-312: re-test de los hallazgos B08, B15, B18, B21, B26, B28, B29, B31, B33, B34, B35 y B38.
// Va al final: crea una regla y usa la intervención que registró 04-alertas.

test.describe('Administrador', () => {
  test.use({ storageState: sesion('admin') });

  test('B08: el doble clic en «Guardar Regla» crea una sola regla', async ({ page }) => {
    let envios = 0;
    await page.route('**/api/alertas/reglas/', async (ruta) => {
      if (ruta.request().method() === 'POST') {
        envios += 1;
        await new Promise((r) => setTimeout(r, 800));
      }
      await ruta.continue();
    });
    await page.goto('/dashboard/admin/risk-rules');
    await page.getByRole('button', { name: 'Añadir Regla' }).click();
    await page.getByPlaceholder('e.g., Bajo Promedio - Crítico').fill('Regla doble clic B08');
    await page.getByPlaceholder('e.g., 3.0').fill('3.1');
    await page.getByRole('button', { name: 'Guardar Regla' }).dblclick();
    await expect(page.getByRole('heading', { name: 'Añadir Nueva Regla' })).toHaveCount(0);
    expect(envios).toBe(1);
    await expect(page.getByRole('heading', { name: 'Regla doble clic B08' })).toHaveCount(1);
  });

  test('B18: el rango inicial de Reportes es el semestre en curso', async ({ page }) => {
    await page.clock.setFixedTime(new Date('2026-11-16T12:00:00-05:00'));
    await page.goto('/dashboard/reports');
    const fechas = page.locator('input[type="date"]');
    await expect(fechas.nth(0)).toHaveValue('2026-07-01');
    await expect(fechas.nth(1)).toHaveValue('2026-12-31');
  });

  test('B26: un campo vacío de recordatorios explica el error en español y bloquea Guardar', async ({ page }) => {
    await page.goto('/dashboard/admin/automatic-processes');
    await page.getByLabel('Días sin intervención (alerta)').fill('');
    await expect(page.getByText('Este campo es obligatorio.')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Guardar configuración' })).toBeDisabled();
  });

  test('B28: una intervención inexistente dice que no existe y no ofrece subir archivos', async ({ page }) => {
    await page.goto('/dashboard/intervenciones/999999/evidencias');
    await expect(page.getByText('La intervención solicitada no existe.')).toBeVisible();
    await expect(page.getByText('Seleccionar Archivo')).toHaveCount(0);
    await expect(page.getByText(/Revisa tu conexión/)).toHaveCount(0);
  });
});

test.describe('Director', () => {
  test.use({ storageState: sesion('director') });

  test('B21: las opciones del filtro de riesgo no prometen rangos de promedio', async ({ page }) => {
    await page.goto('/dashboard/students');
    const filtro = page.locator('select[aria-label="Filtrar por nivel de riesgo"]').first();
    await expect(filtro).toHaveCount(1);
    const opciones = (await filtro.locator('option').allTextContents()).join(' | ');
    expect(opciones).toContain('Riesgo Alto');
    expect(opciones).not.toMatch(/Promedio\s*[<>]|3\.0-3\.4|>=\s*3\.5/);
  });

  test('B15 y B38: la ficha marca «En curso» y explica reprobadas frente a pendientes', async ({ page }) => {
    await page.goto(`/dashboard/students/${ESTUDIANTES.regular.codigo}`);
    await expect(page.getByText('Promedio del Semestre')).toBeVisible();
    await expect(page.getByText('En curso').first()).toBeVisible();
    await expect(page.getByText(/Intentos perdidos \(la regla de riesgo cuenta materias pendientes\)/)).toBeVisible();
  });
});

test.describe('Bienestar', () => {
  test.use({ storageState: sesion('bienestar') });

  test('B34: los modales Historial e Intervenir son diálogos y cierran con Escape', async ({ page }) => {
    await page.goto('/dashboard/alerts');
    await page.getByPlaceholder('Buscar estudiante...').fill(ESTUDIANTES.enRiesgo.nombre);
    await page.getByRole('heading', { name: ESTUDIANTES.enRiesgo.nombre }).click();

    await page.getByRole('button', { name: 'Historial' }).first().click();
    const historial = page.getByRole('dialog', { name: 'Historial de intervenciones' });
    await expect(historial).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(historial).toHaveCount(0);

    await page.getByRole('button', { name: 'Intervenir' }).first().click();
    const registrar = page.getByRole('dialog', { name: 'Registrar intervención' });
    await expect(registrar).toBeVisible();
    await page.keyboard.press('Escape');
    await expect(registrar).toHaveCount(0);
  });

  test('B35: el detalle de la intervención muestra el estado en español', async ({ page }) => {
    await page.goto(`/dashboard/students/${ESTUDIANTES.enRiesgo.codigo}`);
    await page.getByText('Historial de Intervenciones').scrollIntoViewIfNeeded();
    await page.getByText(/Por:/).first().click();
    await expect(page.getByText('Causa de la Alerta')).toBeVisible();
    await expect(page.getByText('En seguimiento', { exact: true })).toBeVisible();
    await expect(page.getByText('en_seguimiento')).toHaveCount(0);
  });
});

test.describe('Sin sesión', () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test('B33: /reset-password sin enlace explica que no sirve', async ({ page }) => {
    await page.goto('/reset-password');
    await expect(page.getByRole('heading', { name: 'El enlace no es válido' })).toBeVisible();
    await expect(page).toHaveURL(/\/reset-password$/);
  });
});

test.describe('Portal del estudiante', () => {
  test.use({ storageState: { cookies: [], origins: [] } });

  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
    await page.getByLabel('Correo electrónico').fill('1152001@ufps.edu.co');
    await page.getByLabel('Contraseña').fill(CONTRASENA);
    await page.getByRole('button', { name: 'Iniciar sesión' }).click();
    await expect(page).toHaveURL(/\/dashboard\/portal$/, { timeout: 15_000 });
  });

  test('B29: en 1366 px el título de la cabecera no se superpone con la navegación', async ({ page }) => {
    await page.setViewportSize({ width: 1366, height: 768 });
    const titulo = await page.getByText('Mi seguimiento académico').boundingBox();
    const inicio = await page.getByRole('navigation', { name: 'Secciones del portal' }).first()
      .getByRole('link', { name: 'Inicio' }).boundingBox();
    expect(inicio).not.toBeNull();
    // Si el título no cabe en esta anchura se oculta (boundingBox null); si se muestra no debe pisar la navegación
    if (titulo) expect(titulo.x + titulo.width).toBeLessThanOrEqual(inicio!.x);
  });

  test('B31: en 375 px la barra inferior cabe en una sola fila', async ({ page }) => {
    await page.setViewportSize({ width: 375, height: 667 });
    const barra = page.getByRole('navigation', { name: 'Secciones del portal' }).last();
    const enlaces = barra.getByRole('link');
    const total = await enlaces.count();
    expect(total).toBeGreaterThan(0);
    const cajas = [];
    for (let i = 0; i < total; i++) cajas.push((await enlaces.nth(i).boundingBox())!);
    expect(new Set(cajas.map((c) => Math.round(c.y))).size).toBe(1);
    for (const c of cajas) expect(c.x + c.width).toBeLessThanOrEqual(375);
  });
});
