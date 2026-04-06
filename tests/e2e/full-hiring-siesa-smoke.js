const fs = require('fs');
const path = require('path');
const { firefox } = require('@playwright/test');

const baseUrl = process.env.HUBGH_BASE_URL || 'http://localhost';
const uploadFile = process.env.HUBGH_E2E_UPLOAD_FILE || path.resolve(__dirname, '..', 'fixtures', 'sample-upload.pdf');

const localePatch = `(() => {
  const safeLang = (document.documentElement && document.documentElement.lang) || 'es-CO';
  if (typeof navigator !== 'undefined') {
    try {
      if (!navigator.language || navigator.language === 'undefined') {
        Object.defineProperty(navigator, 'language', { value: safeLang, configurable: true });
      }
      if (!Array.isArray(navigator.languages) || navigator.languages[0] === 'undefined') {
        Object.defineProperty(navigator, 'languages', { value: [safeLang], configurable: true });
      }
    } catch (error) {}
  }
  if (typeof Intl !== 'undefined' && typeof Intl.Locale === 'function' && !Intl.__hubghSafeLocalePatched) {
    const NativeLocale = Intl.Locale;
    const SafeLocale = function(locale, options) {
      return new NativeLocale(locale && locale !== 'undefined' ? locale : safeLang, options);
    };
    SafeLocale.prototype = NativeLocale.prototype;
    Intl.Locale = SafeLocale;
    Intl.__hubghSafeLocalePatched = true;
  }
})();`;

async function waitForOptions(page, selector, minimum = 2) {
  await page.waitForFunction(
    ({ selector, minimum }) => {
      const el = document.querySelector(selector);
      return !!el && !!el.options && el.options.length >= minimum;
    },
    { selector, minimum },
    { timeout: 30000 }
  );
}

async function clickNext(page) {
  await page.locator('#nextBtn').click();
  await page.waitForTimeout(300);
}

async function frappeCall(page, method, args = {}) {
  const result = await page.evaluate(async ({ method, args }) => {
    try {
      const response = await frappe.call({ method, args });
      return { ok: true, message: response && response.message, raw: response };
    } catch (error) {
      return {
        ok: false,
        error: (error && (error.message || error.exc || error._server_messages)) || JSON.stringify(error),
        raw: error || null,
      };
    }
  }, { method, args });
  if (!result.ok) {
    throw new Error(result.error || `frappe.call failed: ${method}`);
  }
  return result.message;
}

async function getCsrfHeader(page) {
  const cookies = await page.context().cookies(baseUrl);
  const csrf = cookies.find((cookie) => cookie.name === 'csrf_token');
  return csrf && csrf.value ? { 'X-Frappe-CSRF-Token': csrf.value } : {};
}

async function postForm(page, url, form = {}) {
  const headers = {
    Accept: 'application/json',
    ...(await getCsrfHeader(page)),
  };
  const response = await page.context().request.post(`${baseUrl}${url}`, { headers, form });
  return await response.json();
}

async function uploadFileForDoc(page, doctype, docname) {
  const headers = {
    Accept: 'application/json',
    ...(await getCsrfHeader(page)),
  };
  const response = await page.context().request.post(`${baseUrl}/api/method/upload_file`, {
    headers,
    multipart: {
      doctype,
      docname,
      is_private: '1',
      file: {
        name: path.basename(uploadFile),
        mimeType: 'application/pdf',
        buffer: fs.readFileSync(uploadFile),
      },
    },
  });
  const json = await response.json();
  return json.message && json.message.file_url;
}

