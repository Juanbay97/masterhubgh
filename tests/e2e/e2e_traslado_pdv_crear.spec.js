/**
 * e2e_traslado_pdv_crear.spec.js
 *
 * E2E: Crear un Traslado PDV desde la UI de Frappe.
 *
 * Flujo:
 * 1. Login como Administrator
 * 2. Navegar a /app/traslado-pdv/new
 * 3. Llenar campos obligatorios (empleado, pdv_destino, fecha_aplicacion, motivo, justificacion)
 * 4. Guardar
 * 5. Verificar redirect al doc guardado (URL contiene /app/traslado-pdv/TRAS-)
 * 6. Verificar que el estado del doc es Programado
 *
 * Nota: Email Queue no se verifica aquí porque depende de configuración de
 * SMTP en el entorno CI. Para verificar los 3 emails use:
 *   frappe.db.get_all("Email Queue", filters={"status": ["!=", "Sent"]}) en una sesión Frappe.
 *
 * Pre-requisitos en el sitio:
 * - Empleado activo con cedula "EMP-E2E-001" en PDV "E2E-PDV-A"
 * - PDV "E2E-PDV-B" existe
 * - Motivo Traslado "necesidad_operativa" activo
 *
 * Correr: npx playwright test tests/e2e/e2e_traslado_pdv_crear.spec.js
 * Base URL: process.env.HUBGH_BASE_URL (default: http://localhost)
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

async function ensureTestData(page) {
	/**
	 * Crea los fixtures necesarios via API Frappe si no existen.
	 * Se ejecuta una sola vez por suite.
	 */
	await page.evaluate(async () => {
		const csrf = window.csrf_token || 'token';
		const headers = { 'X-Frappe-CSRF-Token': csrf, 'Content-Type': 'application/json' };

		async function ensureDoc(doctype, name, data) {
			const check = await fetch(`/api/resource/${encodeURIComponent(doctype)}/${encodeURIComponent(name)}`, { headers });
			if (check.ok) return;
			await fetch(`/api/resource/${encodeURIComponent(doctype)}`, {
				method: 'POST',
				headers,
				body: JSON.stringify({ ...data, doctype, name }),
			});
		}

		await ensureDoc('Punto de Venta', 'E2E-PDV-A', {
			nombre_pdv: 'E2E-PDV-A', codigo: 'E2E-PDV-A', ciudad: 'E2ECity', activo: 1,
		});
		await ensureDoc('Punto de Venta', 'E2E-PDV-B', {
			nombre_pdv: 'E2E-PDV-B', codigo: 'E2E-PDV-B', ciudad: 'E2ECity', activo: 1,
		});
		await ensureDoc('Ficha Empleado', 'EMP-E2E-001', {
			nombres: 'EmpE2E', apellidos: 'Crear', cedula: 'EMP-E2E-001',
			pdv: 'E2E-PDV-A', estado: 'Activo', email: 'empe2e001@e2etest.com',
		});
		await ensureDoc('Motivo Traslado', 'necesidad_operativa', {
			codigo: 'necesidad_operativa', label: 'Necesidad operativa',
			requiere_cambio_cargo: 0, activo: 1,
		});
	});
}

test.describe('E2E — Crear Traslado PDV', () => {
	test.setTimeout(120_000);

	test('Administrator puede crear un traslado desde la UI y queda en Programado', async ({ page }) => {
		await login(page);
		await ensureTestData(page);

		// 1. Navegar a nuevo traslado
		await page.goto(`${BASE_URL}/app/traslado-pdv/new`, { waitUntil: 'networkidle' });

		// 2. Llenar Empleado
		await page.waitForSelector('[data-fieldname="empleado"] input', { timeout: 15_000 });
		await page.fill('[data-fieldname="empleado"] input', 'EMP-E2E-001');
		await page.keyboard.press('Tab');
		await page.waitForTimeout(500);

		// 3. Llenar PDV Destino
		await page.fill('[data-fieldname="pdv_destino"] input', 'E2E-PDV-B');
		await page.keyboard.press('Tab');
		await page.waitForTimeout(500);

		// 4. Llenar Fecha Aplicación (mañana)
		const tomorrow = new Date();
		tomorrow.setDate(tomorrow.getDate() + 1);
		const fechaStr = tomorrow.toISOString().split('T')[0];
		await page.fill('[data-fieldname="fecha_aplicacion"] input', fechaStr);
		await page.keyboard.press('Tab');

		// 5. Llenar Motivo
		await page.fill('[data-fieldname="motivo"] input', 'necesidad_operativa');
		await page.keyboard.press('Tab');
		await page.waitForTimeout(500);

		// 6. Llenar Justificación (mínimo 20 caracteres)
		await page.fill('[data-fieldname="justificacion"] textarea', 'Justificacion E2E con suficientes caracteres para pasar la validacion del servidor.');

		// 7. Guardar
		await page.click('.page-icon-group .btn-primary, [data-label="Save"]');
		await page.waitForTimeout(2000);

		// 8. Verificar URL apunta a un doc guardado
		await expect(page).toHaveURL(/\/app\/traslado-pdv\/TRAS-/, { timeout: 15_000 });

		// 9. Verificar estado = Programado (puede estar en el formulario o en un campo readonly)
		const estadoEl = page.locator('[data-fieldname="estado"] .control-value, [data-fieldname="estado"] input');
		await expect(estadoEl.first()).toContainText('Programado', { timeout: 10_000 });
	});
});
