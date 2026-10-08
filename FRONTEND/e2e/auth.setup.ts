import { expect, test as setup } from '@playwright/test';
import { CONTRASENA, USUARIOS, type Rol, sesion } from './datos';

// Inicia sesión por la pantalla con cada rol y guarda la sesión para el resto de pruebas
for (const rol of Object.keys(USUARIOS) as Rol[]) {
  setup(`sesión de ${rol}`, async ({ page }) => {
    await page.goto('/login');
    await page.getByLabel('Correo electrónico').fill(USUARIOS[rol].correo);
    await page.getByLabel('Contraseña').fill(CONTRASENA);
    await page.getByRole('button', { name: 'Iniciar sesión' }).click();
    await expect(page).toHaveURL(/\/dashboard\//);
    await page.context().storageState({ path: sesion(rol) });
  });
}