async function browserUploadFile(page, doctype, docname) {
  await page.evaluate(() => {
    if (!document.querySelector('#hubgh-upload-helper')) {
      const input = document.createElement('input');
      input.type = 'file';
      input.id = 'hubgh-upload-helper';
      input.style.display = 'none';
      document.body.appendChild(input);
    }
  });
  await page.setInputFiles('#hubgh-upload-helper', uploadFile);
  return await page.evaluate(async ({ doctype, docname }) => {
    const csrf = (window.frappe && frappe.csrf_token) || window.csrf_token || '';
    const input = document.querySelector('#hubgh-upload-helper');
    const file = input && input.files && input.files[0];
    if (!file) throw new Error('helper_upload_file_missing');
    const formData = new FormData();
    formData.append('doctype', doctype);
    formData.append('docname', docname);
    formData.append('is_private', '1');
    formData.append('file', file, file.name);
    const response = await fetch('/api/method/upload_file', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'X-Frappe-CSRF-Token': csrf, Accept: 'application/json' },
      body: formData,
    });
    const json = await response.json();
    if (!json.message || !json.message.file_url) throw new Error(JSON.stringify(json));
    return json.message.file_url;
  }, { doctype, docname });
}

async function browserPost(page, methodUrl, payload = {}) {
  const result = await page.evaluate(async ({ methodUrl, payload }) => {
    const csrf = (window.frappe && frappe.csrf_token) || window.csrf_token || '';
    const body = new URLSearchParams();
    Object.entries(payload).forEach(([key, value]) => body.append(key, value == null ? '' : String(value)));
    const response = await fetch(methodUrl, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'X-Frappe-CSRF-Token': csrf,
        Accept: 'application/json',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
      },
      body,
    });
    return await response.json();
  }, { methodUrl, payload });
  if (result && (result.exception || result.exc_type || result._server_messages)) {
    throw new Error(result._server_messages || result.exception || result.exc_type);
  }
  return result;
}

async function getFirstName(page, doctype, extra = {}) {
  const rows = await frappeCall(page, 'frappe.client.get_list', {
    doctype,
    fields: ['name'],
    limit_page_length: 5,
    ...extra,
  });
  if (!rows || !rows.length) throw new Error(`No records found for ${doctype}`);
  return rows[0].name;
}

async function dismissOpenModals(page) {
  await page.evaluate(() => {
    document.querySelectorAll('.modal.show .btn-modal-close, .modal.show .modal-header .close, .modal.show .btn-primary').forEach((button) => {
      if (button instanceof HTMLElement && /cerrar|close|ok|aceptar/i.test(button.innerText || '')) {
        button.click();
      }
    });
    document.querySelectorAll('.modal.show').forEach((modal) => {
      modal.classList.remove('show');
      modal.setAttribute('style', 'display:none');
    });
    document.querySelectorAll('.modal-backdrop').forEach((backdrop) => backdrop.remove());
    document.body.classList.remove('modal-open');
  });
}

async function login(page, user, password) {
  await page.goto(`${baseUrl}/login`, { waitUntil: 'networkidle' });
  await page.locator('input[placeholder="juan@example.com"], input[placeholder="jane@example.com"], input[name="usr"]').first().fill(user);
  await page.locator('input[placeholder="•••••"], input[name="pwd"]').first().fill(password);
  await page.locator('button:has-text("Iniciar sesión"), button:has-text("Login")').first().click();
}

