/*
 * E2E - Bandeja Contratacion: indicador docs incompletos + accion Subir documento (T-23)
 *
 * Cubre:
 *   1. Candidato con documentacion_incompleta=1 aparece en bandeja con badge
 *      "Documentación incompleta: N faltantes".
 *   2. El boton "Subir documento" esta visible solo para el candidato incompleto.
 *   3. Hacer click en "Subir documento" abre el dialog con selector de tipo de doc.
 *   4. Seleccionar tipo + archivo llama a upload_contratacion_document y el badge
 *      se actualiza (o desaparece si todos los docs fueron subidos).
 *   5. Candidato completo NO tiene el badge ni el boton "Subir documento".
 *
 * Requiere fixture sembrada via:
 *   bench --site hubgh.local execute hubgh.hubgh.tests._seed_incomplete_send_e2e.seed
 *
 * ENV (todas opcionales, pero recomendadas para CI):
 *   HUBGH_E2E_USER_RRLL              - usuario rol HR Labor Relations
 *   HUBGH_E2E_PASS_RRLL
 *   HUBGH_E2E_CAND_INCOMPLETE        - cedula del candidato incompleto ya en bandeja RRLL
 *   HUBGH_E2E_CAND_COMPLETE          - cedula del candidato completo ya en bandeja RRLL
 *   HUBGH_E2E_UPLOAD_FILE            - ruta a PDF de prueba (fallback: tests/fixtures/sample-upload.pdf)
 *   HUBGH_E2E_RUN_BANDEJA_UPLOAD=1   - habilitar la suite (default: fixme)
 */

const path = require('path');
const { test, expect } = require('@playwright/test');

const SEED_READY = process.env.HUBGH_E2E_RUN_BANDEJA_UPLOAD === '1';

const USER_RRLL = process.env.HUBGH_E2E_USER_RRLL || 'test.rrll@hubgh-test.local';
const PASS_RRLL = process.env.HUBGH_E2E_PASS_RRLL || 'Hubgh-E2E-TestRRLL-2026';
const CAND_INCOMPLETE = process.env.HUBGH_E2E_CAND_INCOMPLETE || '9100000001';
const CAND_COMPLETE = process.env.HUBGH_E2E_CAND_COMPLETE || '9100000002';
const UPLOAD_FILE = process.env.HUBGH_E2E_UPLOAD_FILE
	|| path.resolve(__dirname, '..', 'fixtures', 'sample-upload.pdf');


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


async function navigateToBandeja(page, baseURL) {
	await page.goto(`${baseURL}/app/bandeja_contratacion`, { waitUntil: 'networkidle' });
	await page.locator('.hubgh-card').first().waitFor({ state: 'visible', timeout: 30_000 });
}


async function findCardByCedula(page, cedula) {
	return page.locator(`.hubgh-card:has-text("CC ${cedula}")`).first();
}


