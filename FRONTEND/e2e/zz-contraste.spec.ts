import { expect, test } from '@playwright/test';
import { readFileSync } from 'fs';
import { createRequire } from 'module';
import { CONTRASENA, sesion, type Rol } from './datos';

const require = createRequire(import.meta.url);
const axeSrc = readFileSync(require.resolve('axe-core/axe.min.js'), 'utf-8');

const RUTAS: Array<[Rol | 'estudiante', string]> = [
  ['admin', '/dashboard/admin/import'], ['admin', '/dashboard/admin/risk-rules'], ['admin', '/dashboard/admin/users'],
  ['admin', '/dashboard/admin/audit-log'], ['admin', '/dashboard/students'], ['admin', '/dashboard/students/1152001'],
  ['admin', '/dashboard/alerts'], ['admin', '/dashboard/reports'], ['admin', '/dashboard/courses'],
  ['admin', '/dashboard/notifications'], ['admin', '/dashboard/ayuda'], ['admin', '/dashboard/admin/automatic-processes'],
  ['director', '/dashboard/director'], ['docente', '/dashboard/teacher'], ['bienestar', '/dashboard/students'],
  ['estudiante', '/dashboard/portal'], ['estudiante', '/dashboard/portal/alertas'],
  ['estudiante', '/dashboard/portal/asistencia'], ['estudiante', '/dashboard/portal/acompanamiento'],
];

test.describe('gráficas en móvil', () => {
  test.use({ storageState: sesion('director'), viewport: { width: 360, height: 740 } });
  test('diez semestres conservan etiquetas de 12 px y desplazamiento interno', async ({ page }) => {
    await page.route('**/api/academico/indicadores/', async (ruta) => {
      const respuesta = await ruta.fetch();
      const datos = await respuesta.json();
      datos.distribucion_riesgo = Array.from({ length: 10 }, (_, i) => ({ semester: i + 1, high: 1, medium: 2, low: 3 }));
      await ruta.fulfill({ response: respuesta, json: datos });
    });
    await page.goto('/dashboard/director');
    const grafica = page.getByRole('region', { name: 'Distribución de riesgo por semestre', exact: true });
    const etiquetas = grafica.locator('.recharts-xAxis .recharts-cartesian-axis-tick');
    await expect(etiquetas).toHaveCount(10);
    expect(await grafica.evaluate((nodo) => nodo.scrollWidth > nodo.clientWidth)).toBe(true);
    const cajas = await etiquetas.evaluateAll((nodos) => nodos.map((nodo) => {
      const texto = nodo.querySelector('text')!;
      const caja = texto.getBoundingClientRect();
      return { izquierda: caja.left, derecha: caja.right, tamano: parseFloat(getComputedStyle(texto).fontSize) };
    }));
    for (let i = 0; i < cajas.length; i++) {
      expect(cajas[i].tamano).toBeGreaterThanOrEqual(12);
      if (i) expect(cajas[i].izquierda).toBeGreaterThan(cajas[i - 1].derecha);
    }
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
});

test.describe('preferencia de tema', () => {
  test.use({ storageState: sesion('admin') });
  test('cambia de tema y conserva la elección al recargar', async ({ page }) => {
    await page.emulateMedia({ colorScheme: 'light' });
    await page.goto('/dashboard/admin/import');
    await page.evaluate(() => localStorage.setItem('tema', 'claro'));
    await page.reload();
    await page.getByRole('button', { name: 'Cambiar a modo oscuro' }).click();
    await expect(page.locator('html')).toHaveClass(/dark/);
    expect(await page.evaluate(() => localStorage.getItem('tema'))).toBe('oscuro');
    await page.reload();
    await expect(page.locator('html')).toHaveClass(/dark/);
    await page.getByRole('button', { name: 'Cambiar a modo claro' }).click();
    await page.reload();
    await expect(page.locator('html')).not.toHaveClass(/dark/);
  });
});

for (const tema of ['claro', 'oscuro']) {
  test(`axe contraste ${tema}`, async ({ browser }, testInfo) => {
    test.setTimeout(300_000);
    const resultados: any[] = [];
    for (const [rol, ruta] of RUTAS) {
      const ctx = await browser.newContext({ storageState: rol === 'estudiante' ? undefined : sesion(rol), viewport: { width: rol === 'estudiante' || rol === 'director' ? 360 : 1280, height: 900 } });
      await ctx.addInitScript((t) => { try { localStorage.setItem('tema', t); } catch { /* */ } }, tema);
      const page = await ctx.newPage();
      if (rol === 'estudiante') {
        await page.goto('/login');
        await page.getByLabel('Correo electrónico').fill('1152001@ufps.edu.co');
        await page.getByLabel('Contraseña').fill(CONTRASENA);
        await page.getByRole('button', { name: 'Iniciar sesión' }).click();
        await expect(page).toHaveURL(/\/dashboard\/portal$/);
      }
      await page.goto(ruta);
      await page.waitForLoadState('networkidle');
      if (ruta.endsWith('/1152001')) await expect(page.getByRole('heading', { name: 'Ana Pérez', exact: true })).toBeVisible();
      await page.waitForTimeout(800);
      await page.evaluate(axeSrc);
      const r = await page.evaluate(async () => {
        // @ts-ignore
        const out = await axe.run(document, { runOnly: ['color-contrast'] });
        return out.violations.flatMap((v: any) => v.nodes.map((n: any) => ({
          html: n.html.slice(0, 120), msg: (n.any[0]?.message || '').slice(0, 200),
        })));
      });
      resultados.push({ tema, rol, ruta, n: r.length, nodos: r });
      await ctx.close();
    }
    await testInfo.attach(`contraste-${tema}`, { body: JSON.stringify(resultados, null, 2), contentType: 'application/json' });
    expect(resultados.filter((r) => r.n > 0)).toEqual([]);
  });
}
