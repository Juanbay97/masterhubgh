frappe.pages["mis_documentos_candidato"].on_page_load = function (wrapper) {
	const safeLang =
		(frappe.boot && frappe.boot.lang) ||
		(document.documentElement && document.documentElement.lang) ||
		(navigator.language && navigator.language !== "undefined" ? navigator.language : "") ||
		"es";
	if (frappe.boot) {
		frappe.boot.lang = safeLang;
	}
	if (window.Intl && typeof window.Intl.Locale === "function" && !window.Intl.__hubghSafeLocalePatched) {
		const NativeLocale = window.Intl.Locale;
		window.Intl.Locale = function (locale, options) {
			const normalizedLocale = locale && locale !== "undefined" ? locale : safeLang;
			return new NativeLocale(normalizedLocale, options);
		};
		window.Intl.Locale.prototype = NativeLocale.prototype;
		window.Intl.__hubghSafeLocalePatched = true;
	}
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Mis Documentos",
		single_column: true,
	});

	const $root = $("<div class='mis-documentos-candidato'></div>").appendTo(page.body);
	let siesaOptions = { eps: [], afp: [], cesantias: [], bancos: [] };

	const toSelectOptions = (rows) =>
		(rows || [])
			.map((row) => row?.label || row?.value)
			.filter(Boolean)
			.join("\n");

	const NIVEL_EDUCATIVO_SIESA_OPTIONS = [
		"PREESCOLAR",
		"BÁSICA PRIMARIA",
		"BÁSICA SECUNDARIA",
		"MEDIA",
		"TÉCNICO LABORAL",
		"FORMACIÓN TÉCNICA PROFESIONAL",
		"TECNOLÓGICA",
		"UNIVERSITARIA",
		"ESPECIALIZACIÓN",
		"MAESTRÍA",
		"DOCTORADO",
		"SIN DEFINIR",
		"OTROS",
	].join("\n");

	const mapStoredCodeToLabel = (fieldname, storedValue) => {
		if (!storedValue) return storedValue;
		const catalogMap = {
			eps_siesa: siesaOptions.eps,
			afp_siesa: siesaOptions.afp,
			cesantias_siesa: siesaOptions.cesantias,
			banco_siesa: siesaOptions.bancos,
		};
		const list = catalogMap[fieldname] || [];
		const row = list.find((r) => (r?.value || "") === storedValue);
		return row?.label || storedValue;
	};

	const uploadToFileAPI = (doctype, docname, file) => {
		const formData = new FormData();
		formData.append("file", file);
		formData.append("is_private", 1);
		formData.append("doctype", doctype);
		formData.append("docname", docname);
		return fetch("/api/method/upload_file", {
			method: "POST",
			body: formData,
			credentials: "same-origin",
			headers: { "X-Frappe-CSRF-Token": frappe.csrf_token },
		})
			.then((r) => r.json())
			.then((r) => {
				if (!r.message?.file_url) throw new Error("upload_error");
				return r.message.file_url;
			});
	};

	const statusColor = (status) => {
		if (status === "Aprobado") return "green";
		if (status === "Subido") return "blue";
		if (status === "Rechazado") return "red";
		return "orange";
	};

	const sectionTone = (percent) => {
		const value = Number(percent || 0);
		if (value >= 100) return "green";
		if (value >= 50) return "blue";
		return "orange";
	};

	const metadataConfig = () => ({
		"Certificado de EPS (Salud).": {
			title: "Completa la información",
			fields: [
				{
					fieldname: "eps_siesa",
					label: "Selecciona tu EPS",
					fieldtype: "Select",
					options: toSelectOptions(siesaOptions.eps),
					reqd: 1,
				},
			],
		},
		"Certificado de fondo de pensiones.": {
			title: "Completa la información",
			fields: [
				{
					fieldname: "afp_siesa",
					label: "Selecciona tu fondo de pensiones",
					fieldtype: "Select",
					options: toSelectOptions(siesaOptions.afp),
					reqd: 1,
				},
			],
		},
		"Certificado de fondo de cesantías.": {
			title: "Completa la información",
			fields: [
				{
					fieldname: "cesantias_siesa",
					label: "Selecciona tu fondo de cesantías",
					fieldtype: "Select",
					options: toSelectOptions(siesaOptions.cesantias),
					reqd: 1,
				},
			],
		},
		"Certificación bancaria (No mayor a 30 días).": {
			title: "Completa la información",
			fields: [
				{
					fieldname: "banco_siesa",
					label: "Selecciona tu banco",
					fieldtype: "Select",
					options: toSelectOptions(siesaOptions.bancos),
					reqd: 1,
				},
				{ fieldname: "tipo_cuenta_bancaria", label: "Tipo de cuenta", fieldtype: "Select", options: "Ahorros\nCorriente\nTarjeta Prepago", reqd: 1 },
				{ fieldname: "numero_cuenta_bancaria", label: "Número de cuenta", fieldtype: "Data", reqd: 1 },
			],
		},
		"Certificados de estudios y/o actas de grado Bachiller y posteriores.": {
			title: "Completa la información",
			fields: [
				{
					fieldname: "nivel_educativo_siesa",
					label: "Nivel educativo",
					fieldtype: "Select",
					options: NIVEL_EDUCATIVO_SIESA_OPTIONS,
					reqd: 1,
				},
			],
		},
	});

	const openMetadataDialog = (documentType, candidateData, onSuccess) => {
		const cfg = metadataConfig()[documentType];
		if (!cfg) {
			frappe.msgprint("Este documento no requiere información adicional.");
			return;
		}

		const d = new frappe.ui.Dialog({
			title: cfg.title,
			fields: cfg.fields,
			primary_action_label: "Guardar",
			primary_action(values) {
				frappe.call("hubgh.hubgh.page.mis_documentos_candidato.mis_documentos_candidato.save_my_document_meta", {
					document_type: documentType,
					payload: JSON.stringify(values || {}),
				}).then(() => {
					frappe.show_alert({ indicator: "green", message: "Información guardada" });
					d.hide();
					onSuccess?.();
				});
			},
		});
		const initial = candidateData || {};
		(cfg.fields || []).forEach((f) => {
			if (Object.prototype.hasOwnProperty.call(initial, f.fieldname)) {
				d.set_value(f.fieldname, mapStoredCodeToLabel(f.fieldname, initial[f.fieldname]));
			}
		});
		d.show();
	};

	const render = (payload) => {
		const candidate = payload?.candidate;
		const candidateData = payload?.candidate_data || {};
		const docs = payload?.documents || [];
		const sectionProgress = payload?.section_progress || {};

		const summaryHtml = Object.entries(sectionProgress)
			.map(([, info]) => {
				const total = Number(info?.required_total || 0);
				const ok = Number(info?.uploaded_ok || 0);
				const percent = Number(info?.percent || 0);
				const tone = sectionTone(percent);
				return `
					<div class='summary-chip ${tone}'>
						<div class='summary-chip-title'>${frappe.utils.escape_html(info?.label || "Sección")}</div>
						<div class='summary-chip-meta'>${ok}/${total} requeridos • ${percent}%</div>
					</div>
				`;
			})
			.join("");

		const cards = docs
			.map((d) => {
				const hasMeta = Number(d.has_metadata || 0) === 1;
				const requiredTag = d.required_for_hiring ? "<span class='tag required'>Obligatorio</span>" : "<span class='tag optional'>Opcional</span>";
				const approvalTag = d.requires_approval ? "<span class='tag approval'>Requiere aprobación</span>" : "";
				const multipleTag = Number(d.allows_multiple || 0) === 1 ? "<span class='tag optional'>Múltiples archivos</span>" : "";
				const files = Array.isArray(d.files) ? d.files : [];
				const fileLink = d.file ? `<a href='${d.file}' target='_blank' class='btn btn-xs btn-default'>Ver último archivo</a>` : "";
				const fileList = files.length
					? `<div class='doc-files-list'>${files
						.map((f) => {
							const uploaded = f?.uploaded_on ? frappe.datetime.str_to_user(f.uploaded_on) : "";
							return `<div class='doc-file-item'><a href='${f.file}' target='_blank'>Archivo</a> <span class='text-muted'>(${frappe.utils.escape_html(f.status || "Pendiente")}${uploaded ? ` • ${frappe.utils.escape_html(uploaded)}` : ""})</span></div>`;
						})
						.join("")}</div>`
					: "";
				const metaButton = hasMeta
					? `<button class='btn btn-xs btn-default action-meta' data-document='${frappe.utils.escape_html(d.document_type)}'>Completa la información</button>`
					: "";
				return `
					<div class='doc-card'>
						<div class='doc-head'>
							<div>
								<div class='doc-title'>${frappe.utils.escape_html(d.label || d.document_type)}</div>
								<div class='doc-tags'>${requiredTag}${approvalTag}${multipleTag}</div>
							</div>
							<span class='indicator-pill ${statusColor(d.status)}'>${frappe.utils.escape_html(d.status || "Pendiente")}</span>
						</div>
						<div class='doc-actions'>
							<button class='btn btn-xs btn-primary action-upload' data-document='${frappe.utils.escape_html(d.document_type)}'>Subir / Reemplazar</button>
							${metaButton}
							${fileLink}
						</div>
						${fileList}
					</div>
				`;
			})
			.join("");

		$root.html(`
			<style>
				.mis-documentos-candidato { padding: 8px; }
				.mis-documentos-candidato .header-note { margin-bottom: 12px; color: #475569; }
				.mis-documentos-candidato .summary-grid { display: grid; grid-template-columns: repeat(auto-fit,minmax(210px,1fr)); gap: 8px; margin-bottom: 12px; }
				.mis-documentos-candidato .summary-chip { border-radius: 10px; border: 1px solid #e2e8f0; padding: 10px; }
				.mis-documentos-candidato .summary-chip-title { font-weight: 700; }
				.mis-documentos-candidato .summary-chip-meta { color: #475569; font-size: 12px; margin-top: 2px; }
				.mis-documentos-candidato .summary-chip.green { background: #f0fdf4; border-color: #86efac; }
				.mis-documentos-candidato .summary-chip.blue { background: #eff6ff; border-color: #93c5fd; }
				.mis-documentos-candidato .summary-chip.orange { background: #fff7ed; border-color: #fdba74; }
				.mis-documentos-candidato .grid { display: grid; grid-template-columns: repeat(auto-fill,minmax(300px,1fr)); gap: 12px; }
				.mis-documentos-candidato .doc-card { border: 1px solid #e2e8f0; border-radius: 12px; padding: 12px; background: #fff; }
				.mis-documentos-candidato .doc-head { display: flex; justify-content: space-between; gap: 8px; }
				.mis-documentos-candidato .doc-title { font-weight: 700; margin-bottom: 6px; }
				.mis-documentos-candidato .doc-tags { display: flex; gap: 6px; flex-wrap: wrap; }
				.mis-documentos-candidato .tag { font-size: 11px; padding: 2px 8px; border-radius: 999px; background: #f1f5f9; }
				.mis-documentos-candidato .required { background: #fee2e2; color: #991b1b; }
				.mis-documentos-candidato .optional { background: #e0f2fe; color: #0c4a6e; }
				.mis-documentos-candidato .approval { background: #ede9fe; color: #5b21b6; }
				.mis-documentos-candidato .indicator-pill { font-size: 11px; padding: 3px 8px; border-radius: 999px; height: fit-content; }
				.mis-documentos-candidato .indicator-pill.green { background: #dcfce7; color: #166534; }
				.mis-documentos-candidato .indicator-pill.blue { background: #dbeafe; color: #1d4ed8; }
				.mis-documentos-candidato .indicator-pill.orange { background: #ffedd5; color: #9a3412; }
				.mis-documentos-candidato .indicator-pill.red { background: #fee2e2; color: #991b1b; }
				.mis-documentos-candidato .doc-actions { margin-top: 12px; display: flex; gap: 8px; flex-wrap: wrap; }
				.mis-documentos-candidato .doc-files-list { margin-top: 8px; display: grid; gap: 2px; }
				.mis-documentos-candidato .doc-file-item { font-size: 12px; color: #475569; }
			</style>
			<div class='header-note'>
				Carga tus documentos en esta bandeja. Solo tú y el equipo autorizado pueden verlos. Candidato: <b>${frappe.utils.escape_html(candidate || "")}</b>
			</div>
			<div class='summary-grid'>${summaryHtml || ""}</div>
			<div class='grid'>${cards || "<div class='text-muted'>No hay documentos configurados.</div>"}</div>
		`);

		$root.find(".action-upload").on("click", function () {
			const documentType = $(this).data("document");
			const picker = $("<input type='file' class='d-none' />");
			picker.on("change", function () {
				const file = this.files[0];
				if (!file) return;
				uploadToFileAPI("Candidato", candidate, file)
					.then((fileUrl) =>
						frappe.call("hubgh.hubgh.page.mis_documentos_candidato.mis_documentos_candidato.upload_my_document", {
							document_type: documentType,
							file_url: fileUrl,
						})
					)
					.then(() => {
						frappe.show_alert({ indicator: "green", message: "Documento cargado correctamente" });
						load();
					});
			});
			picker.trigger("click");
		});

		$root.find(".action-meta").on("click", function () {
			const documentType = $(this).data("document");
			openMetadataDialog(documentType, candidateData, load);
		});
	};

	const load = () => {
		$root.html("<div class='text-muted'>Cargando tus documentos...</div>");
		Promise.all([
			frappe.call("hubgh.hubgh.page.mis_documentos_candidato.mis_documentos_candidato.get_siesa_options"),
			frappe.call("hubgh.hubgh.page.mis_documentos_candidato.mis_documentos_candidato.get_my_documents"),
		]).then(([siesaRes, docsRes]) => {
			siesaOptions = siesaRes?.message || { eps: [], afp: [], cesantias: [], bancos: [] };
			render(docsRes?.message || {});
		});
	};

	load();
};
