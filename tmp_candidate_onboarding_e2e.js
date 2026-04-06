const { firefox } = require('playwright');

async function waitForOptions(page, selector, minimum = 2) {
  await page.waitForFunction(
    ({ selector, minimum }) => {
      const el = document.querySelector(selector);
      return !!el && el.options && el.options.length >= minimum;
    },
    { selector, minimum },
    { timeout: 30000 }
  );
}

async function clickNext(page) {
  await page.locator('#nextBtn').click();
  await page.waitForTimeout(300);
}

async function main() {
  const docId = `99${Date.now().toString().slice(-8)}`;
  const email = `candidate.${docId}@example.com`;
  const dialogs = [];

  const browser = await firefox.launch({
    headless: true,
  });

  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 } });
  page.on('dialog', async (dialog) => {
    dialogs.push(dialog.message());
    await dialog.accept();
  });

  try {
    await page.goto('http://localhost/candidato', { waitUntil: 'networkidle', timeout: 60000 });

    await page.fill('#nombre', 'E2E');
    await page.fill('#primer_apellido', 'Candidate');
    await page.fill('#segundo_apellido', 'Automation');
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
    await page.fill('#contacto_emergencia_nombre', 'Contacto Prueba');
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
    await page.waitForTimeout(300);
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

    await page.waitForSelector('#step-6.active', { timeout: 60000 });
    const successText = (await page.locator('#success-message').innerText()).trim();
    const loginUser = await page.locator('#credential-user').innerText().catch(() => '');

    console.log(JSON.stringify({
      ok: true,
      docId,
      email,
      successText,
      loginUser: (loginUser || '').trim(),
      dialogs,
    }, null, 2));
  } catch (error) {
    await page.screenshot({ path: `/tmp/candidate-e2e-${docId}.png`, fullPage: true }).catch(() => {});
    console.log(JSON.stringify({
      ok: false,
      docId,
      email,
      dialogs,
      error: String(error && error.stack ? error.stack : error),
      screenshot: `/tmp/candidate-e2e-${docId}.png`,
    }, null, 2));
    process.exitCode = 1;
  } finally {
    await browser.close();
  }
}

main();
