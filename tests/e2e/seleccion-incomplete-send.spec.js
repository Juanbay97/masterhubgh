/*
 * E2E - Seleccion: Envio incompleto a RRLL con motivo obligatorio (T-21)
 *
 * Cubre:
 *   1. Candidato con docs incompletos: click "Enviar a RRLL (incompleto)" muestra
 *      el dialog con alerta de docs faltantes y campo motivo obligatorio.
 *   2. Intentar confirmar con motivo vacio: el dialog NO cierra (reqd:1 bloquea).
 *   3. Confirmar con motivo valido: llama a send_to_labor_relations con el motivo
 *      y muestra el mensaje de exito.
 *   4. Candidato con docs completos: dialog NO tiene el campo motivo ni alerta.
 *
 * Requiere fixture sembrada via:
 *   bench --site hubgh.local execute hubgh.hubgh.tests._seed_incomplete_send_e2e.seed
 *
 * ENV (todas opcionales, pero recomendadas para CI):
 *   HUBGH_E2E_USER_SELECCION         - usuario rol HR Selection
 *   HUBGH_E2E_PASS_SELECCION
 *   HUBGH_E2E_CAND_INCOMPLETE        - cedula del candidato incompleto (con concepto Favorable + SAGRILAFT)
 *   HUBGH_E2E_CAND_COMPLETE          - cedula del candidato con docs completos
 *   HUBGH_E2E_RUN_INCOMPLETE_SEND=1  - habilitar la suite (default: fixme)
 */

const { test, expect } = require('@playwright/test');

const SEED_READY = process.env.HUBGH_E2E_RUN_INCOMPLETE_SEND === '1';

const USER_SELECCION = process.env.HUBGH_E2E_USER_SELECCION || 'test.seleccion@hubgh-test.local';
const PASS_SELECCION = process.env.HUBGH_E2E_PASS_SELECCION || 'Hubgh-E2E-TestSeleccion-2026';
const CAND_INCOMPLETE = process.env.HUBGH_E2E_CAND_INCOMPLETE || '9100000001';
const CAND_COMPLETE = process.env.HUBGH_E2E_CAND_COMPLETE || '9100000002';

const ADMIN_PASSWORD = process.env.HUBGH_ADMIN_PASSWORD || 'admin';


async function login(page, baseURL, user, pass) {
	await page.goto(`${baseURL}/login`, { waitUntil: 'domcontentloaded' });
	const usrInput = page.locator('#login_email, input[name="usr"], input[name="email"]').first();
	const pwdInput = page.locator('#login_password, input[name="pwd"], input[name="password"]').first();
	await usrInput.waitFor({ state: 'visible', timeout: 30_000 });
	await usrInput.fill(user);
	await pwdInput.fill(pass);
	await page.locator('.btn-login, button:has-text("Iniciar sesión"), button:has-text("Login")').first().click();
	await page.waitForURL(/\/app(\/.*)?$/, { timeout: 30_000 });
}


async function navigateToSeleccion(page, baseURL) {
	await page.goto(`${baseURL}/app/seleccion_documentos`, { waitUntil: 'networkidle' });
	// Wait for at least one card to render
	await page.locator('.hubgh-card').first().waitFor({ state: 'visible', timeout: 30_000 });
}


/**
 * Find the hubgh-card for a candidate by cedula (numero_documento shown as "CC XXXXX")
 */
async function findCardByCedula(page, cedula) {
	return page.locator(`.hubgh-card:has-text("CC ${cedula}")`).first();
}


/**
 * Trigger the hidden .action-send button for a candidate by clicking the primary action button.
 * The primary button routes to action-send via data-action="send".
 */
async function clickSendActionForCandidate(page, cedula) {
	const card = await findCardByCedula(page, cedula);
	// Click the primary action button with data-action="send"
	await card.locator('button.action-primary[data-action="send"]').click();
}


