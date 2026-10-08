import { expect, test } from '@playwright/test';
import { sesion } from './datos';

const NUEVO = { nombre: 'Laura Docente E2E', correo: 'laura.e2e@ufps.edu.co' };

test('el administrador crea un usuario y este debe cambiar la contraseña al entrar', async ({ browser }) => {
  const admin = await browser.newPage({ storageState: sesion('admin') });
  await admin.goto('/dashboard/admin/users');
  await admin.getByRole('button', { name: 'Nuevo Usuario' }).click();
  await admin.getByPlaceholder('e.g., Juan Carlos Pérez').fill(NUEVO.nombre);
  await admin.getByPlaceholder('usuario@ufps.edu.co').fill(NUEVO.correo);
  await admin.getByRole('button', { name: 'Crear Usuario' }).click();

  const aviso = admin.getByText(/Contraseña temporal: /);
  await expect(aviso).toBeVisible();
  const temporal = (await aviso.textContent())!.replace(/.*Contraseña temporal:\s*/, '').trim();
  await expect(admin.getByRole('row', { name: new RegExp(NUEVO.correo) })).toContainText('DOCENTE');
  await admin.close();

  // El usuario nuevo entra con la temporal y el sistema lo lleva a cambiarla
  const nuevo = await browser.newPage();
  await nuevo.goto('/login');
  await nuevo.getByLabel('Correo electrónico').fill(NUEVO.correo);
  await nuevo.getByLabel('Contraseña').fill(temporal);
  await nuevo.getByRole('button', { name: 'Iniciar sesión' }).click();
  await expect(nuevo).toHaveURL(/\/reset-password/);
  await nuevo.close();
});
