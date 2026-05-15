/*
 * E2E - Correccion de Datos de Candidato (Batch 7)
 *
 * Cubre:
 *   1. Correccion email pre-contrato (aplica directo).
 *   2. Correccion cedula post-contrato (requiere aprobacion de Gerente GH).
 *   3. Correccion cuenta bancaria con preview PDF (iframe).
 *
 * Requiere fixtures sembradas via:
 *   bench --site hubgh.local execute hubgh.tests._seed_correccion_e2e.seed
 *
 * ENV (todas opcionales pero recomendadas):
 *   HUBGH_E2E_USER_SELECCION       - usuario rol HR Selection
 *   HUBGH_E2E_PASS_SELECCION
 *   HUBGH_E2E_USER_GERENTE         - usuario rol Gerente GH
 *   HUBGH_E2E_PASS_GERENTE
 *   HUBGH_E2E_CANDIDATO_PRE        - cedula del Candidato pre-contrato
 *   HUBGH_E2E_CANDIDATO_POST       - cedula del Candidato con contrato activo
 *   HUBGH_E2E_CANDIDATO_BANK       - cedula del Candidato con cert bancaria
 *   HUBGH_E2E_RUN_CORRECCION=1     - habilitar la suite (default: fixme)
 */

const { test, expect } = require('@playwright/test');

const SEED_READY = process.env.HUBGH_E2E_RUN_CORRECCION === '1';

const USER_SELECCION = process.env.HUBGH_E2E_USER_SELECCION || 'test.seleccion@hubgh-test.local';
const PASS_SELECCION = process.env.HUBGH_E2E_PASS_SELECCION || 'Hubgh-E2E-TestSeleccion-2026';
const USER_GERENTE = process.env.HUBGH_E2E_USER_GERENTE || 'test.gerente@hubgh-test.local';
const PASS_GERENTE = process.env.HUBGH_E2E_PASS_GERENTE || 'Hubgh-E2E-TestGerente-2026';
const CAND_PRE = process.env.HUBGH_E2E_CANDIDATO_PRE || '9000000001';
const CAND_POST = process.env.HUBGH_E2E_CANDIDATO_POST || '9000000002';
const CAND_BANK = process.env.HUBGH_E2E_CANDIDATO_BANK || '9000000003';


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


async function logout(page, baseURL) {
	await page.goto(`${baseURL}/api/method/logout`);
}


/**
 * Abre el dialog de Correccion de Datos para un candidato desde su bandeja custom.
 * Las bandejas son SPAs con cards .hubgh-card; el boton "Corregir datos" lleva
 * data-c=<cedula>. La clase varia entre bandejas:
 *   - seleccion_documentos -> .action-correccion
 *   - bandeja_contratacion -> .btn-correccion
 */
async function openCorreccionDialogForCandidato(page, baseURL, bandejaSlug, candidatoName) {
	await page.goto(`${baseURL}/app/${bandejaSlug}`, { waitUntil: 'domcontentloaded' });

	// Las bandejas custom hacen frappe.call asincrono y montan cards via $root.html(...).
	// El backend recorre todos los candidatos -> puede tardar 30-60s con dataset real.
	// Esperar al boton del candidato directamente (mucho mas robusto que .hubgh-card).
	const button = page.locator(
		`.action-correccion[data-c="${candidatoName}"], .btn-correccion[data-c="${candidatoName}"]`
	).first();
	await button.waitFor({ state: 'visible', timeout: 90_000 });
	await button.scrollIntoViewIfNeeded();
	await button.click();

	// Frappe ui.Dialog renderiza como .modal con .modal-dialog dentro.
	const modal = page.locator('.modal.show, .modal:visible').first();
	await modal.waitFor({ state: 'visible', timeout: 15_000 });
	await expect(modal.locator('.modal-title')).toContainText(/Corregir datos/i);

	return modal;
}


async function getCandidatoField(page, baseURL, candidatoName, fieldname) {
	// frappe.client.get devuelve el doc completo — mas robusto que get_value
	// que tiene quirks con fieldname array/string en Frappe v15.
	const url = `${baseURL}/api/method/frappe.client.get`
		+ `?doctype=Candidato`
		+ `&name=${encodeURIComponent(candidatoName)}`;
	const response = await page.request.get(url);
	if (response.status() !== 200) return null;
	const body = await response.json();
	return (body && body.message && body.message[fieldname]) || null;
}


async function waitForBannerPhase(modal) {
	// El banner inicialmente dice "Detectando fase...". Esperar a que termine
	// (texto "Fase: pre_contrato" o "Fase: post_contrato").
	const banner = modal.locator('.hubgh-corr-banner');
	await expect(banner).toBeVisible({ timeout: 10_000 });
	await expect(banner).toContainText(/Fase: (pre|post)_contrato/i, { timeout: 20_000 });
	return banner;
}