async function createCandidateAndUploadDocs(browser, summary) {
  const context = await browser.newContext({ acceptDownloads: true });
  await context.addInitScript(localePatch);
  const page = await context.newPage();
  const docId = `66${Date.now().toString().slice(-6)}`;
  const email = `candidate.${docId}@example.com`;

  summary.docId = docId;
  summary.email = email;

  await page.goto(`${baseUrl}/candidato`, { waitUntil: 'networkidle' });
  await page.fill('#nombre', 'Smoke');
  await page.fill('#primer_apellido', 'Integral');
  await page.fill('#segundo_apellido', 'Playwright');
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
  await page.fill('#contacto_emergencia_nombre', 'Contacto Smoke');
  await page.fill('#contacto_emergencia_telefono', '3007654321');
  await page.selectOption('#procedencia_pais', '169');
  await waitForOptions(page, '#procedencia_departamento');
  const dep = await page.locator('#procedencia_departamento option:not([value=""])').nth(0).getAttribute('value');
  await page.selectOption('#procedencia_departamento', dep);
  await waitForOptions(page, '#procedencia_ciudad');
  const city = await page.locator('#procedencia_ciudad option:not([value=""])').nth(0).getAttribute('value');
  await page.selectOption('#procedencia_ciudad', city);
  const bank = await page.locator('#banco_siesa option:not([value=""])').nth(0).getAttribute('value');
  await page.selectOption('#banco_siesa', bank);
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
  await page.waitForSelector('#step-6.active', { timeout: 60000 });
  summary.steps.push('candidate_created');

  const loginUser = (await page.locator('#credential-user').innerText()).trim();
  const loginPassword = (await page.locator('#credential-password').innerText()).trim();
  summary.loginUser = loginUser;

  await page.locator('#loginBtn').click();
  await page.waitForLoadState('networkidle');
  await page.locator('input[placeholder="juan@example.com"], input[placeholder="jane@example.com"], input[name="usr"]').first().fill(loginUser);
  await page.locator('input[placeholder="•••••"], input[name="pwd"]').first().fill(loginPassword);
  await page.locator('button:has-text("Iniciar sesión"), button:has-text("Login")').first().click();
  await page.waitForURL(/\/app(\/mis_documentos_candidato)?$/, { timeout: 60000 });
  await page.goto(`${baseUrl}/app/mis_documentos_candidato`, { waitUntil: 'networkidle' });
  summary.steps.push('candidate_logged_in');

  const docsPayload = await browserPost(page, '/api/method/hubgh.hubgh.page.mis_documentos_candidato.mis_documentos_candidato.get_my_documents', {});
  const candidateName = docsPayload.message && docsPayload.message.candidate;
  const documents = (docsPayload.message && docsPayload.message.documents) || [];
  for (const document of documents) {
    const fileUrl = await browserUploadFile(page, 'Candidato', candidateName);
    const body = await browserPost(page, '/api/method/hubgh.hubgh.page.mis_documentos_candidato.mis_documentos_candidato.upload_my_document', {
      document_type: document.document_type,
      file_url: fileUrl,
      notes: 'Smoke upload candidate docs',
    });
    if (body._server_messages) summary.issues.push(`candidate_upload:${body._server_messages}`);
  }
  summary.steps.push('candidate_uploaded_all_docs');
  await context.close();
}

