import { expect, test } from '@playwright/test';
import { CONTRASENA } from './datos';

const API = 'http://127.0.0.1:8001/api/usuarios';

async function tokenAdministrador(request: import('@playwright/test').APIRequestContext) {
  const respuesta = await request.post(`${API}/login/`, {
    data: { email: 'admin@ufps.edu.co', password: CONTRASENA },
  });
  expect(respuesta.ok()).toBeTruthy();
  return (await respuesta.json()).token as string;
}

test.beforeEach(async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('Correo electrónico').fill('1152001@ufps.edu.co');
  await page.getByLabel('Contraseña').fill(CONTRASENA);
  await page.getByRole('button', { name: 'Iniciar sesión' }).click();
  await expect(page).toHaveURL(/\/dashboard\/portal$/, { timeout: 15_000 });
});

test('el estudiante consulta riesgo, alertas, asistencia y acompañamiento', async ({ page }) => {
  await expect(page.getByRole('heading', { name: 'Hola, Ana Pérez' })).toBeVisible();
  for (const [ruta, titulo] of [
    ['alertas', 'Mis alertas'], ['asistencia', 'Mi asistencia'], ['acompanamiento', 'Mi acompañamiento'],
  ]) {
    await page.goto(`/dashboard/portal/${ruta}`);
    await expect(page.getByRole('heading', { name: titulo, exact: true })).toBeVisible();
    await expect(page.getByText('Carla Ruiz', { exact: true })).toHaveCount(0);
  }
  await page.goto('/dashboard/admin/users');
  await expect(page.getByRole('heading', { name: 'Gestión de Usuarios' })).toHaveCount(0);
});

test('la API impide consultar datos del personal y alertas de otro estudiante', async ({ page }) => {
  const respuestas = await page.evaluate(async () => {
    const token = JSON.parse(localStorage.getItem('user')!).token;
    const consultar = async (ruta: string) => {
      const respuesta = await fetch(`http://127.0.0.1:8001${ruta}`, { headers: { Authorization: `Bearer ${token}` } });
      return { status: respuesta.status, body: await respuesta.json() };
    };
    return {
      personal: await consultar('/api/usuarios/'),
      propias: await consultar('/api/portal/alertas/?codigo=1152003'),
    };
  });
  expect(respuestas.personal.status).toBe(403);
  expect(respuestas.propias.status).toBe(200);
  expect(JSON.stringify(respuestas.propias.body)).not.toContain('Carla Ruiz');
  expect(JSON.stringify(respuestas.propias.body)).not.toContain('observaciones');

  const token = await tokenAdministrador(page.request);
  const auditoria = await page.request.get(`${API}/auditoria/?tipo_accion=ACCESO_DENEGADO`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(auditoria.ok()).toBeTruthy();
  const registros = (await auditoria.json()).registros as { usuario_correo: string; detalle: string }[];
  expect(registros.some(registro =>
    registro.usuario_correo === '1152001@ufps.edu.co' && registro.detalle.includes('/api/usuarios/')
  )).toBeTruthy();
});

test('el primer ingreso activa una cuenta de estudiante sin revelar si el correo existe', async ({ page }) => {
  const token = await tokenAdministrador(page.request);
  const headers = { Authorization: `Bearer ${token}` };
  const antes = await page.request.get(`${API}/`, { headers });
  expect(antes.ok()).toBeTruthy();
  expect((await antes.json()).usuarios.some((usuario: { correo: string }) => usuario.correo === '1152002@ufps.edu.co')).toBeFalsy();

  const activacion = await page.request.post(`${API}/recuperar-password/`, {
    data: { email: '1152002@ufps.edu.co' },
  });
  const correoInexistente = await page.request.post(`${API}/recuperar-password/`, {
    data: { email: 'desconocido@ufps.edu.co' },
  });
  expect(activacion.status()).toBe(200);
  expect(correoInexistente.status()).toBe(200);
  expect(await activacion.json()).toEqual(await correoInexistente.json());

  const despues = await page.request.get(`${API}/`, { headers });
  expect(despues.ok()).toBeTruthy();
  expect((await despues.json()).usuarios).toEqual(expect.arrayContaining([
    expect.objectContaining({ correo: '1152002@ufps.edu.co', rol: 'ESTUDIANTE' }),
  ]));
});

test('crear y cancelar una solicitud mantiene el estado al recargar', async ({ page }) => {
  await page.goto('/dashboard/portal/acompanamiento');
  await page.getByRole('heading', { name: 'Solicitar acompañamiento' }).waitFor();
  await page.getByLabel('Motivo', { exact: false }).selectOption({ index: 1 });
  await page.getByPlaceholder('Describe brevemente tu situación y el tipo de apoyo que necesitas.').fill(
    'Necesito apoyo académico para organizar mi estudio y mejorar mis resultados en cálculo.',
  );
  await page.getByRole('button', { name: 'Enviar solicitud' }).click();
  await expect(page.getByRole('button', { name: 'Cancelar solicitud', exact: true })).toBeVisible();
  await page.reload();
  page.on('dialog', dialogo => dialogo.accept());
  await page.getByRole('button', { name: 'Cancelar solicitud', exact: true }).click();
  const confirmar = page.getByRole('alertdialog').getByRole('button', { name: 'Confirmar', exact: true });
  if (await confirmar.count()) await confirmar.click();
  await expect(page.getByRole('button', { name: 'Enviar solicitud' })).toBeEnabled();
});