test.describe('Seleccion: envio incompleto a RRLL', () => {
	test.beforeEach(async ({ page, baseURL }) => {
		if (!SEED_READY) {
			test.fixme(true, 'Set HUBGH_E2E_RUN_INCOMPLETE_SEND=1 and seed via bench execute hubgh.hubgh.tests._seed_incomplete_send_e2e.seed');
		}
		await login(page, baseURL, USER_SELECCION, PASS_SELECCION);
		await navigateToSeleccion(page, baseURL);
	});

	test('T-21a: dialog shows missing-docs alert and motivo field for incomplete candidate', async ({ page, baseURL }) => {
		test.setTimeout(90_000);

		await clickSendActionForCandidate(page, CAND_INCOMPLETE);

		// Dialog must appear
		const dialog = page.locator('.modal-dialog').last();
		await expect(dialog).toBeVisible({ timeout: 15_000 });

		// Title should signal incomplete state
		await expect(dialog.locator('.modal-title')).toContainText('incompleto');

		// Alert block listing missing docs must be visible
		await expect(dialog.locator('.sel-docs-note')).toBeVisible();
		await expect(dialog.locator('.sel-docs-note')).toContainText('Documentación incompleta');

		// Motivo textarea must be present
		const motivoField = dialog.locator('[data-fieldname="motivo"] textarea, [data-fieldname="motivo"] input');
		await expect(motivoField).toBeVisible();

		// reqd indicator should exist (Frappe marks required fields)
		const motivoWrapper = dialog.locator('[data-fieldname="motivo"]');
		await expect(motivoWrapper).toBeVisible();
	});

	test('T-21b: submit with empty motivo does not close dialog', async ({ page, baseURL }) => {
		test.setTimeout(90_000);

		await clickSendActionForCandidate(page, CAND_INCOMPLETE);

		const dialog = page.locator('.modal-dialog').last();
		await expect(dialog).toBeVisible({ timeout: 15_000 });

		// Fill required pdv/fecha/cargo fields but leave motivo empty
		const pdvInput = dialog.locator('[data-fieldname="pdv_destino"] input').first();
		if (await pdvInput.isVisible()) {
			await pdvInput.fill('PDV Test');
		}

		// Click primary action (Enviar) without filling motivo
		await dialog.locator('.btn-modal-primary, button.btn-primary:has-text("Enviar")').first().click();

		// Dialog should still be visible (reqd:1 prevents submission)
		await expect(dialog).toBeVisible();
	});

	test('T-21c: submit with valid motivo calls send_to_labor_relations and shows success', async ({ page, baseURL }) => {
		test.setTimeout(90_000);

		await clickSendActionForCandidate(page, CAND_INCOMPLETE);

		const dialog = page.locator('.modal-dialog').last();
		await expect(dialog).toBeVisible({ timeout: 15_000 });

		// Fill pdv_destino and fecha
		const pdvInput = dialog.locator('[data-fieldname="pdv_destino"] input').first();
		await pdvInput.waitFor({ state: 'visible', timeout: 10_000 });
		await pdvInput.fill('PDV Test');
		await pdvInput.press('Tab');

		const fechaInput = dialog.locator('[data-fieldname="fecha_tentativa_ingreso"] input').first();
		if (await fechaInput.isVisible()) {
			await fechaInput.fill('2026-08-01');
		}

		// Fill cargo
		const cargoInput = dialog.locator('[data-fieldname="cargo"] input').first();
		if (await cargoInput.isVisible()) {
			await cargoInput.fill('Cajero');
			await cargoInput.press('Tab');
		}

		// Fill motivo
		const motivoField = dialog.locator('[data-fieldname="motivo"] textarea').first();
		await motivoField.waitFor({ state: 'visible', timeout: 10_000 });
		await motivoField.fill('Urgencia operativa — PDV apertura inminente');

		// Intercept the send_to_labor_relations API call
		const [apiResponse] = await Promise.all([
			page.waitForResponse(
				resp => resp.url().includes('send_to_labor_relations') && resp.status() === 200,
				{ timeout: 30_000 },
			),
			dialog.locator('.btn-modal-primary, button.btn-primary:has-text("Enviar")').first().click(),
		]);

		const json = await apiResponse.json();
		expect(json._server_messages).toBeFalsy();

		// Success alert should appear
		await expect(page.locator('.alert-message-container, .frappe-alert')).toContainText('incompleta', { timeout: 15_000 });
	});

	test('T-21d: complete candidate send dialog has NO motivo field', async ({ page, baseURL }) => {
		test.setTimeout(90_000);

		await clickSendActionForCandidate(page, CAND_COMPLETE);

		const dialog = page.locator('.modal-dialog').last();
		await expect(dialog).toBeVisible({ timeout: 15_000 });

		// No alert, no motivo field
		await expect(dialog.locator('.sel-docs-note')).not.toBeVisible();
		await expect(dialog.locator('[data-fieldname="motivo"]')).not.toBeVisible();

		// Dialog title should NOT say incompleto
		await expect(dialog.locator('.modal-title')).not.toContainText('incompleto');
	});
});
