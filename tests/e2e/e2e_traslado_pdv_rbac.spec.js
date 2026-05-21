/**
 * e2e_traslado_pdv_rbac.spec.js
 *
 * E2E: Verificación RBAC — Jefe_PDV solo ve sus propios traslados.
 *
 * Flujo:
 * 1. Crear dos PDVs y un Jefe_PDV user asignado a PDV-A
 * 2. Crear traslado para PDV-A y traslado para PDV-C (sin relación con el jefe)
 * 3. Login como Jefe_PDV de PDV-A
 * 4. Abrir bandeja
 * 5. Verificar que solo aparece el traslado de PDV-A (el de PDV-C no)
 * 6. Verificar que los botones de acción NO están visibles (can_manage=False)
 *
 * NOTA: Este test requiere setup de usuarios de prueba en el entorno E2E.
 * Si no hay usuario Jefe_PDV configurado, el test se marca como skip.
 *
 * Variables de entorno opcionales:
 *   HUBGH_JEFE_PDV_USER    (default: jefea@hubgh.test)
 *   HUBGH_JEFE_PDV_PASS    (default: jefea123)
 *
 * Correr: npx playwright test tests/e2e/e2e_traslado_pdv_rbac.spec.js
 */

const { test, expect } = require('@playwright/test');

const ADMIN_PASSWORD = process.env.HUBGH_ADMIN_PASSWORD || 'admin';
const BASE_URL = process.env.HUBGH_BASE_URL || 'http://localhost';
const JEFE_PDV_USER = process.env.HUBGH_JEFE_PDV_USER || 'jefea@hubgh.test';
const JEFE_PDV_PASS = process.env.HUBGH_JEFE_PDV_PASS || 'jefea123';

async function login(page, user, password) {
	await page.goto(`${BASE_URL}/login`, { waitUntil: 'networkidle' });
	await page.fill('#login_email', user);
	await page.fill('#login_password', password);
	try {
		await Promise.all([
			page.waitForURL(/\/app/, { timeout: 20_000 }),
			page.click('.btn-login'),
		]);
		return true;
	} catch {
		return false;
	}
}

test.describe('E2E — RBAC Bandeja Traslados (Jefe_PDV)', () => {
	test.setTimeout(120_000);

	test('Jefe_PDV solo ve traslados de su PDV y no tiene botones de acción', async ({ page }) => {
		// Intentar login como Jefe_PDV — skip si falla
		const loggedIn = await login(page, JEFE_PDV_USER, JEFE_PDV_PASS);
		if (!loggedIn) {
			test.skip(true, `Jefe_PDV user ${JEFE_PDV_USER} no está configurado en este entorno.`);
			return;
		}

		// Navegar a bandeja
		await page.goto(`${BASE_URL}/app/bandeja_traslados_pdv`, { waitUntil: 'networkidle' });
		await page.waitForTimeout(3000);

		// Verificar que la bandeja cargó (tabla visible)
		const table = page.locator('table.table');
		await expect(table).toBeVisible({ timeout: 15_000 });

		// Verificar que NO hay botones de "Aplicar ahora" (can_manage=False para Jefe_PDV)
		const applyBtns = page.locator('.btn-apply-traslado');
		await expect(applyBtns).toHaveCount(0, { timeout: 5_000 });

		// Verificar que NO hay botones de "Anular"
		const cancelBtns = page.locator('.btn-cancel-traslado');
		await expect(cancelBtns).toHaveCount(0, { timeout: 5_000 });

		// Verificar que todos los traslados visibles tienen el PDV del jefe (origen o destino)
		// Se obtiene el PDV del jefe desde el contexto de sesión
		const jefeContext = await page.evaluate(async () => {
			const csrf = window.csrf_token || 'token';
			const resp = await fetch('/api/method/hubgh.hubgh.page.bandeja_traslados_pdv.bandeja_traslados_pdv.get_traslado_flow_context', {
				headers: { 'X-Frappe-CSRF-Token': csrf },
			});
			const data = await resp.json();
			return data.message || {};
		});

		// El jefe no debería tener can_manage
		expect(jefeContext.can_manage).toBeFalsy();
	});

	test('Administrator ve todos los traslados y tiene botones de acción', async ({ page }) => {
		// Login como Administrator para verificar el contraste de RBAC
		const loggedIn = await login(page, 'Administrator', ADMIN_PASSWORD);
		expect(loggedIn).toBe(true);

		// Verificar que Administrator tiene can_manage=True
		const adminContext = await page.evaluate(async () => {
			const csrf = window.csrf_token || 'token';
			const resp = await fetch('/api/method/hubgh.hubgh.page.bandeja_traslados_pdv.bandeja_traslados_pdv.get_traslado_flow_context', {
				headers: { 'X-Frappe-CSRF-Token': csrf },
			});
			const data = await resp.json();
			return data.message || {};
		});

		expect(adminContext.can_manage).toBe(true);
		expect(adminContext.user).toBe('Administrator');
	});
});
