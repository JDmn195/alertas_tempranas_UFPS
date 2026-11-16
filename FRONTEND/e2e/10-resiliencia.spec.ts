import { expect, test } from '@playwright/test';
import { sesion } from './datos';

test.use({ storageState: sesion('admin') });

test('cancelar una confirmación no envía el borrado; confirmar lo envía una vez', async ({ page }) => {
  let borrados = 0;
  await page.route('**/api/alertas/reglas/*/', async ruta => {
    if (ruta.request().method() === 'DELETE') {
      borrados++;
      await ruta.fulfill({ status: 200, json: { mensaje: 'Regla eliminada.' } });
    } else await ruta.continue();
  });
  page.on('dialog', () => { throw new Error('Se abrió un diálogo nativo del navegador.'); });
  await page.goto('/dashboard/admin/risk-rules');
  const eliminar = page.getByRole('button', { name: 'Eliminar regla Promedio Crítico', exact: true });
  await eliminar.click();
  const dialogo = page.getByRole('alertdialog');
  await expect(dialogo).toBeVisible();
  await dialogo.getByRole('button', { name: 'Cancelar', exact: true }).click();
  await expect(dialogo).toHaveCount(0);
  expect(borrados).toBe(0);
  await eliminar.click();
  await dialogo.getByRole('button', { name: 'Eliminar regla', exact: true }).click();
  await expect.poll(() => borrados).toBe(1);
  await expect(dialogo).toHaveCount(0);
});

test('una respuesta HTML del servidor muestra un error legible y permite recuperarse', async ({ page }) => {
  let fallar = true;
  await page.route('**/api/alertas/notificaciones/historial/**', async ruta => {
    if (fallar) await ruta.fulfill({ status: 503, contentType: 'text/html', body: '<html>upstream unavailable</html>' });
    else await ruta.continue();
  });
  await page.goto('/dashboard/admin/notifications-history');
  await expect(page.getByText(/El servidor está iniciando o no está disponible/)).toBeVisible();
  await expect(page.getByText(/Unexpected token|upstream unavailable/)).toHaveCount(0);
  fallar = false;
  await page.reload();
  await expect(page.getByText(/El servidor está iniciando o no está disponible/)).toHaveCount(0);
});

test('el inicio de sesión muestra un aviso cuando Render responde HTML', async ({ browser }) => {
  const contexto = await browser.newContext();
  const pagina = await contexto.newPage();
  await pagina.route('**/api/usuarios/login/', ruta => ruta.fulfill({
    status: 502, contentType: 'text/html', body: '<html>upstream unavailable</html>',
  }));
  await pagina.goto('/login');
  await pagina.getByLabel('Correo electrónico').fill('admin@ufps.edu.co');
  await pagina.getByLabel('Contraseña').fill('Clave-Segura-2026');
  await pagina.getByRole('button', { name: 'Iniciar sesión' }).click();
  await expect(pagina.getByRole('alert')).toContainText('El servidor está iniciando o no está disponible');
  await expect(pagina.getByText('upstream unavailable')).toHaveCount(0);
  await contexto.close();
});