test.describe('Bandeja contratacion: indicador docs incompletos + subir documento', () => {
	test.beforeEach(async ({ page, baseURL }) => {
		if (!SEED_READY) {
			test.fixme(true, 'Set HUBGH_E2E_RUN_BANDEJA_UPLOAD=1 and seed via bench execute hubgh.hubgh.tests._seed_incomplete_send_e2e.seed');
		}
		await login(page, baseURL, USER_RRLL, PASS_RRLL);
		await navigateToBandeja(page, baseURL);
	});

	test('T-23a: incomplete candidate shows missing-docs badge', async ({ page, baseURL }) => {
		test.setTimeout(90_000);

		const card = await findCardByCedula(page, CAND_INCOMPLETE);
		await expect(card).toBeVisible({ timeout: 15_000 });

		// Badge must be visible and contain "incompleta"
		const badge = card.locator('.incomplete-docs-badge');
		await expect(badge).toBeVisible();
		await expect(badge).toContainText('incompleta');
		// Should mention at least "1 faltante"
		await expect(badge).toContainText('faltante');
	});

	test('T-23b: incomplete candidate has "Subir documento" button', async ({ page, baseURL }) => {
		test.setTimeout(90_000);

		const card = await findCardByCedula(page, CAND_INCOMPLETE);
		await expect(card).toBeVisible({ timeout: 15_000 });

		const uploadBtn = card.locator('button.btn-upload-doc');
		await expect(uploadBtn).toBeVisible();
		await expect(uploadBtn).toContainText('Subir documento');
	});

	test('T-23c: complete candidate has no missing-docs badge and no upload button', async ({ page, baseURL }) => {
		test.setTimeout(90_000);

		const card = await findCardByCedula(page, CAND_COMPLETE);
		await expect(card).toBeVisible({ timeout: 15_000 });

		await expect(card.locator('.incomplete-docs-badge')).not.toBeVisible();
		await expect(card.locator('button.btn-upload-doc')).not.toBeVisible();
	});

	test('T-23d: clicking "Subir documento" opens doc-type picker dialog', async ({ page, baseURL }) => {
		test.setTimeout(90_000);

		const card = await findCardByCedula(page, CAND_INCOMPLETE);
		await expect(card).toBeVisible({ timeout: 15_000 });

		await card.locator('button.btn-upload-doc').click();

		// Dialog should appear with a document_type selector
		const dialog = page.locator('.modal-dialog').last();
		await expect(dialog).toBeVisible({ timeout: 15_000 });
		await expect(dialog.locator('[data-fieldname="document_type"]')).toBeVisible();
		await expect(dialog.locator('.modal-title')).toContainText('documento');
	});

	test('T-23e: uploading a file calls upload_contratacion_document and reloads board', async ({ page, baseURL }) => {
		test.setTimeout(120_000);

		const card = await findCardByCedula(page, CAND_INCOMPLETE);
		await expect(card).toBeVisible({ timeout: 15_000 });

		// Count missing docs before upload
		const badgeBefore = card.locator('.incomplete-docs-badge');
		const badgeTextBefore = await badgeBefore.innerText();
		const countBefore = parseInt((badgeTextBefore.match(/(\d+)\s+faltante/) || [])[1] || '0', 10);
		expect(countBefore).toBeGreaterThan(0);

		await card.locator('button.btn-upload-doc').click();

		const dialog = page.locator('.modal-dialog').last();
		await expect(dialog).toBeVisible({ timeout: 15_000 });

		// Select the first available document type
		const docTypeSelect = dialog.locator('[data-fieldname="document_type"] select').first();
		await docTypeSelect.waitFor({ state: 'visible', timeout: 10_000 });
		await docTypeSelect.selectOption({ index: 0 });

		// Intercept upload_contratacion_document API call
		const [uploadResponse] = await Promise.all([
			page.waitForResponse(
				resp => resp.url().includes('upload_contratacion_document') && resp.status() === 200,
				{ timeout: 60_000 },
			),
			// Click primary and then handle the file picker
			(async () => {
				const fileChooserPromise = page.waitForEvent('filechooser', { timeout: 30_000 });
				await dialog.locator('.btn-modal-primary, button.btn-primary:has-text("Seleccionar archivo")').first().click();
				const fileChooser = await fileChooserPromise;
				await fileChooser.setFiles(UPLOAD_FILE);
			})(),
		]);

		const uploadJson = await uploadResponse.json();
		expect(uploadJson._server_messages).toBeFalsy();

		// Board reloads; wait for cards to re-render
		await page.locator('.hubgh-card').first().waitFor({ state: 'visible', timeout: 30_000 });

		// If all docs were uploaded, badge disappears; otherwise count decrements
		const updatedCard = await findCardByCedula(page, CAND_INCOMPLETE);
		const updatedBadge = updatedCard.locator('.incomplete-docs-badge');
		const isBadgeStillVisible = await updatedBadge.isVisible();
		if (isBadgeStillVisible) {
			const badgeTextAfter = await updatedBadge.innerText();
			const countAfter = parseInt((badgeTextAfter.match(/(\d+)\s+faltante/) || [])[1] || '0', 10);
			expect(countAfter).toBeLessThan(countBefore);
		}
		// If badge is gone, all docs were uploaded — that's also valid.
	});
});