async function selectCampo(modal, value) {
	// El field "campo" es un Select estandar de Frappe -> selector real
	// se renderiza como <select> dentro de [data-fieldname="campo"].
	const select = modal.locator('[data-fieldname="campo"] select').first();
	await select.waitFor({ state: 'visible', timeout: 10_000 });
	await select.selectOption(value);
}


async function fillMotivo(modal, text) {
	const motivo = modal.locator('[data-fieldname="motivo"] textarea').first();
	await motivo.waitFor({ state: 'visible', timeout: 10_000 });
	await motivo.fill(text);
}


test.describe('Correccion Datos Candidato - E2E', () => {
	test.beforeEach(async () => {
		if (!SEED_READY) {
			test.fixme(true, 'Requiere fixtures sembradas (HUBGH_E2E_RUN_CORRECCION=1).');
		}
	});

	test('1) Corrige email pre-contrato y aplica directo', async ({ page, baseURL }) => {
		test.setTimeout(120_000);
		await login(page, baseURL, USER_SELECCION, PASS_SELECCION);
		const modal = await openCorreccionDialogForCandidato(
			page, baseURL, 'seleccion_documentos', CAND_PRE
		);

		// Banner debe indicar pre-contrato (azul, sin clase .is-post).
		const banner = await waitForBannerPhase(modal);
		await expect(banner).not.toHaveClass(/is-post/);
		await expect(banner).toContainText(/pre_contrato/i);

		await selectCampo(modal, 'email');

		const nuevoEmail = `corr.${Date.now()}@example.com`;
		await modal.locator('[data-fieldname="valor_nuevo_email"] input').first().fill(nuevoEmail);
		await fillMotivo(modal, 'Email tipeado mal en onboarding');

		// El boton primario de un frappe.ui.Dialog vive en .modal-footer.
		// Su label es "Aplicar correccion" en pre-contrato (lo seteo el dialog).
		await modal.locator('.modal-footer .btn-primary').click();

		// Polling al API: el valor persiste tras submit exitoso. Mas robusto
		// que mirar el modal (Bootstrap deja .modal.show flotando en DOM).
		await expect.poll(
			() => getCandidatoField(page, baseURL, CAND_PRE, 'email'),
			{ timeout: 20_000, intervals: [500, 1000, 2000] }
		).toBe(nuevoEmail);
	});

	test('2) Corrige cedula post-contrato - requiere aprobacion de Gerente GH', async ({ page, baseURL }) => {
		test.setTimeout(180_000);
		await login(page, baseURL, USER_SELECCION, PASS_SELECCION);
		const modal = await openCorreccionDialogForCandidato(
			page, baseURL, 'bandeja_contratacion', CAND_POST
		);

		const banner = await waitForBannerPhase(modal);
		await expect(banner).toHaveClass(/is-post/);
		await expect(banner).toContainText(/post_contrato/i);

		await selectCampo(modal, 'cedula');

		const nuevaCedula = `10${Date.now().toString().slice(-7)}`;
		await modal.locator('[data-fieldname="valor_nuevo_cedula"] input').first().fill(nuevaCedula);
		await fillMotivo(modal, 'Cedula erronea capturada en seleccion');

		// En post-contrato, el dialog reetiqueta el primary action a "Solicitar aprobacion".
		// Tras submit exitoso se crea un doc Correccion Datos Candidato pendiente.
		await modal.locator('.modal-footer .btn-primary').click();

		// Esperar a que aparezca la correccion pendiente (signal de que el
		// submit cuajo) antes de logout.
		await expect.poll(async () => {
			const url = `${baseURL}/api/method/frappe.client.get_count`
				+ `?doctype=${encodeURIComponent('Correccion Datos Candidato')}`
				+ `&filters=${encodeURIComponent(JSON.stringify({
					candidato: CAND_POST,
					workflow_state: 'Pendiente Aprobación',
				}))}`;
			const r = await page.request.get(url);
			const b = await r.json();
			return (b && b.message) || 0;
		}, { timeout: 20_000, intervals: [500, 1000, 2000] }).toBeGreaterThan(0);

		await logout(page, baseURL);

		// Paso B: Gerente GH aprueba via lista de Correccion Datos Candidato.
		await login(page, baseURL, USER_GERENTE, PASS_GERENTE);

		// Buscar la correccion pendiente mas reciente por API y abrirla por nombre.
		const findUrl = `${baseURL}/api/method/frappe.client.get_list`
			+ `?doctype=${encodeURIComponent('Correccion Datos Candidato')}`
			+ `&filters=${encodeURIComponent(JSON.stringify({
				candidato: CAND_POST,
				workflow_state: 'Pendiente Aprobación',
			}))}`
			+ `&fields=${encodeURIComponent(JSON.stringify(['name']))}`
			+ `&order_by=creation desc&limit_page_length=1`;
		const resp = await page.request.get(findUrl);
		const body = await resp.json();
		const correccionName = body && body.message && body.message[0] && body.message[0].name;
		expect(correccionName, 'No se encontro Correccion pendiente para el candidato POST').toBeTruthy();

		await page.goto(
			`${baseURL}/app/correccion-datos-candidato/${encodeURIComponent(correccionName)}`,
			{ waitUntil: 'domcontentloaded' }
		);
		await page.waitForLoadState('networkidle');

		// Aprobar via API: usamos el endpoint custom `approve_correction` del feature
		// (ese es el flow oficial que la UI dispararia tambien). Pasa por
		// before_submit -> apply_correction -> cascada.
		await page.waitForLoadState('networkidle');
		const csrfToken = await page.evaluate(() => (window.frappe && window.frappe.csrf_token) || '');
		const approveResp = await page.request.post(
			`${baseURL}/api/method/hubgh.hubgh.api.correcciones.approve_correction`,
			{
				form: { correccion_name: correccionName },
				headers: { 'X-Frappe-CSRF-Token': csrfToken },
			}
		);
		if (approveResp.status() !== 200) {
			throw new Error(`approve_correction fallo: HTTP ${approveResp.status()} ${await approveResp.text()}`);
		}
		const approveBody = await approveResp.json();
		// El endpoint devuelve `{message: {name, status, afectados}}`.
		expect(approveBody.message && approveBody.message.status,
			`Esperaba status=applied, recibi: ${JSON.stringify(approveBody)}`).toBe('applied');

		// Verifica la cascada via el resumen `afectados` que devuelve el endpoint.
		// _apply_cedula_change setea candidato_new = nueva_cedula tras rename_doc.
		const afectados = approveBody.message.afectados || {};
		expect(afectados.candidato_new,
			`Esperaba candidato_new=${nuevaCedula}, recibi afectados: ${JSON.stringify(afectados)}`)
			.toBe(nuevaCedula);
		// Sanity check: el rename movió el Candidato. La cédula vieja ya no existe
		// como name de Candidato (el FK fue renombrado por Frappe rename_doc).
		expect(afectados.candidato_old).toBe(CAND_POST);
	});

	test('3) Corrige cuenta bancaria con preview PDF visible', async ({ page, baseURL }) => {
		test.setTimeout(120_000);
		await login(page, baseURL, USER_SELECCION, PASS_SELECCION);
		const modal = await openCorreccionDialogForCandidato(
			page, baseURL, 'seleccion_documentos', CAND_BANK
		);

		await waitForBannerPhase(modal);

		await selectCampo(modal, 'cuenta_bancaria');

		// El iframe del PDF se renderiza dentro de .hubgh-corr-bank-wrap una vez
		// que get_bank_cert_url responde.
		const iframe = modal.locator('.hubgh-corr-bank-wrap iframe').first();
		await expect(iframe).toBeVisible({ timeout: 20_000 });
		const iframeSrc = await iframe.getAttribute('src');
		expect(iframeSrc, 'El iframe del PDF debe apuntar a un archivo .pdf').toMatch(/\.pdf/i);

		// Los inputs bancarios son HTML custom (no Frappe controls salvo banco).
		const nuevoNumero = `9${Date.now().toString().slice(-9)}`;
		await modal.locator('.hubgh-corr-numero').first().fill(nuevoNumero);
		await modal.locator('.hubgh-corr-tipo').first().selectOption('Ahorros');

		// Banco siesa se renderiza via frappe.ui.form.make_control en el host
		// .hubgh-corr-banco-host. Buscar el input de autocomplete y elegir el
		// primer valor disponible.
		const bancoHost = modal.locator('.hubgh-corr-banco-host').first();
		const bancoInput = bancoHost.locator('input.input-with-feedback, input[data-fieldname="banco_siesa"], input').first();
		await bancoInput.waitFor({ state: 'visible', timeout: 10_000 });

		// Tomar el primer banco existente via API y setearlo.
		const bancosResp = await page.request.get(
			`${baseURL}/api/method/frappe.client.get_list`
			+ `?doctype=${encodeURIComponent('Banco Siesa')}`
			+ `&fields=${encodeURIComponent(JSON.stringify(['name']))}`
			+ `&limit_page_length=1`
		);
		const bancosBody = await bancosResp.json();
		const bancoName = bancosBody && bancosBody.message && bancosBody.message[0] && bancosBody.message[0].name;
		expect(bancoName, 'Debe existir al menos un Banco Siesa').toBeTruthy();

		await bancoInput.fill(bancoName);
		// Esperar dropdown y elegir la opcion exacta (awesomplete).
		await page.waitForTimeout(500);
		await page.keyboard.press('Tab');

		await fillMotivo(modal, 'Cuenta actualizada segun cert bancaria');

		await modal.locator('.modal-footer .btn-primary').click();

		await expect.poll(
			() => getCandidatoField(page, baseURL, CAND_BANK, 'numero_cuenta_bancaria'),
			{ timeout: 20_000, intervals: [500, 1000, 2000] }
		).toBe(nuevoNumero);
	});
});
