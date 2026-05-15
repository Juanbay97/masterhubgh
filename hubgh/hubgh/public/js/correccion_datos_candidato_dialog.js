(() => {
	if (window.hubgh && window.hubgh.openCorreccionDatosDialog) return;
	window.hubgh = window.hubgh || {};

	const STYLE_ID = "hubgh-correccion-datos-style";
	const injectStyles = () => {
		if (document.getElementById(STYLE_ID)) return;
		const style = document.createElement("style");
		style.id = STYLE_ID;
		style.innerHTML = `
			.hubgh-corr-banner {
				padding: 10px 12px;
				border-radius: 10px;
				font-size: 12px;
				font-weight: 600;
				margin-bottom: 8px;
				border: 1px solid #bfdbfe;
				background: #eff6ff;
				color: #1e40af;
			}
			.hubgh-corr-banner.is-post {
				border-color: #fed7aa;
				background: #fff7ed;
				color: #9a3412;
			}
			.hubgh-corr-bank-wrap {
				display: grid;
				grid-template-columns: minmax(0, 1fr) minmax(0, 1.4fr);
				gap: 14px;
				align-items: start;
			}
			.hubgh-corr-bank-wrap .hubgh-corr-bank-fields { display: grid; gap: 8px; }
			.hubgh-corr-bank-wrap iframe {
				width: 100%;
				height: 480px;
				border: 1px solid #e2e8f0;
				border-radius: 8px;
				background: #f8fafc;
			}
			.hubgh-corr-bank-empty {
				border: 1px dashed #cbd5e1;
				border-radius: 8px;
				padding: 14px;
				color: #64748b;
				font-size: 12px;
				text-align: center;
			}
			@media (max-width: 900px) {
				.hubgh-corr-bank-wrap { grid-template-columns: 1fr; }
				.hubgh-corr-bank-wrap iframe { height: 360px; }
			}
		`;
		document.head.appendChild(style);
	};

	const esc = value => (window.frappe && frappe.utils && frappe.utils.escape_html)
		? frappe.utils.escape_html(value == null ? "" : String(value))
		: String(value == null ? "" : value);

	const CAMPO_OPTIONS = [
		{ value: "", label: "Seleccioná un campo…" },
		{ value: "email", label: "Email" },
		{ value: "cedula", label: "Cédula (número de documento)" },
		{ value: "cuenta_bancaria", label: "Cuenta bancaria" },
		{ value: "datos_personales", label: "Datos personales (nombres, fechas, contacto, dirección)" },
	];

	const TIPO_CUENTA_OPTIONS = "\nAhorros\nCorriente\nTarjeta Prepago";

	// Campos editables bajo `datos_personales`. Sincronizado con
	// PERSONAL_DATA_FIELDS en candidate_correction_service.py — si cambia uno,
	// cambiar el otro.
	const PERSONAL_DATA_FIELDS = [
		// Identidad
		{ fieldname: "nombres", fieldtype: "Data", label: "Nombres", group: "identidad" },
		{ fieldname: "primer_apellido", fieldtype: "Data", label: "Primer Apellido", group: "identidad" },
		{ fieldname: "segundo_apellido", fieldtype: "Data", label: "Segundo Apellido", group: "identidad" },
		{ fieldname: "apellidos", fieldtype: "Data", label: "Apellidos (combinado)", group: "identidad" },
		// Fechas
		{ fieldname: "fecha_nacimiento", fieldtype: "Date", label: "Fecha Nacimiento", group: "fechas" },
		{ fieldname: "fecha_expedicion", fieldtype: "Date", label: "Fecha Expedición Documento", group: "fechas" },
		// Contacto
		{ fieldname: "celular", fieldtype: "Data", label: "Celular", group: "contacto" },
		{ fieldname: "telefono_fijo", fieldtype: "Data", label: "Teléfono Fijo", group: "contacto" },
		{ fieldname: "contacto_emergencia_nombre", fieldtype: "Data", label: "Nombre Contacto Emergencia", group: "contacto" },
		{ fieldname: "contacto_emergencia_telefono", fieldtype: "Data", label: "Teléfono Contacto Emergencia", group: "contacto" },
		// Demográficos
		{ fieldname: "genero", fieldtype: "Select", label: "Género", options: "\nMasculino\nFemenino\nOtro", group: "demo" },
		{ fieldname: "estado_civil", fieldtype: "Select", label: "Estado Civil", options: "\nSoltero\nCasado\nUnión Libre\nDivorciado\nViudo", group: "demo" },
		{ fieldname: "nivel_educativo_siesa", fieldtype: "Link", label: "Nivel Educativo (Siesa)", options: "Nivel Educativo Siesa", group: "demo" },
		{ fieldname: "es_extranjero", fieldtype: "Check", label: "Es Extranjero", group: "demo" },
		// Dirección
		{ fieldname: "ciudad", fieldtype: "Link", label: "Ciudad", options: "Ciudad", group: "direccion" },
		{ fieldname: "localidad", fieldtype: "Select", label: "Localidad (Bogotá)", options: "\nAntonio Nariño\nBarrios Unidos\nBosa\nChapinero\nCiudad Bolivar\nEngativa\nFontibon\nKennedy\nLa Candelaria\nLos Martires\nPuente Aranda\nRafael Uribe Uribe\nSan Cristobal\nSanta Fe\nSuba\nSumapaz\nTeusaquillo\nTunjuelito\nUsaquen\nUsme", group: "direccion" },
		{ fieldname: "localidad_otras", fieldtype: "Data", label: "Localidad / Comuna", group: "direccion" },
		{ fieldname: "barrio", fieldtype: "Data", label: "Barrio", group: "direccion" },
		{ fieldname: "direccion", fieldtype: "Data", label: "Dirección", group: "direccion" },
		// Procedencia / residencia
		{ fieldname: "procedencia_pais", fieldtype: "Data", label: "Procedencia País", group: "proc" },
		{ fieldname: "procedencia_departamento", fieldtype: "Data", label: "Procedencia Departamento", group: "proc" },
		{ fieldname: "procedencia_ciudad", fieldtype: "Data", label: "Procedencia Ciudad", group: "proc" },
		{ fieldname: "pais_residencia_siesa", fieldtype: "Data", label: "País Residencia (Siesa)", group: "proc" },
		{ fieldname: "departamento_residencia_siesa", fieldtype: "Data", label: "Departamento Residencia (Siesa)", group: "proc" },
		{ fieldname: "ciudad_residencia_siesa", fieldtype: "Data", label: "Ciudad Residencia (Siesa)", group: "proc" },
	];

	const PERSONAL_GROUPS = [
		{ id: "identidad", label: "Identidad" },
		{ id: "fechas", label: "Fechas" },
		{ id: "contacto", label: "Contacto" },
		{ id: "demo", label: "Demográficos" },
		{ id: "direccion", label: "Dirección" },
		{ id: "proc", label: "Procedencia / Residencia" },
	];

	window.hubgh.openCorreccionDatosDialog = function({ candidato_name, candidato_label, on_success } = {}) {
		if (!candidato_name) {
			frappe.msgprint("Falta el candidato.");
			return;
		}
		injectStyles();

		const title = `Corregir datos — ${candidato_label || candidato_name}`;
		let phase = null;

		const dialog = new frappe.ui.Dialog({
			title,
			size: "extra-large",
			fields: [
				{ fieldtype: "HTML", fieldname: "banner_html" },
				{
					fieldtype: "Select",
					fieldname: "campo",
					label: "Campo a corregir",
					reqd: 1,
					options: CAMPO_OPTIONS.map(o => o.value).join("\n"),
					onchange: () => refreshVisibility(),
				},
				{ fieldtype: "Section Break", fieldname: "sec_email", hidden: 1, label: "Nuevo email" },
				{ fieldtype: "Data", fieldname: "valor_nuevo_email", label: "Nuevo email", options: "Email" },
				{ fieldtype: "Section Break", fieldname: "sec_cedula", hidden: 1, label: "Nueva cédula" },
				{ fieldtype: "Data", fieldname: "valor_nuevo_cedula", label: "Nuevo número de documento", description: "Solo dígitos, sin puntos ni espacios." },
				{ fieldtype: "Section Break", fieldname: "sec_cuenta", hidden: 1, label: "Nueva cuenta bancaria" },
				{ fieldtype: "HTML", fieldname: "cuenta_html" },
				{ fieldtype: "Section Break", fieldname: "sec_datos_personales", hidden: 1, label: "Corregir datos personales" },
				{ fieldtype: "HTML", fieldname: "datos_personales_html" },
				{ fieldtype: "Section Break", fieldname: "sec_motivo", label: "Motivo" },
				{ fieldtype: "Long Text", fieldname: "motivo", label: "Motivo (obligatorio)", reqd: 1 },
			],
			primary_action_label: "Aplicar corrección",
			primary_action: () => handleSubmit(),
		});

		// Estado interno cuenta bancaria (inputs propios dentro del HTML field).
		const bankState = {
			numero_cuenta_bancaria: "",
			tipo_cuenta_bancaria: "Ahorros",
			banco_siesa: "",
			file_url: null,
			loaded: false,
		};

		// Estado interno datos personales: original (pre-cambio) y controls
		// renderizados via frappe.ui.form.make_control para tipos compuestos.
		const personalState = {
			loaded: false,
			loading: false,
			original: {},
			controls: {},
		};

		const updatePrimaryLabel = () => {
			if (!phase) return;
			const label = phase === "post_contrato" ? "Solicitar aprobación" : "Aplicar corrección";
			// Frappe expone set_primary_action_label en algunas versiones; fallback al DOM.
			if (typeof dialog.set_primary_action_label === "function") {
				dialog.set_primary_action_label(label);
			}
			dialog.$wrapper.find(".modal-footer .btn-primary").text(label);
		};

		const renderBanner = () => {
			const isPost = phase === "post_contrato";
			const text = phase
				? (isPost
					? "Fase: post_contrato — la corrección queda PENDIENTE de aprobación."
					: "Fase: pre_contrato — la corrección se aplica al instante.")
				: "Detectando fase del candidato…";
			const cls = isPost ? "hubgh-corr-banner is-post" : "hubgh-corr-banner";
			dialog.fields_dict.banner_html.$wrapper.html(`<div class='${cls}'>${esc(text)}</div>`);
		};

		const renderBankBlock = () => {
			const $wrap = dialog.fields_dict.cuenta_html.$wrapper;
			const iframeHtml = bankState.file_url
				? `<iframe src='${esc(bankState.file_url)}#toolbar=1' title='Certificación bancaria'></iframe>`
				: `<div class='hubgh-corr-bank-empty'>
					<div><b>No hay certificación bancaria adjunta.</b></div>
					<div style='margin-top:6px'>Subila desde el detalle documental del candidato antes de modificar la cuenta.</div>
				</div>`;
			$wrap.html(`
				<div class='hubgh-corr-bank-wrap'>
					<div class='hubgh-corr-bank-fields'>
						<div class='form-group'>
							<label class='control-label'>Número de cuenta</label>
							<input type='text' class='form-control hubgh-corr-numero' value='${esc(bankState.numero_cuenta_bancaria)}' />
						</div>
						<div class='form-group'>
							<label class='control-label'>Tipo de cuenta</label>
							<select class='form-control hubgh-corr-tipo'>
								${TIPO_CUENTA_OPTIONS.split("\n").map(opt => `<option value='${esc(opt)}' ${opt === bankState.tipo_cuenta_bancaria ? "selected" : ""}>${esc(opt || "—")}</option>`).join("")}
							</select>
						</div>
						<div class='form-group hubgh-corr-banco-host'></div>
					</div>
					<div>${iframeHtml}</div>
				</div>
			`);

			$wrap.find(".hubgh-corr-numero").on("input", function() {
				bankState.numero_cuenta_bancaria = $(this).val();
			});
			$wrap.find(".hubgh-corr-tipo").on("change", function() {
				bankState.tipo_cuenta_bancaria = $(this).val();
			});

			// Banco Siesa como Link via frappe.ui.form.make_control para autocomplete coherente.
			const $bancoHost = $wrap.find(".hubgh-corr-banco-host");
			$bancoHost.empty();
			const bancoCtrl = frappe.ui.form.make_control({
				parent: $bancoHost.get(0),
				df: {
					fieldname: "banco_siesa",
					label: "Banco",
					fieldtype: "Link",
					options: "Banco Siesa",
				},
				render_input: true,
			});
			bancoCtrl.set_value(bankState.banco_siesa || "");
			bancoCtrl.$input && bancoCtrl.$input.on("change", () => {
				bankState.banco_siesa = bancoCtrl.get_value() || "";
			});
			// Guardar referencia para validación al submit.
			bankState._control = bancoCtrl;
		};

		const loadBankCert = () => {
			if (bankState.loaded) return;
			bankState.loaded = true;
			frappe.call({
				method: "hubgh.hubgh.api.correcciones.get_bank_cert_url",
				args: { candidato: candidato_name },
			}).then(r => {
				const file_url = r && r.message && r.message.file_url;
				bankState.file_url = file_url || null;
				renderBankBlock();
			}).catch(() => {
				bankState.file_url = null;
				renderBankBlock();
			});
		};

		const renderPersonalBlock = () => {
			const $wrap = dialog.fields_dict.datos_personales_html.$wrapper;
			if (personalState.loading) {
				$wrap.html("<div style='padding:12px;color:#64748b'>Cargando datos actuales del candidato…</div>");
				return;
			}
			if (!personalState.loaded) {
				$wrap.html("<div style='padding:12px;color:#64748b'>Esperando carga…</div>");
				return;
			}
			// Layout: una sección por grupo, dentro grid de 2 cols.
			const sections = PERSONAL_GROUPS.map(g => {
				const fields = PERSONAL_DATA_FIELDS.filter(f => f.group === g.id);
				if (!fields.length) return "";
				const hosts = fields.map(f =>
					`<div class='form-group' data-host='${esc(f.fieldname)}'><label class='control-label'>${esc(f.label)}</label><div class='hubgh-pd-host'></div></div>`
				).join("");
				return `
					<div class='hubgh-pd-section'>
						<div class='hubgh-pd-section-title'>${esc(g.label)}</div>
						<div class='hubgh-pd-grid'>${hosts}</div>
					</div>
				`;
			}).join("");
			$wrap.html(`
				<style>
					.hubgh-pd-section { margin-bottom: 14px; }
					.hubgh-pd-section-title { font-weight: 600; font-size: 12px; color: #334155; margin: 6px 0; text-transform: uppercase; letter-spacing: 0.04em; }
					.hubgh-pd-grid { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 8px 14px; }
					.hubgh-pd-grid .form-group { margin-bottom: 4px; }
				</style>
				${sections}
			`);

			// Montar controles Frappe en cada host.
			personalState.controls = {};
			PERSONAL_DATA_FIELDS.forEach(f => {
				const $host = $wrap.find(`[data-host='${f.fieldname}'] .hubgh-pd-host`);
				if (!$host.length) return;
				$host.empty();
				const df = {
					fieldname: f.fieldname,
					label: "",
					fieldtype: f.fieldtype,
				};
				if (f.options) df.options = f.options;
				const ctrl = frappe.ui.form.make_control({
					parent: $host.get(0),
					df,
					render_input: true,
				});
				const initial = personalState.original[f.fieldname];
				if (initial !== undefined && initial !== null) {
					ctrl.set_value(initial);
				}
				personalState.controls[f.fieldname] = ctrl;
			});
		};

		const loadPersonalData = () => {
			if (personalState.loaded || personalState.loading) {
				renderPersonalBlock();
				return;
			}
			personalState.loading = true;
			renderPersonalBlock();
			frappe.call({
				method: "frappe.client.get_value",
				args: {
					doctype: "Candidato",
					filters: { name: candidato_name },
					fieldname: PERSONAL_DATA_FIELDS.map(f => f.fieldname),
				},
			}).then(r => {
				const data = (r && r.message) || {};
				personalState.original = data;
				personalState.loaded = true;
				personalState.loading = false;
				renderPersonalBlock();
			}).catch(() => {
				personalState.loading = false;
				personalState.loaded = true;
				personalState.original = {};
				renderPersonalBlock();
			});
		};

		const refreshVisibility = () => {
			const campo = dialog.get_value("campo") || "";
			const setHidden = (fname, hidden) => {
				const field = dialog.fields_dict[fname];
				if (!field) return;
				field.df.hidden = hidden ? 1 : 0;
				if (typeof field.refresh === "function") field.refresh();
			};
			setHidden("sec_email", campo !== "email");
			setHidden("valor_nuevo_email", campo !== "email");
			setHidden("sec_cedula", campo !== "cedula");
			setHidden("valor_nuevo_cedula", campo !== "cedula");
			setHidden("sec_cuenta", campo !== "cuenta_bancaria");
			setHidden("cuenta_html", campo !== "cuenta_bancaria");
			setHidden("sec_datos_personales", campo !== "datos_personales");
			setHidden("datos_personales_html", campo !== "datos_personales");

			if (campo === "cuenta_bancaria") {
				if (!bankState.loaded) {
					loadBankCert();
				} else {
					renderBankBlock();
				}
			}
			if (campo === "datos_personales") {
				loadPersonalData();
			}
		};

		const handleSubmit = () => {
			const campo = dialog.get_value("campo") || "";
			const motivo = (dialog.get_value("motivo") || "").trim();
			if (!campo) {
				frappe.msgprint("Elegí un campo a corregir.");
				return;
			}
			if (!motivo) {
				frappe.msgprint("El motivo es obligatorio.");
				return;
			}

			let valor_nuevo;
			if (campo === "email") {
				const v = (dialog.get_value("valor_nuevo_email") || "").trim();
				if (!v || !/.+@.+\..+/.test(v)) {
					frappe.msgprint("Ingresá un email válido.");
					return;
				}
				valor_nuevo = v;
			} else if (campo === "cedula") {
				const v = (dialog.get_value("valor_nuevo_cedula") || "").trim();
				if (!v || !/^[0-9]{5,15}$/.test(v)) {
					frappe.msgprint("La cédula debe contener solo dígitos (5 a 15).");
					return;
				}
				valor_nuevo = v;
			} else if (campo === "cuenta_bancaria") {
				const numero = (bankState.numero_cuenta_bancaria || "").trim();
				const tipo = bankState.tipo_cuenta_bancaria || "";
				const banco = bankState._control ? (bankState._control.get_value() || "").trim() : (bankState.banco_siesa || "").trim();
				if (!numero || !tipo || !banco) {
					frappe.msgprint("Completá número de cuenta, tipo y banco.");
					return;
				}
				valor_nuevo = {
					numero_cuenta_bancaria: numero,
					tipo_cuenta_bancaria: tipo,
					banco_siesa: banco,
				};
			} else if (campo === "datos_personales") {
				if (!personalState.loaded) {
					frappe.msgprint("Aún se están cargando los datos del candidato.");
					return;
				}
				// Diff: solo incluimos campos que cambiaron respecto al original.
				const diff = {};
				PERSONAL_DATA_FIELDS.forEach(f => {
					const ctrl = personalState.controls[f.fieldname];
					if (!ctrl) return;
					let current = ctrl.get_value();
					if (typeof current === "string") current = current.trim();
					let original = personalState.original[f.fieldname];
					if (typeof original === "string") original = original.trim();
					// Normalizar null/undefined a "" para comparar.
					const cmpCur = current == null ? "" : current;
					const cmpOrig = original == null ? "" : original;
					// Check booleano: comparar como 0/1.
					if (f.fieldtype === "Check") {
						const a = cmpCur ? 1 : 0;
						const b = cmpOrig ? 1 : 0;
						if (a !== b) diff[f.fieldname] = a;
					} else if (String(cmpCur) !== String(cmpOrig)) {
						diff[f.fieldname] = current;
					}
				});
				if (!Object.keys(diff).length) {
					frappe.msgprint("No se detectaron cambios en los datos personales.");
					return;
				}
				valor_nuevo = diff;
			} else {
				frappe.msgprint("Campo no soportado.");
				return;
			}

			const $btn = dialog.$wrapper.find(".modal-footer .btn-primary");
			$btn.prop("disabled", true);

			frappe.call({
				method: "hubgh.hubgh.api.correcciones.submit_candidate_correction",
				args: {
					candidato: candidato_name,
					campo,
					valor_nuevo: typeof valor_nuevo === "string" ? valor_nuevo : JSON.stringify(valor_nuevo),
					motivo,
				},
			}).then(r => {
				$btn.prop("disabled", false);
				const msg = r && r.message;
				const status = msg && msg.status;
				if (status === "applied") {
					frappe.show_alert({ message: "Corrección aplicada", indicator: "green" });
					dialog.hide();
					if (typeof on_success === "function") on_success({ status, response: msg });
				} else if (status === "pending_approval") {
					frappe.show_alert({ message: "Corrección enviada para aprobación", indicator: "orange" });
					dialog.hide();
					if (typeof on_success === "function") on_success({ status, response: msg });
				} else {
					frappe.msgprint("Respuesta inesperada del servidor.");
				}
			}).catch(err => {
				$btn.prop("disabled", false);
				const message = (err && (err.message || err._server_messages)) || "No fue posible registrar la corrección.";
				frappe.msgprint(message);
			});
		};

		dialog.show();
		dialog.$wrapper.on("hidden.bs.modal", () => {
			$("body").removeClass("modal-open");
			$(".modal-backdrop").remove();
		});

		renderBanner();
		refreshVisibility();

		// Cargar fase.
		frappe.call({
			method: "hubgh.hubgh.api.correcciones.get_correction_phase_api",
			args: { candidato: candidato_name },
		}).then(r => {
			phase = (r && r.message && r.message.fase) || "pre_contrato";
			renderBanner();
			updatePrimaryLabel();
		}).catch(() => {
			phase = "pre_contrato";
			renderBanner();
			updatePrimaryLabel();
		});
	};
})();