async function run() {
  const browser = await firefox.launch({ headless: process.env.HUBGH_E2E_HEADLESS === '0' ? false : true });
  const adminContext = await browser.newContext({ acceptDownloads: true });
  await adminContext.addInitScript(localePatch);
  const page = await adminContext.newPage();
  const summary = { steps: [], downloads: [], issues: [] };

  try {
    await createCandidateAndUploadDocs(browser, summary);

    await login(page, 'Administrator', 'admin');
    await page.waitForURL('**/app');
    summary.steps.push('admin_ready');

    const refs = {
      pdv: await getFirstName(page, 'Punto de Venta'),
      cargo: await getFirstName(page, 'Cargo'),
      eps: await getFirstName(page, 'Entidad EPS Siesa'),
      afp: await getFirstName(page, 'Entidad AFP Siesa'),
      ces: await getFirstName(page, 'Entidad Cesantias Siesa'),
      ccf: await getFirstName(page, 'Entidad CCF Siesa'),
      tipoCotizante: await getFirstName(page, 'Tipo Cotizante Siesa'),
      centroCostos: await getFirstName(page, 'Centro Costos Siesa'),
      unidadNegocio: await getFirstName(page, 'Unidad Negocio Siesa'),
      centroTrabajo: await getFirstName(page, 'Centro Trabajo Siesa'),
      grupoEmpleados: await getFirstName(page, 'Grupo Empleados Siesa'),
    };
    summary.refs = refs;

    await page.goto(`${baseUrl}/app/seleccion_documentos`, { waitUntil: 'networkidle' });
    await page.fill('.filter-search', summary.docId);
    await page.waitForTimeout(1200);
    const selectionCard = page.locator('.hubgh-card').filter({ hasText: summary.docId }).first();
    await selectionCard.waitFor({ state: 'visible', timeout: 60000 });

    let fileUrl = await browserUploadFile(page, 'Candidato', summary.docId);
    let json = await browserPost(page, '/api/method/hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.upload_candidate_document', {
      candidate: summary.docId,
      document_type: 'SAGRILAFT',
      file_url: fileUrl,
    });
    if (json._server_messages) summary.issues.push(`selection_sagrilaft:${json._server_messages}`);
    await dismissOpenModals(page);
    summary.steps.push('selection_uploaded_sagrilaft');

    await Promise.all([
      page.waitForResponse((resp) => resp.url().includes('send_to_medical_exam') && resp.status() === 200, { timeout: 60000 }),
      selectionCard.locator('.action-primary').click(),
    ]);
    summary.steps.push('sent_to_medical_exam');

    await page.goto(`${baseUrl}/app/sst_examenes_medicos`, { waitUntil: 'networkidle' });
    await page.fill('.filter-search', summary.docId);
    await page.waitForTimeout(1200);
    const medicalCard = page.locator('.hubgh-card').filter({ hasText: summary.docId }).first();
    await medicalCard.waitFor({ state: 'visible', timeout: 60000 });
    fileUrl = await browserUploadFile(page, 'Candidato', summary.docId);
    json = await browserPost(page, '/api/method/hubgh.hubgh.page.sst_examenes_medicos.sst_examenes_medicos.upload_medical_exam_document', {
      candidate: summary.docId,
      file_url: fileUrl,
    });
    if (json._server_messages) summary.issues.push(`medical_upload:${json._server_messages}`);
    await dismissOpenModals(page);
    summary.steps.push('medical_exam_uploaded');

    await page.waitForTimeout(800);
    await browserPost(page, '/api/method/hubgh.hubgh.page.sst_examenes_medicos.sst_examenes_medicos.set_medical_concept', {
      candidate: summary.docId,
      concepto_medico: 'Favorable',
      notes: 'Smoke favorable',
    });
    summary.steps.push('medical_concept_favorable');

    await page.goto(`${baseUrl}/app/bandeja_afiliaciones`, { waitUntil: 'networkidle' });
    await page.fill('.filter-search', summary.docId);
    await page.waitForTimeout(1200);
    const affiliationTypes = ['arl', 'eps', 'afp', 'cesantias', 'caja'];
    for (const pendingType of affiliationTypes) {
      const payload = { data: { [`${pendingType}_afiliado`]: 1, [`${pendingType}_fecha_afiliacion`]: '2026-04-10', [`${pendingType}_numero_afiliacion`]: `${pendingType}-SMOKE` } };
      if (pendingType === 'eps') payload.data.eps_siesa = refs.eps;
      if (pendingType === 'afp') payload.data.afp_siesa = refs.afp;
      if (pendingType === 'cesantias') payload.data.cesantias_siesa = refs.ces;
      await browserPost(page, '/api/method/hubgh.hubgh.page.bandeja_afiliaciones.bandeja_afiliaciones.save_affiliation', {
        candidate: summary.docId,
        affiliation_type: pendingType,
        payload: JSON.stringify(payload),
      });
    }
    await browserPost(page, '/api/method/hubgh.hubgh.page.bandeja_afiliaciones.bandeja_afiliaciones.mark_affiliation_complete', {
      candidate: summary.docId,
    });
    summary.steps.push('affiliations_completed');

    await page.goto(`${baseUrl}/app/bandeja_contratacion`, { waitUntil: 'networkidle' });
    await page.fill('.filter-search', summary.docId);
    await page.waitForTimeout(1200);
    const contractCard = page.locator('.hubgh-card').filter({ hasText: summary.docId }).first();
    await contractCard.waitFor({ state: 'visible', timeout: 60000 });
    const contractPayload = {
      numero_contrato: Number(summary.docId.slice(-4)),
      tipo_contrato: 'Indefinido',
      fecha_ingreso: '2026-04-15',
      salario: 1800000,
      horas_trabajadas_mes: 220,
      pdv_destino: refs.pdv,
      cargo: refs.cargo,
      eps_siesa: refs.eps,
      afp_siesa: refs.afp,
      cesantias_siesa: refs.ces,
      ccf_siesa: refs.ccf,
      tipo_cotizante_siesa: refs.tipoCotizante,
      centro_costos_siesa: refs.centroCostos,
      unidad_negocio_siesa: refs.unidadNegocio,
      centro_trabajo_siesa: refs.centroTrabajo,
      grupo_empleados_siesa: refs.grupoEmpleados,
      direccion: 'Calle 123 # 45-67',
      celular: '3001234567',
      email: summary.email,
    };
    const createdContract = await browserPost(page, '/api/method/hubgh.hubgh.page.bandeja_contratacion.bandeja_contratacion.create_contract', {
      candidate: summary.docId,
      payload: JSON.stringify(contractPayload),
    });
    const contractName = (createdContract.message && createdContract.message.name) || createdContract.name;
    await browserPost(page, '/api/method/hubgh.hubgh.page.bandeja_contratacion.bandeja_contratacion.submit_contract', {
      contract: contractName,
    });
    summary.steps.push('contract_created_submitted');

    const datosRows = await frappeCall(page, 'frappe.client.get_list', { doctype: 'Datos Contratacion', fields: ['name'], filters: { candidato: summary.docId }, limit_page_length: 1 });
    summary.datosContratacion = datosRows && datosRows[0] && datosRows[0].name;
    if (summary.datosContratacion) {
      await page.goto(`${baseUrl}/app/form/Datos Contratacion/${encodeURIComponent(summary.datosContratacion)}`, { waitUntil: 'networkidle' });
      await page.waitForTimeout(2000);
      await page.evaluate((refs) => {
        const setIfBlank = (field, value) => {
          const current = cur_frm.doc[field];
          if (current === null || current === undefined || current === '') cur_frm.set_value(field, value);
        };
        setIfBlank('genero', 'Masculino');
        setIfBlank('estado_civil', 'Soltero');
        setIfBlank('nivel_educativo_siesa', 'BACHILLER');
        setIfBlank('direccion', 'Calle 123 # 45-67');
        setIfBlank('barrio', 'Chico');
        setIfBlank('ciudad', 'Bogota');
        setIfBlank('procedencia_pais', '169');
        setIfBlank('procedencia_departamento', '11');
        setIfBlank('procedencia_ciudad', '001');
        setIfBlank('pais_residencia_siesa', '169');
        setIfBlank('departamento_residencia_siesa', '11');
        setIfBlank('ciudad_residencia_siesa', '001');
        setIfBlank('pais_nacimiento_siesa', '169');
        setIfBlank('departamento_nacimiento_siesa', '11');
        setIfBlank('ciudad_nacimiento_siesa', '001');
        setIfBlank('pais_expedicion_siesa', '169');
        setIfBlank('departamento_expedicion_siesa', '11');
        setIfBlank('ciudad_expedicion_siesa', '001');
        setIfBlank('telefono_contacto_siesa', '3001234567');
        setIfBlank('tipo_cotizante_siesa', refs.tipoCotizante);
        setIfBlank('centro_costos_siesa', refs.centroCostos);
        setIfBlank('unidad_negocio_siesa', refs.unidadNegocio);
        setIfBlank('grupo_empleados_siesa', refs.grupoEmpleados);
        setIfBlank('centro_trabajo_siesa', refs.centroTrabajo);
        setIfBlank('pdv_destino', refs.pdv);
        setIfBlank('cargo_postulado', refs.cargo);
        setIfBlank('eps_siesa', refs.eps);
        setIfBlank('afp_siesa', refs.afp);
        setIfBlank('cesantias_siesa', refs.ces);
        setIfBlank('ccf_siesa', refs.ccf);
      }, refs);
      await Promise.all([
        page.waitForResponse((resp) => resp.url().includes('/api/method/frappe.desk.form.save.savedocs') && resp.status() === 200, { timeout: 60000 }),
        page.evaluate(() => cur_frm.save()),
      ]);
      summary.steps.push('datos_contratacion_checked');
    }

    const employeeRows = await frappeCall(page, 'frappe.client.get_list', { doctype: 'Ficha Empleado', fields: ['name'], filters: { cedula: summary.docId }, limit_page_length: 1 });
    summary.employee = employeeRows && employeeRows[0] && employeeRows[0].name;
    await page.goto(`${baseUrl}/app/carpeta_documental_empleado`, { waitUntil: 'networkidle' });
    await page.fill('.hub-search', summary.docId);
    await page.click('.btn-search');
    await page.waitForTimeout(1500);
    await page.locator('.btn-open-drawer').first().click();
    await page.waitForTimeout(1500);
    summary.folderText = (await page.locator('.hub-drawer__body').innerText()).slice(0, 2000);
    if (await page.locator('.btn-doc-download').count()) {
      const popupPromise = page.waitForEvent('popup');
      await page.locator('.btn-doc-download').first().click();
      const popup = await popupPromise;
      await popup.waitForLoadState('domcontentloaded').catch(() => {});
      summary.downloads.push({ type: 'employee_doc', url: popup.url() });
      await popup.close().catch(() => {});
    }
    const zipPopupPromise = page.waitForEvent('popup');
    await page.locator('.btn-download-zip').click();
    const zipPopup = await zipPopupPromise;
    await zipPopup.waitForLoadState('domcontentloaded').catch(() => {});
    summary.downloads.push({ type: 'employee_zip', url: zipPopup.url() });
    await zipPopup.close().catch(() => {});
    summary.steps.push('employee_folder_checked');

    await page.goto(`${baseUrl}/app/reportes_siesa`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(2500);
    const row = page.locator('tr').filter({ hasText: summary.docId }).first();
    await row.waitFor({ state: 'visible', timeout: 60000 });
    summary.siesaRow = await row.innerText();
    if (await row.locator('.row-check').count()) {
      const rowCheck = row.locator('.row-check');
      if (!(await rowCheck.isChecked().catch(() => false))) {
        await rowCheck.check().catch(() => {});
      }
    }
    const empPopupPromise = page.waitForEvent('popup');
    await page.locator('.btn-emp').click();
    const empPopup = await empPopupPromise;
    await empPopup.waitForLoadState('domcontentloaded').catch(() => {});
    summary.downloads.push({ type: 'siesa_empleados', url: empPopup.url() });
    await empPopup.close().catch(() => {});
    const contPopupPromise = page.waitForEvent('popup');
    await page.locator('.btn-cont').click();
    const contPopup = await contPopupPromise;
    await contPopup.waitForLoadState('domcontentloaded').catch(() => {});
    summary.downloads.push({ type: 'siesa_contratos', url: contPopup.url() });
    await contPopup.close().catch(() => {});
    summary.steps.push('siesa_downloaded');

    console.log(JSON.stringify(summary, null, 2));
  } catch (error) {
    summary.error = String(error && error.stack ? error.stack : error);
    summary.failedUrl = page.url();
    try {
      const shot = path.resolve(process.cwd(), 'test-results', `full-hiring-siesa-smoke-${Date.now()}.png`);
      await page.screenshot({ path: shot, fullPage: true });
      summary.screenshot = shot;
    } catch (shotError) {
      summary.screenshotError = String(shotError);
    }
    console.log(JSON.stringify(summary, null, 2));
    process.exitCode = 1;
  } finally {
    await adminContext.close();
    await browser.close();
  }
}

run();
