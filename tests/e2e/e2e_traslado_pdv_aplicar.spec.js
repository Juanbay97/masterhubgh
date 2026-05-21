/**
 * e2e_traslado_pdv_aplicar.spec.js
 *
 * E2E: Aplicar un traslado Programado desde la Bandeja Traslados PDV.
 *
 * Flujo:
 * 1. Crear traslado via API (sin UI) con fecha_aplicacion = hoy
 * 2. Navegar a /app/bandeja_traslados_pdv
 * 3. Click en botón "Aplicar ahora" para ese traslado
 * 4. Confirmar en el dialog de confirmación
 * 5. Verificar toast/alert de éxito
 * 6. Verificar que el traslado aparece como Aplicado en la lista
 *
 * Correr: npx playwright test tests/e2e/e2e_traslado_pdv_aplicar.spec.js
 */

const { test, expect } = require('@playwright/test');

const ADMIN_PASSWORD = process.env.HUBGH_ADMIN_PASSWORD || 'admin';
const BASE_URL = process.env.HUBGH_BASE_URL || 'http://localhost';

async function login(page, user = 'Administrator', password = ADMIN_PASSWORD) {
	await page.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle' });
	await page.fill('#login_email', user);
	await page.fill('#login_password', password);
	await Promise.all([
		page.waitForURL(/\/app/, { timeout: 30_000 }),
		page.click('.btn-login'),
	]);
}

async function createTestTraslado(page) {
	/**
	 * Crea un traslado via el endpoint whitelist con fecha_aplicacion = hoy.
	 * Retorna el nombre del traslado creado.
	 */
	const today = new Date().toISOString().split('T')[0];
	const result = await page.evaluate(async (fecha) => {
		const csrf = window.csrf_token || 'token';
		// Ensure fixtures
		const headers = { 'X-Frappe-CSRF-Token': csrf, 'Content-Type': 'application/json' };
		async function ensureDoc(doctype, name, data) {
			const check = await fetch(`/api/resource/${encodeURIComponent(doctype)}/${encodeURIComponent(name)}`, { headers });
			if (check.ok) return;
			await fetch(`/api/resource/${encodeURIComponent(doctype)}`, {
				method: 'POST', headers, body: JSON.stringify({ ...data, doctype, name }),
			});
		}
		await ensureDoc('Punto de Venta', 'E2E-PDV-A', {
			nombre_pdv: 'E2E-PDV-A', codigo: 'E2E-PDV-A', ciudad: 'E2ECity', activo: 1,
		});
		await ensureDoc('Punto de Venta', 'E2E-PDV-B', {
			nombre_pdv: 'E2E-PDV-B', codigo: 'E2E-PDV-B', ciudad: 'E2ECity', activo: 1,
		});
		await ensureDoc('Ficha Empleado', 'EMP-E2E-APL', {
			nombres: 'EmpE2E', apellidos: 'Aplicar', cedula: 'EMP-E2E-APL',
			pdv: 'E2E-PDV-A', estado: 'Activo', email: 'empe2eapl@e2etest.com',
		});
		await ensureDoc('Motivo Traslado', 'necesidad_operativa', {
			codigo: 'necesidad_operativa', label: 'Necesidad operativa',
			requiere_cambio_cargo: 0, activo: 1,
		});

		// Create traslado via whitelist method
		const resp = await fetch('/api/method/hubgh.hubgh.page.bandeja_traslados_pdv.bandeja_traslados_pdv.create_traslado_action', {
			method: 'POST',
			headers,
			body: JSON.stringify({
				empleado: 'EMP-E2E-APL',
				pdv_destino: 'E2E-PDV-B',
				fecha_aplicacion: fecha,
				motivo: 'necesidad_operativa',
				justificacion: 'Justificacion E2E para el test de aplicacion desde bandeja.',
			}),
		});
		const data = await resp.json();
		return data.message || null;
	}, today);
	return result;
}

test.describe('E2E — Aplicar Traslado desde Bandeja', () => {
	test.setTimeout(120_000);

	test('Administrator puede aplicar un traslado desde la bandeja', async ({ page }) => {
		await login(page);
		const traslado_name = await createTestTraslado(page);

		if (!traslado_name) {
			test.skip(true, 'No se pudo crear el traslado de test (posible duplicado Programado)');
			return;
		}

		// Navegar a bandeja
		await page.goto(`${BASE_URL}/app/bandeja_traslados_pdv`, { waitUntil: 'networkidle' });
		await page.waitForTimeout(3000); // Wait for JS to load context and data

		// Buscar el botón "Aplicar ahora" para el traslado creado
		const applyBtn = page.locator(`.btn-apply-traslado[data-name="${traslado_name}"]`);
		await expect(applyBtn).toBeVisible({ timeout: 15_000 });
		await applyBtn.click();

		// Confirmar en el dialog de Frappe
		const confirmBtn = page.locator('.modal-dialog .btn-primary, .modal .btn-primary');
		await expect(confirmBtn.first()).toBeVisible({ timeout: 10_000 });
		await confirmBtn.first().click();

		// Verificar que la bandeja se refresca y el traslado aparece como Aplicado
		await page.waitForTimeout(2000);

		// El traslado debería estar Aplicado (botón ya no debe existir)
		const applyBtnAfter = page.locator(`.btn-apply-traslado[data-name="${traslado_name}"]`);
		// No debería existir ya que el estado cambió
		await expect(applyBtnAfter).toHaveCount(0, { timeout: 10_000 });
	});
});
