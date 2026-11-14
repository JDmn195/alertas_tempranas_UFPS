import { expect, test } from '@playwright/test';
import { sesion } from './datos';

test.use({ storageState: sesion('admin') });

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
