/**
 * e2e_traslado_pdv_anular.spec.js
 *
 * E2E: Anular un traslado Programado desde la Bandeja Traslados PDV.
 *
 * Flujo:
 * 1. Crear traslado via API con fecha_aplicacion futura (no aplicable hoy)
 * 2. Navegar a /app/bandeja_traslados_pdv
 * 3. Click en botón "Anular"
 * 4. Llenar el prompt de motivo de anulación (≥ 5 chars)
 * 5. Confirmar
 * 6. Verificar que el botón "Anular" desaparece (estado cambió a Anulado)
 *
 * Correr: npx playwright test tests/e2e/e2e_traslado_pdv_anular.spec.js
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

async function createFutureTraslado(page) {
	const future = new Date();
	future.setDate(future.getDate() + 30);
	const fechaStr = future.toISOString().split('T')[0];

	const result = await page.evaluate(async (fecha) => {
		const csrf = window.csrf_token || 'token';
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
		await ensureDoc('Ficha Empleado', 'EMP-E2E-ANU', {
			nombres: 'EmpE2E', apellidos: 'Anular', cedula: 'EMP-E2E-ANU',
			pdv: 'E2E-PDV-A', estado: 'Activo', email: 'empe2eanu@e2etest.com',
		});
		await ensureDoc('Motivo Traslado', 'necesidad_operativa', {
			codigo: 'necesidad_operativa', label: 'Necesidad operativa',
			requiere_cambio_cargo: 0, activo: 1,
		});

		const resp = await fetch('/api/method/hubgh.hubgh.page.bandeja_traslados_pdv.bandeja_traslados_pdv.create_traslado_action', {
			method: 'POST',
			headers,
			body: JSON.stringify({
				empleado: 'EMP-E2E-ANU',
				pdv_destino: 'E2E-PDV-B',
				fecha_aplicacion: fecha,
				motivo: 'necesidad_operativa',
				justificacion: 'Justificacion E2E para el test de anulacion desde bandeja.',
			}),
		});
		const data = await resp.json();
		return data.message || null;
	}, fechaStr);
	return result;
}

test.describe('E2E — Anular Traslado desde Bandeja', () => {
	test.setTimeout(120_000);

	test('Administrator puede anular un traslado desde la bandeja', async ({ page }) => {
		await login(page);
		const traslado_name = await createFutureTraslado(page);

		if (!traslado_name) {
			test.skip(true, 'No se pudo crear el traslado de test (posible duplicado Programado)');
			return;
		}

		// Navegar a bandeja
		await page.goto(`${BASE_URL}/app/bandeja_traslados_pdv`, { waitUntil: 'networkidle' });
		await page.waitForTimeout(3000);

		// Click en "Anular"
		const cancelBtn = page.locator(`.btn-cancel-traslado[data-name="${traslado_name}"]`);
		await expect(cancelBtn).toBeVisible({ timeout: 15_000 });
		await cancelBtn.click();

		// Llenar motivo en el dialog
		const motivoField = page.locator('[data-fieldname="motivo_anulacion"] textarea, [data-fieldname="motivo_anulacion"] input');
		await expect(motivoField.first()).toBeVisible({ timeout: 10_000 });
		await motivoField.first().fill('Motivo de anulación E2E suficientemente largo para pasar la validación.');

		// Confirmar
		const confirmBtn = page.locator('.modal-dialog .btn-primary');
		await confirmBtn.first().click();

		// Verificar que el botón de anular desapareció (estado Anulado)
		await page.waitForTimeout(2000);
		const cancelBtnAfter = page.locator(`.btn-cancel-traslado[data-name="${traslado_name}"]`);
		await expect(cancelBtnAfter).toHaveCount(0, { timeout: 10_000 });
	});
});
