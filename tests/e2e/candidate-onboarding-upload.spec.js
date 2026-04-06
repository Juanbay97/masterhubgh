const path = require('path');
const os = require('os');
const { test, expect } = require('@playwright/test');


function resolveUploadFile() {
	if (process.env.HUBGH_E2E_UPLOAD_FILE) {
		return process.env.HUBGH_E2E_UPLOAD_FILE;
	}

	const userDocument = path.join(os.homedir(), 'Documents', 'RUT 2026 (Clave 901422345).pdf');
	return userDocument;
}


const fallbackUploadFile = path.resolve(__dirname, '..', 'fixtures', 'sample-upload.pdf');


async function waitForOptions(page, selector, minimum = 2) {
	await page.waitForFunction(
		({ selector, minimum }) => {
			const element = document.querySelector(selector);
			return Boolean(element && element.options && element.options.length >= minimum);
		},
		{ selector, minimum },
		{ timeout: 30_000 },
	);
}


async function clickNext(page) {
	await page.locator('#nextBtn').click();
	await page.waitForTimeout(250);
}


test('candidate can onboard, login and upload document', async ({ page, baseURL }) => {
	test.setTimeout(180_000);

	const docId = `99${Date.now().toString().slice(-8)}`;
	const email = `candidate.${docId}@example.com`;
	const preferredUploadFile = resolveUploadFile();
	const uploadFile = preferredUploadFile;

	await page.goto(`${baseURL}/candidato`, { waitUntil: 'networkidle' });

	await page.fill('#nombre', 'E2E');
	await page.fill('#primer_apellido', 'Playwright');
	await page.fill('#segundo_apellido', 'Firefox');
	await page.fill('#cedula', docId);
	await page.selectOption('#tipo_documento', 'Cedula');
	await page.fill('#fecha_nacimiento', '1995-01-15');
	await page.fill('#fecha_expedicion', '2015-01-15');
	await clickNext(page);
	await clickNext(page);

	await waitForOptions(page, '#procedencia_pais');
	await waitForOptions(page, '#banco_siesa');

	await page.fill('#email', email);
	await page.fill('#celular', '3001234567');
	await page.fill('#telefono_fijo', '6011234567');
	await page.fill('#contacto_emergencia_nombre', 'Contacto E2E');
	await page.fill('#contacto_emergencia_telefono', '3007654321');
	await page.selectOption('#procedencia_pais', '169');
	await waitForOptions(page, '#procedencia_departamento');
	const departamento = await page.locator('#procedencia_departamento option:not([value=""])').nth(0).getAttribute('value');
	await page.selectOption('#procedencia_departamento', departamento);
	await waitForOptions(page, '#procedencia_ciudad');
	const ciudadProcedencia = await page.locator('#procedencia_ciudad option:not([value=""])').nth(0).getAttribute('value');
	await page.selectOption('#procedencia_ciudad', ciudadProcedencia);
	const banco = await page.locator('#banco_siesa option:not([value=""])').nth(0).getAttribute('value');
	await page.selectOption('#banco_siesa', banco);
	await page.selectOption('#tipo_cuenta_bancaria', 'Ahorros');
	await page.fill('#numero_cuenta_bancaria', `${docId}01`);
	await clickNext(page);

	await page.selectOption('#ciudad', 'Bogota');
	await page.waitForTimeout(200);
	await page.selectOption('#localidad', { index: 1 });
	await page.fill('#direccion', 'Calle 123 # 45-67');
	await page.fill('#barrio', 'Chico');
	await clickNext(page);

	await page.selectOption('#grupo_sanguineo', 'O+');
	await page.selectOption('#tiene_alergias', '0');
	await page.fill('#personas_a_cargo', '0');
	await page.selectOption('#talla_camisa', 'M');
	await page.selectOption('#talla_delantal', 'M');
	await page.fill('#talla_pantalon', '32');
	await page.fill('#numero_zapatos', '40');
	await page.click('label[for="check-lunes"]');
	await page.fill('#start-lunes', '08:00');
	await page.fill('#end-lunes', '17:00');
	await clickNext(page);

	await page.waitForSelector('#step-6.active');
	await expect(page.locator('#success-message')).toContainText('Excelente');
	const loginUser = (await page.locator('#credential-user').innerText()).trim();
	const loginPassword = (await page.locator('#credential-password').innerText()).trim();
	await expect.soft(page.locator('#credential-user')).not.toHaveText('');
	await expect.soft(page.locator('#credential-password')).not.toHaveText('');

	await page.locator('#loginBtn').click();
	await page.waitForLoadState('networkidle');
	const loginEmail = page.locator('input[placeholder="juan@example.com"], input[placeholder="jane@example.com"], input[name="usr"]');
	const loginPasswordInput = page.locator('input[placeholder="•••••"], input[name="pwd"]');
	const loginSubmit = page.locator('button:has-text("Iniciar sesión"), button:has-text("Login")');
	await loginEmail.first().fill(loginUser);
	await loginPasswordInput.first().fill(loginPassword);
	await loginSubmit.first().click();
	await page.waitForURL(/\/app(\/mis_documentos_candidato)?$/);

	await page.goto(`${baseURL}/app/mis_documentos_candidato`, { waitUntil: 'networkidle' });
	await expect(page.locator('.mis-documentos-candidato')).toBeVisible();
	await expect(page.locator('.doc-card').first()).toBeVisible();

	const uploadButton = page.locator('.action-upload').first();
	const fileChooserPromise = page.waitForEvent('filechooser');
	await uploadButton.click();
	const fileChooser = await fileChooserPromise;
	try {
		await fileChooser.setFiles(uploadFile);
	} catch (error) {
		await fileChooser.setFiles(fallbackUploadFile);
	}

	const uploadResponse = await page.waitForResponse((response) => {
		return response.url().includes('/api/method/hubgh.hubgh.page.mis_documentos_candidato.mis_documentos_candidato.upload_my_document') && response.status() === 200;
	});
	const uploadResponseJson = await uploadResponse.json();

	const firstCard = page.locator('.doc-card').first();
	await expect(firstCard).toContainText('Subido');
	const latestFileLink = firstCard.locator('a[href*="/private/files/"]').last();
	await expect(latestFileLink).toBeVisible();
	await expect(latestFileLink).toHaveAttribute('href', /\/private\/files\/.+\.pdf/i);
	expect(uploadResponseJson._server_messages).toBeFalsy();
	console.log(JSON.stringify({ docId, email, loginUser }, null, 2));
});
