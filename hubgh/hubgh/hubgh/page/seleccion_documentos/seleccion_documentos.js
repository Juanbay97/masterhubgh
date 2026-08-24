frappe.pages["seleccion_documentos"].on_page_load = function(wrapper) {
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
		window.Intl.Locale = function(locale, options) {
			const normalizedLocale = locale && locale !== "undefined" ? locale : safeLang;
			return new NativeLocale(normalizedLocale, options);
		};
		window.Intl.Locale.prototype = NativeLocale.prototype;
		window.Intl.__hubghSafeLocalePatched = true;
	}
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Selección - Control documental",
		single_column: true,
	});

	const ui = window.hubghBandejasUI || {
		injectBaseStyles() {},
		injectScopedStyles() {},
		esc: value => frappe.utils.escape_html(value == null ? "" : String(value)),
		indicator: (tone, label) => `<span class='indicator-pill ${frappe.utils.escape_html(tone)}'>${frappe.utils.escape_html(label)}</span>`,
		yesNoBadge: ok => (ok ? "<span class='indicator-pill green'>Completo</span>" : "<span class='indicator-pill orange'>Pendiente</span>"),
	};

	ui.injectBaseStyles();
	ui.injectScopedStyles("seleccion-documentos", `
		.sel-docs-badges { display: grid; grid-template-columns: repeat(4, minmax(150px, 1fr)); gap: 8px; }
		.sel-docs-subtitle { color: #64748b; font-size: 12px; }
		.sel-docs-toolbar-actions { display: flex; gap: 8px; flex-wrap: wrap; margin-left: auto; }
		.sel-docs-summary { display: grid; grid-template-columns: repeat(4, minmax(140px, 1fr)); gap: 8px; }
		.sel-docs-summary-card { border: 1px solid #e2e8f0; border-radius: 12px; background: #fff; padding: 10px 12px; display: grid; gap: 4px; }
		.sel-docs-summary-label { color: #64748b; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: .03em; }
		.sel-docs-summary-value { color: #0f172a; font-size: 22px; font-weight: 700; line-height: 1; }
		.sel-docs-table-wrap { margin-top: 10px; border: 1px solid #e2e8f0; border-radius: 10px; overflow: hidden; }
		.sel-docs-table-wrap table { margin: 0; }
		.sel-docs-table-wrap th { background: #f8fafc; color: #475569; font-size: 12px; }
		.sel-docs-dialog-head { display: grid; gap: 8px; margin-bottom: 10px; }
		.sel-docs-dialog-head-line { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
		.sel-docs-note { padding: 10px 12px; border: 1px solid #bfdbfe; background: #eff6ff; border-radius: 10px; color: #1e40af; font-size: 12px; }
		.sel-docs-grid-2 { display: grid; grid-template-columns: repeat(2, minmax(160px, 1fr)); gap: 8px; }
		.sel-req-docs { display: grid; gap: 6px; margin-top: 8px; }
		.sel-req-doc { border: 1px solid #e2e8f0; border-radius: 8px; padding: 8px 10px; background: #fff; display: flex; justify-content: space-between; gap: 8px; align-items: center; }
		.sel-req-doc-title { font-size: 12px; font-weight: 600; }
		.sel-docs-priority-line { display: flex; justify-content: space-between; gap: 10px; flex-wrap: wrap; align-items: center; width: 100%; }
		.sel-docs-priority-copy { color: #475569; font-size: 12px; font-weight: 600; }
		.sel-docs-secondary-actions { display: flex; gap: 6px; flex-wrap: wrap; justify-content: flex-end; width: 100%; }
		.sel-docs-secondary-actions .btn-link { padding: 0 2px; }
		.sel-docs-empty-actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 12px; }
		@media (max-width: 768px) {
			.sel-docs-badges,
			.sel-docs-summary { grid-template-columns: repeat(2, minmax(120px, 1fr)); }
			.sel-docs-toolbar-actions { margin-left: 0; width: 100%; }
		}
	`);

	const $tabsWrap = $(`
		<div class='hubgh-board-toolbar' style='margin-bottom:8px'>
			<button class='btn btn-sm btn-primary tab-board'>Bandeja</button>
			<button class='btn btn-sm btn-default tab-post-handoff'>Enviados con pendientes</button>
		</div>
	`).appendTo(page.body);
	const $root = $("<div class='hubgh-board-shell'></div>").appendTo(page.body);
	let state = {
		rows: [], postHandoffRows: [], search: "", status: "all", view: "board",
		uploadDocTypes: [], uploadDocTypesLoaded: false,
		// Gate-failure fix (orchestrator re-run, item 1): the exemption picker must
		// NEVER reuse the upload catalog above — upload legitimately allows any
		// active type, exemption only makes sense for the required set. Separate
		// cache, separate endpoint (list_exemptable_document_types).
		exemptDocTypes: [], exemptDocTypesLoaded: false,
		// ADR-6: kept separate from search/status above — getFilteredRows reads
		// state.rows and calls board-only helpers (canSendToRL/isInMedicalExam),
		// so sharing state would leak the tab's filters into the board and vice versa.
		postHandoffSearch: "", postHandoffStatus: "all",
	};
	const esc = ui.esc;

	// ADR-4: fetch the active document-type catalog once and cache it on state so
	// every upload entry point (tray row, tray primary action, detail dialog, tab)
	// shares the same source instead of re-fetching or falling back to a hardcoded list.
	const ensureUploadDocTypes = () => {
		if (state.uploadDocTypesLoaded) return Promise.resolve(state.uploadDocTypes);
		return frappe.call("hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.list_upload_document_types")
			.then(r => {
				state.uploadDocTypes = r.message || [];
				state.uploadDocTypesLoaded = true;
				return state.uploadDocTypes;
			})
			.catch(() => {
				state.uploadDocTypes = [];
				state.uploadDocTypesLoaded = false;
				return null;
			});
	};

	// Gate-failure fix (item 1): required-only catalog for the exemption picker.
	// Deliberately a separate fetch/cache from ensureUploadDocTypes — the upload
	// dialog legitimately offers any active type, the exemption dialog must not.
	const ensureExemptDocTypes = () => {
		if (state.exemptDocTypesLoaded) return Promise.resolve(state.exemptDocTypes);
		return frappe.call("hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.list_exemptable_document_types")
			.then(r => {
				state.exemptDocTypes = r.message || [];
				state.exemptDocTypesLoaded = true;
				return state.exemptDocTypes;
			})
			.catch(() => {
				state.exemptDocTypes = [];
				state.exemptDocTypesLoaded = false;
				return null;
			});
	};

	const setActiveTab = view => {
		$tabsWrap.find(".tab-board")
			.toggleClass("btn-primary", view === "board")
			.toggleClass("btn-default", view !== "board");
		$tabsWrap.find(".tab-post-handoff")
			.toggleClass("btn-primary", view === "post_handoff")
			.toggleClass("btn-default", view !== "post_handoff");
	};

	const cleanupModal = dialog => {
		dialog.$wrapper.on("hidden.bs.modal", () => {
			$("body").removeClass("modal-open");
			$(".modal-backdrop").remove();
			page.wrapper.focus();
		});
	};

	const processBadge = status => {
		const norm = (status || "").toLowerCase();
		if (norm.includes("examen médico")) return ui.indicator("blue", status || "En Examen Médico");
		if (norm.includes("listo para contratar")) return ui.indicator("green", status || "Listo");
		if (norm.includes("rechaz")) return ui.indicator("red", status || "Rechazado");
		return ui.indicator("orange", status || "En proceso");
	};

	const conceptBadge = concept => {
		const c = (concept || "Pendiente").toLowerCase();
		if (c === "favorable") return ui.indicator("green", "Médico: Favorable");
		if (c === "desfavorable") return ui.indicator("red", "Médico: Desfavorable");
		if (c === "aplazado") return ui.indicator("orange", "Médico: Aplazado");
		return ui.indicator("gray", `Médico: ${concept || "Pendiente"}`);
	};

	const isInMedicalExam = row => (row?.estado_proceso || "") === "En Examen Médico";
	const hasResolvedMedicalConcept = row => {
		const concept = (row?.concepto_medico || "").trim().toLowerCase();
		return ["favorable", "desfavorable", "aplazado"].includes(concept);
	};
	const canSendToRL = row => !!(row?.can_manage && row?.completo && row?.sagrilaft_ok && (row?.concepto_medico || "") === "Favorable" && !isInMedicalExam(row));
	// canSendToRLIncomplete: HARD gate passes (Favorable + SAGRILAFT) but docs are incomplete.
	// Server will require motivo; client shows dialog with motivo field.
	const canSendToRLIncomplete = row => !!(row?.can_manage && !row?.completo && row?.sagrilaft_ok && (row?.concepto_medico || "") === "Favorable" && !isInMedicalExam(row));
	const canShowSendToRL = row => !!(row?.can_manage && (row?.concepto_medico || "") === "Favorable" && !isInMedicalExam(row));
	const getPrimaryAction = row => {
		if (canSendToRL(row)) {
			return { type: "send", label: "Enviar a RRLL", tone: "btn-primary", copy: "Handoff listo para formalización" };
		}
		if (canSendToRLIncomplete(row)) {
			return { type: "send", label: "Enviar a RRLL (incompleto)", tone: "btn-warning", copy: "Documentación incompleta — requiere motivo" };
		}
		if (row?.can_manage && !isInMedicalExam(row) && !hasResolvedMedicalConcept(row) && !canShowSendToRL(row)) {
			return { type: "medical", label: "Enviar a examen", tone: "btn-warning", copy: "Siguiente paso operativo" };
		}
		return { type: "upload", label: "Cargar soporte", tone: "btn-default", copy: "Completá lo pendiente sin salir" };
	};

	const ensureCorreccionDialogLoaded = () => {
		if (window.hubgh && typeof window.hubgh.openCorreccionDatosDialog === "function") {
			return Promise.resolve();
		}
		return new Promise(resolve => {
			frappe.require("/assets/hubgh/js/correccion_datos_candidato_dialog.js", resolve);
		});
	};

	const openSimpleDialog = (title, fields, primaryLabel, onPrimary) => {
		const dialog = new frappe.ui.Dialog({ title, fields });
		dialog.set_primary_action(primaryLabel, () => {
			onPrimary(dialog.get_values() || {});
			dialog.hide();
		});
		dialog.show();
		cleanupModal(dialog);
		return dialog;
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
			.then(r => r.json())
			.then(r => {
				if (!r.message?.file_url) throw new Error("upload_error");
				return r.message.file_url;
			});
	};

	const quickUpload = (candidate, documentType) => {
		const picker = $("<input type='file' class='d-none' />");
		picker.on("change", function() {
			const file = this.files[0];
			if (!file) return;
			uploadToFileAPI("Candidato", candidate, file)
				.then(fileUrl => frappe.call("hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.upload_candidate_document", {
					candidate,
					document_type: documentType,
					file_url: fileUrl,
				}))
				.then(() => {
					frappe.show_alert({ indicator: "green", message: "Documento cargado" });
					// Pre-existing bug fixed here: this always reloaded the main board even
					// when invoked from the post-handoff tab's row action, silently switching
					// the visible view back to "Bandeja" after an upload. Reload whichever
					// view is actually active so ADR-6 filters on the tab survive (C4.5).
					if (state.view === "post_handoff") { loadPostHandoff(); } else { loadBoard(); }
				});
		});
		picker.trigger("click");
	};

	const openUploadCatalogErrorDialog = () => {
		const dialog = new frappe.ui.Dialog({
			title: "Subir documento de selección",
			fields: [{ fieldtype: "HTML", fieldname: "content" }],
			primary_action_label: "Subir",
			primary_action: () => {},
		});
		dialog.fields_dict.content.$wrapper.html(`
			<div class='sel-docs-note' style='border-color:#fecaca;background:#fef2f2;color:#991b1b;'>
				No se pudo cargar el catálogo de documentos. Recarga la página.
			</div>
		`);
		dialog.disable_primary_action();
		dialog.show();
		cleanupModal(dialog);
	};

	// ADR-4 ordering, extracted so both the upload picker and the exemption
	// picker (C3.1) share the exact same missing-first catalog logic instead
	// of each re-implementing it.
	const buildMissingFirstDocOptions = (catalog, missing = []) => {
		const missingList = (missing || []).filter(Boolean);
		const missingSet = new Set(missingList);
		const catalogNames = new Set(catalog.map(row => row.name));
		// Missing-first ordering (ADR-4): missing docs still offered by the catalog come
		// first and default-select; legacy missing names absent from the active catalog
		// would fail backend validation, so they are dropped from the Select but kept
		// visible in the warning copy the caller renders.
		const missingInCatalog = missingList.filter(name => catalogNames.has(name));
		const rest = catalog.filter(row => !missingSet.has(row.name)).map(row => row.name);
		return { optionsStr: [...missingInCatalog, ...rest].join("\n"), missingInCatalog, missingList };
	};

	const openSelectionDocsUploadDialog = (candidate, missing = []) => {
		ensureUploadDocTypes().then(catalog => {
			if (!catalog || !catalog.length) {
				openUploadCatalogErrorDialog();
				return;
			}
			const { optionsStr, missingInCatalog, missingList } = buildMissingFirstDocOptions(catalog, missing);
			const dialogFields = [];
			if (missingList.length) {
				dialogFields.push({
					fieldtype: "HTML",
					options: `<div class='sel-docs-note' style='border-color:#fbbf24;background:#fffbeb;color:#92400e;margin-bottom:8px;'>Documentos faltantes: <b>${esc(missingList.join(", "))}</b></div>`,
				});
			}
			dialogFields.push({
				fieldname: "document_type",
				label: "Documento",
				fieldtype: "Select",
				options: optionsStr,
				default: missingInCatalog[0] || undefined,
				reqd: 1,
			});
			openSimpleDialog("Subir documento de selección", dialogFields, "Subir", values => {
				quickUpload(candidate, values.document_type);
			});
		});
	};

	// Gate-failure fix (item 3): a stable, distinguishable, explicitly visible
	// warning block — .alert.alert-warning plus a dedicated sagrilaft-exempt-warning
	// class so it is queryable/verifiable independent of styling. Shared markup
	// for both the fixed-type and picker exemption dialogs.
	const sagrilaftExemptWarningHtml = () => `
		<div class='alert alert-warning sagrilaft-exempt-warning' role='alert'>
			<strong>Atención:</strong> exonerar SAGRILAFT no habilita el envío del candidato a Relaciones Laborales.
			El documento físico de SAGRILAFT sigue siendo obligatorio para ese envío.
		</div>
	`;

	// C3.1 — per-row "Exonerar" entry point (post-handoff tab): a document-type
	// picker (missing-first) restricted to the REQUIRED catalog only (gate-failure
	// fix, item 1) — deliberately NOT ensureUploadDocTypes/the upload catalog:
	// upload legitimately allows any active type, exemption only makes sense for
	// documents that count toward hiring progress. The SAGRILAFT warning toggles
	// dynamically since the selected type can change, unlike the fixed-type
	// dialog used from the candidate detail table (openExemptDocumentDialog below).
	const openExemptDocumentPickerDialog = (candidate, missing = [], { onSuccess } = {}) => {
		ensureExemptDocTypes().then(catalog => {
			if (!catalog || !catalog.length) {
				openUploadCatalogErrorDialog();
				return;
			}
			const { optionsStr, missingInCatalog, missingList } = buildMissingFirstDocOptions(catalog, missing);
			const defaultType = missingInCatalog[0] || (catalog[0] && catalog[0].name) || "";

			const fields = [];
			if (missingList.length) {
				fields.push({
					fieldtype: "HTML",
					options: `<div class='sel-docs-note' style='border-color:#fbbf24;background:#fffbeb;color:#92400e;margin-bottom:8px;'>Documentos faltantes: <b>${esc(missingList.join(", "))}</b></div>`,
				});
			}
			fields.push({
				fieldname: "document_type",
				label: "Documento",
				fieldtype: "Select",
				options: optionsStr,
				default: defaultType,
				reqd: 1,
				onchange() {
					const selected = (d.get_value("document_type") || "").toUpperCase();
					d.fields_dict.sagrilaft_warning.$wrapper.toggle(selected === "SAGRILAFT");
				},
			});
			fields.push({
				fieldname: "sagrilaft_warning",
				fieldtype: "HTML",
				options: sagrilaftExemptWarningHtml(),
			});
			fields.push({
				fieldname: "motivo",
				label: "Motivo de la exención",
				fieldtype: "Small Text",
				reqd: 1,
				description: "Obligatorio. Queda registrado en la trazabilidad del candidato.",
			});

			const d = new frappe.ui.Dialog({
				title: "Exonerar documento",
				fields,
				primary_action_label: "Exonerar",
				primary_action(values) {
					const motivo = (values.motivo || "").trim();
					if (!motivo) {
						frappe.msgprint({ title: "Motivo requerido", message: "Ingresá el motivo de la exención.", indicator: "red" });
						return;
					}
					frappe.call("hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.exempt_candidate_document", {
						candidate,
						document_type: values.document_type,
						motivo,
					}).then(() => {
						frappe.show_alert({ indicator: "blue", message: "Documento exonerado" });
						d.hide();
						if (typeof onSuccess === "function") onSuccess();
					}).catch(err => {
						const msg = (err && (err.message || err.exc || err._server_messages)) || "No fue posible exonerar el documento.";
						frappe.msgprint(msg);
					});
				},
			});
			d.show();
			cleanupModal(d);
			d.fields_dict.sagrilaft_warning.$wrapper.toggle((defaultType || "").toUpperCase() === "SAGRILAFT");
		});
	};

	// C3.2/C3.3 — Grant/revoke exemption dialogs (Batch C). Both reuse the same
	// dialog machinery as the upload dialog; motivo is server-validated too
	// (RED-2 in design.md), this reqd:1 is a UX affordance, not the real gate.
	const openExemptDocumentDialog = (candidate, documentType, { onSuccess } = {}) => {
		const isSagrilaft = (documentType || "").toUpperCase() === "SAGRILAFT";
		const sagrilaftWarning = isSagrilaft ? sagrilaftExemptWarningHtml() : "";
		const dialogFields = [];
		if (sagrilaftWarning) {
			dialogFields.push({ fieldtype: "HTML", options: sagrilaftWarning });
		}
		dialogFields.push({
			fieldname: "motivo",
			label: "Motivo de la exención",
			fieldtype: "Small Text",
			reqd: 1,
			description: "Obligatorio. Queda registrado en la trazabilidad del candidato.",
		});
		openSimpleDialog(`Exonerar documento: ${documentType}`, dialogFields, "Exonerar", values => {
			const motivo = (values.motivo || "").trim();
			if (!motivo) {
				frappe.msgprint({ title: "Motivo requerido", message: "Ingresá el motivo de la exención.", indicator: "red" });
				return;
			}
			frappe.call("hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.exempt_candidate_document", {
				candidate,
				document_type: documentType,
				motivo,
			}).then(() => {
				frappe.show_alert({ indicator: "blue", message: "Documento exonerado" });
				if (typeof onSuccess === "function") onSuccess();
			}).catch(err => {
				const msg = (err && (err.message || err.exc || err._server_messages)) || "No fue posible exonerar el documento.";
				frappe.msgprint(msg);
			});
		});
	};

	const openRevokeExemptionDialog = (candidate, documentType, { onSuccess } = {}) => {
		const d = new frappe.ui.Dialog({
			title: `Revocar exención: ${documentType}`,
			fields: [
				{ fieldtype: "HTML", fieldname: "warning" },
				{ fieldname: "motivo", label: "Motivo de la revocación (opcional)", fieldtype: "Small Text" },
			],
			primary_action_label: "Revocar",
			primary_action(values) {
				frappe.call("hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.revoke_candidate_document_exemption", {
					candidate,
					document_type: documentType,
					motivo: (values.motivo || "").trim() || undefined,
				}).then(() => {
					frappe.show_alert({ indicator: "orange", message: "Exención revocada" });
					d.hide();
					if (typeof onSuccess === "function") onSuccess();
				}).catch(err => {
					const msg = (err && (err.message || err.exc || err._server_messages)) || "No fue posible revocar la exención.";
					frappe.msgprint(msg);
				});
			},
		});
		d.fields_dict.warning.$wrapper.html(`
			<div class='sel-docs-note'>El documento vuelve a estado <b>Pendiente</b> y deberá subirse o exonerarse nuevamente.</div>
		`);
		d.show();
		cleanupModal(d);
	};

	const openDetail = candidate => {
		frappe.call("hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.candidate_detail", { candidate })
			.then(r => {
				const data = r.message || {};
				const progress = data.progress || {};
				const completionTone = progress.is_complete ? "green" : "orange";
				const completionLabel = progress.is_complete ? "Documentación completa" : "Documentación incompleta";
				const candidateData = data.candidate || {};

				// ADR-5: rendered directly from the server-sourced selection_doc_status
				// (get_selection_operational_document_names()), not the old 4-name JS
				// constant that silently hid "Examen Médico" (the 5th operational doc).
				const requiredDocsHtml = (data.selection_doc_status || []).map(rowStatus => {
					const requiredTag = rowStatus.required ? "<span class='indicator-pill red'>Requerido</span>" : "<span class='indicator-pill blue'>Opcional</span>";
					return `
						<div class='sel-req-doc'>
							<div class='sel-req-doc-title'>${esc(rowStatus.document_type)}</div>
							<div>${requiredTag} ${ui.yesNoBadge(!!rowStatus.uploaded_ok)}</div>
						</div>
					`;
				}).join("");

				const canDeleteDoc = !!data.can_delete_document;
				// C3.1/C3.4: exemption affordance is gated server-side (can_exempt_documents,
				// same pattern as can_delete_document) and only offered for the required
				// catalog (required_for_hiring) — a non-required type can still be exempted
				// via direct API call (PR B's exempt_candidate_document has no
				// is_required_for_hiring gate, only an active-type check), but this UI never
				// offers that action for a non-required document.
				const canExemptDocs = !!data.can_exempt_documents;
				const requiredTypeNames = new Set(
					(data.upload_doc_types || []).filter(t => t.required_for_hiring).map(t => t.name)
				);
				const docsHtml = (data.documents || []).map(d => {
					const deleteBtn = (canDeleteDoc && d.name)
						? `<button class='btn btn-xs btn-link text-danger action-delete-pdoc' data-pd='${esc(d.name)}' data-dtype='${esc(d.document_type || "")}' data-file='${esc(d.file || "")}' title='Eliminar permanentemente'><i class='fa fa-trash'></i></button>`
						: "";
					const isExento = d.status === "Exento";
					const statusCell = isExento
						? `<span class='indicator-pill blue exempted-doc-pill' title='${esc(d.exencion_motivo || "")}'>Exonerado</span>`
						: esc(d.status || "Pendiente");
					let exemptionBtn = "";
					if (canExemptDocs) {
						if (isExento) {
							exemptionBtn = `<button class='btn btn-xs btn-link text-warning action-revoke-exemption' data-dtype='${esc(d.document_type || "")}' title='Motivo: ${esc(d.exencion_motivo || "")}'>Revocar</button>`;
						} else if (!d.file && d.status !== "Subido" && d.status !== "Aprobado" && requiredTypeNames.has(d.document_type)) {
							exemptionBtn = `<button class='btn btn-xs btn-link action-exempt-doc' data-dtype='${esc(d.document_type || "")}'>Exonerar</button>`;
						}
					}
					return `
					<tr>
						<td>${esc(d.document_type || "")}</td>
						<td>${statusCell}</td>
						<td>${esc(d.uploaded_by || "")}</td>
						<td>${frappe.datetime.str_to_user(d.uploaded_on || "") || ""}</td>
						<td>${d.file ? `<a href='${d.file}' target='_blank'>Ver</a>` : ""}</td>
						<td>${deleteBtn}${exemptionBtn}</td>
					</tr>
				`;
				}).join("");

				const candidateInfoHtml = [
					["Documento", candidateData.numero_documento],
					["PDV destino", candidateData.pdv_destino_nombre || candidateData.pdv_destino],
					["Cargo postulado", candidateData.cargo_postulado],
					["Ciudad", candidateData.ciudad],
					["Localidad", candidateData.localidad],
					["Dirección", candidateData.direccion],
					["Barrio", candidateData.barrio],
					["País procedencia", candidateData.procedencia_pais],
					["Departamento procedencia", candidateData.procedencia_departamento],
					["Ciudad procedencia", candidateData.procedencia_ciudad],
					["Banco", candidateData.banco_siesa],
					["Tipo cuenta", candidateData.tipo_cuenta_bancaria],
					["Nro. cuenta", candidateData.numero_cuenta_bancaria],
					["Contacto emergencia (nombre)", candidateData.contacto_emergencia_nombre],
					["Contacto emergencia (teléfono)", candidateData.contacto_emergencia_telefono],
				].map(([label, value]) => `
					<div class='sel-docs-summary-card'>
						<div class='sel-docs-summary-label'>${esc(label)}</div>
						<div class='sel-docs-summary-value' style='font-size:14px; line-height:1.3;'>${esc(value || "—")}</div>
					</div>
				`).join("");

				const dialog = new frappe.ui.Dialog({
					title: `Detalle documental: ${candidateData.full_name || candidate}`,
					fields: [{ fieldtype: "HTML", fieldname: "content" }],
					size: "extra-large",
				});
				dialog.fields_dict.content.$wrapper.html(`
					<div class='sel-docs-dialog-head'>
						<div class='sel-docs-dialog-head-line'>
							${processBadge(candidateData.estado_proceso)}
							${conceptBadge(candidateData.concepto_medico)}
							${ui.indicator(completionTone, completionLabel)}
							<span class='text-muted'>${esc(progress.required_ok || 0)}/${esc(progress.required_total || 0)} requeridos</span>
						</div>
						<div class='sel-docs-note'>
							Avance documental: <b>${esc(progress.percent || 0)}%</b>
						</div>
						<div>
							<button class='btn btn-sm btn-default btn-download-zip'>Descargar ZIP</button>
							<button class='btn btn-sm btn-primary btn-upload-selection-doc'>Subir documento</button>
						</div>
						<div class='sel-req-docs'>${requiredDocsHtml}</div>
						<div class='sel-docs-summary'>${candidateInfoHtml}</div>
					</div>
					<div class='sel-docs-table-wrap'>
						<table class='table table-sm'>
							<thead><tr><th>Tipo</th><th>Estado</th><th>Subido por</th><th>Fecha</th><th>Archivo</th><th></th></tr></thead>
							<tbody>${docsHtml || "<tr><td colspan='6' class='text-muted'>Sin documentos</td></tr>"}</tbody>
						</table>
					</div>
				`);

				dialog.fields_dict.content.$wrapper.find(".btn-download-zip").on("click", () => {
					const url = "/api/method/hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.download_candidate_documents_zip?candidate=" + encodeURIComponent(candidate);
					window.open(url, "_blank");
				});
				dialog.fields_dict.content.$wrapper.find(".btn-upload-selection-doc").on("click", () => openSelectionDocsUploadDialog(candidate, progress.missing || []));
				dialog.fields_dict.content.$wrapper.find(".action-delete-pdoc").on("click", function() {
					const pdocName = $(this).data("pd");
					const dtype = $(this).data("dtype") || "";
					const fileUrl = $(this).data("file") || "";
					openDeletePersonDocumentDialog({ pdocName, documentType: dtype, fileUrl, onSuccess: () => {
						dialog.hide();
						openDetail(candidate);
					}});
				});
				dialog.fields_dict.content.$wrapper.find(".action-exempt-doc").on("click", function() {
					const dtype = $(this).data("dtype") || "";
					openExemptDocumentDialog(candidate, dtype, { onSuccess: () => {
						dialog.hide();
						openDetail(candidate);
					}});
				});
				dialog.fields_dict.content.$wrapper.find(".action-revoke-exemption").on("click", function() {
					const dtype = $(this).data("dtype") || "";
					openRevokeExemptionDialog(candidate, dtype, { onSuccess: () => {
						dialog.hide();
						openDetail(candidate);
					}});
				});
				dialog.show();
				cleanupModal(dialog);
			});
	};

	const openDeletePersonDocumentDialog = ({ pdocName, documentType, fileUrl, onSuccess }) => {
		const fileLabel = fileUrl ? (fileUrl.split("/").pop() || fileUrl) : "(sin archivo)";
		const d = new frappe.ui.Dialog({
			title: "Eliminar documento permanentemente",
			fields: [
				{ fieldtype: "HTML", fieldname: "warning" },
				{ fieldtype: "Long Text", fieldname: "motivo", label: "Motivo (obligatorio para auditoría)", reqd: 1 },
			],
			primary_action_label: "Eliminar permanentemente",
			primary_action: values => {
				const motivo = (values.motivo || "").trim();
				if (!motivo) {
					frappe.msgprint({ title: "Motivo requerido", message: "Ingrese el motivo del borrado.", indicator: "red" });
					return;
				}
				d.set_primary_action(__("Eliminando..."), null);
				d.disable_primary_action();
				frappe.call({
					method: "hubgh.hubgh.api.correcciones.delete_person_document",
					args: { person_document_name: pdocName, motivo },
				}).then(r => {
					if (r && r.message && r.message.deleted) {
						frappe.show_alert({ message: "Documento eliminado permanentemente", indicator: "red" });
						d.hide();
						if (typeof onSuccess === "function") onSuccess();
					} else {
						d.enable_primary_action();
						d.set_primary_action("Eliminar permanentemente", d.primary_action);
					}
				}).catch(() => {
					d.enable_primary_action();
					d.set_primary_action("Eliminar permanentemente", d.primary_action);
				});
			},
		});
		d.fields_dict.warning.$wrapper.html(`
			<div style='background:#fef2f2;border:1px solid #fecaca;color:#991b1b;padding:10px 12px;border-radius:6px;font-size:13px;line-height:1.4;'>
				<strong>Esta acción ELIMINA PERMANENTEMENTE el archivo del disco.</strong>
				No se puede deshacer. Se registra en los comentarios del candidato para auditoría.
				<div style='margin-top:8px;font-size:12px;'>
					<div><b>Tipo:</b> ${frappe.utils.escape_html(documentType || "—")}</div>
					<div><b>Archivo:</b> ${frappe.utils.escape_html(fileLabel)}</div>
				</div>
			</div>
		`);
		d.get_primary_btn().removeClass("btn-primary").addClass("btn-danger");
		d.show();
		cleanupModal(d);
	};

	const getFilteredRows = () => {
		const q = (state.search || "").trim().toLowerCase();
		return (state.rows || []).filter(row => {
			if (q) {
				const blob = [row.full_name, row.name, row.numero_documento, row.pdv_destino_nombre, row.pdv_destino, row.cargo_postulado, row.estado_proceso].filter(Boolean).join(" ").toLowerCase();
				if (!blob.includes(q)) return false;
			}
			if (state.status === "complete" && !row.completo) return false;
			if (state.status === "pending" && row.completo) return false;
			if (state.status === "rl_ready" && !canSendToRL(row)) return false;
			if (state.status === "medical" && !isInMedicalExam(row)) return false;
			if (state.status === "in_process" && row.estado_proceso === "Listo para Contratar") return false;
			return true;
		});
	};

	const getSummary = rows => ({
		total: rows.length,
		pending: rows.filter(row => !row.completo).length,
		medical: rows.filter(isInMedicalExam).length,
		rlReady: rows.filter(canSendToRL).length,
	});

	const renderCards = rows => {
		const TERMINAL_OR_AFFILIATED = new Set(["En afiliación", "Listo para Contratar", "Rechazado", "Contratado"]);
		const cards = (rows || []).map(row => {
			const porcentaje = Number(row.avance_porcentaje || 0);
			const progressTone = row.completo ? "green" : (porcentaje >= 100 ? "green" : (porcentaje >= 50 ? "blue" : "orange"));
			const inMedical = isInMedicalExam(row);
			const manageEnabled = !!row.can_manage;
			const primary = getPrimaryAction(row);
			const pdvLabel = row.pdv_destino_nombre || row.pdv_destino || "";
			const canSendToAffiliation = manageEnabled && !TERMINAL_OR_AFFILIATED.has(row.estado_proceso || "");

			return `
				<div class='hubgh-card' data-c='${esc(row.name)}'>
					<div class='hubgh-card-head'>
						<div class='hubgh-main'>
							<div class='hubgh-title-row'>
								<button type='button' class='btn btn-link btn-xs hubgh-name action-detail' data-c='${esc(row.name)}'>${esc(row.full_name || row.name)}</button>
								${processBadge(row.estado_proceso)}
								${conceptBadge(row.concepto_medico)}
								${row.solo_afiliacion ? `<span class='indicator-pill blue' title='Enviado solo a Afiliación con documentación pendiente. Falta envío oficial a RRLL.'>Pendiente RRLL</span>` : ""}
							</div>
							<div class='hubgh-meta'>CC ${esc(row.numero_documento || "-")}</div>
							<div class='hubgh-submeta'>
							<span>${esc(row.cargo_postulado || "Sin cargo")}</span>
							<span class='hubgh-dot'>•</span>
							<span title='${esc(row.pdv_destino || "")}'>${esc(pdvLabel || "Sin PDV")}</span>
						</div>
						</div>
						<div class='hubgh-right'>
							<div>${ui.yesNoBadge(!!row.completo)}</div>
							<div class='hubgh-time'>Actualizado: ${frappe.datetime.str_to_user(row.creation) || "—"}</div>
						</div>
					</div>

					<div class='sel-docs-badges'>
						<div class='hubgh-badge ${row.completo ? "is-complete" : "is-pending"}'>
							<span class='hubgh-badge-label'>Requeridos</span>
							<span>${esc(row.documentos_ok || 0)}/${esc(row.documentos_total || 0)}</span>
						</div>
						<div class='hubgh-badge ${row.completo ? "is-complete" : "is-pending"}'>
							<span class='hubgh-badge-label'>Avance</span>
							${ui.indicator(progressTone, `${esc(porcentaje)}%`)}
						</div>
						<div class='hubgh-badge ${row.sagrilaft_ok ? "is-complete" : "is-pending"}'>
							<span class='hubgh-badge-label'>SAGRILAFT</span>
							${ui.yesNoBadge(!!row.sagrilaft_ok)}
						</div>
						<div class='hubgh-badge ${inMedical ? "is-pending" : "is-complete"}'>
							<span class='hubgh-badge-label'>Progresión</span>
							${ui.indicator(inMedical ? "orange" : "green", inMedical ? "Pausada" : "Activa")}
						</div>
					</div>

					<div class='hubgh-actions'>
						<div class='sel-docs-priority-line'>
							<div class='sel-docs-priority-copy'>${esc(primary.copy)}</div>
							<button class='btn btn-xs ${primary.tone} action-primary' data-c='${esc(row.name)}' data-action='${esc(primary.type)}'>${esc(primary.label)}</button>
						</div>
						<div class='sel-docs-secondary-actions'>
							<button class='btn btn-xs btn-link action-detail' data-c='${esc(row.name)}'>Detalle</button>
							${primary.type === "upload" ? "" : `<button class='btn btn-xs btn-link action-upload-selection' data-c='${esc(row.name)}'>Subir soporte</button>`}
							${canSendToAffiliation ? `<button class='btn btn-xs btn-link text-info action-send-affiliation' data-c='${esc(row.name)}'>Enviar a Afiliación</button>` : ""}
							${manageEnabled ? `<button class='btn btn-xs btn-link action-correccion' data-c='${esc(row.name)}' data-label='${esc(row.full_name || row.name)}'>Corregir datos</button>` : ""}
							${manageEnabled ? `<button class='btn btn-xs btn-link text-danger action-reject' data-c='${esc(row.name)}'>Rechazar</button>` : ""}
						</div>
						<button class='d-none action-medical' data-c='${esc(row.name)}'></button>
						<button class='d-none action-send' data-c='${esc(row.name)}'></button>
					</div>
				</div>
			`;
		}).join("");

		$root.find(".hubgh-cards-wrap").html(cards || `
			<div class='hubgh-empty'>
				<span class='hubgh-empty-title'>No hay candidatos para este foco</span>
				<p class='hubgh-empty-copy'>Ajustá los filtros visibles o revisá la cola de exámenes médicos para retomar el flujo.</p>
				<div class='sel-docs-empty-actions'>
					<button class='btn btn-sm btn-default action-clear-filters'>Limpiar filtros</button>
					<button class='btn btn-sm btn-primary action-go-medical'>Ir a exámenes</button>
				</div>
			</div>
		`);
	};

	const bindEvents = () => {
		$root.find(".filter-search").off("input").on("input", function() {
			state.search = $(this).val() || "";
			renderCards(getFilteredRows());
			bindEvents();
		});

		$root.find(".filter-status").off("change").on("change", function() {
			state.status = $(this).val() || "all";
			renderCards(getFilteredRows());
			bindEvents();
		});

		$root.find(".action-detail").off("click").on("click", function() { openDetail($(this).data("c")); });
		$root.find(".action-correccion").off("click").on("click", function() {
			const candidato_name = $(this).data("c");
			const candidato_label = $(this).data("label") || candidato_name;
			ensureCorreccionDialogLoaded().then(() => {
				if (!window.hubgh || typeof window.hubgh.openCorreccionDatosDialog !== "function") {
					frappe.msgprint("No fue posible cargar el componente de corrección.");
					return;
				}
				window.hubgh.openCorreccionDatosDialog({
					candidato_name,
					candidato_label,
					on_success: () => loadBoard(),
				});
			});
		});
		$root.find(".action-upload-selection").off("click").on("click", function() {
			const candidate = $(this).data("c");
			// jQuery's .data() auto-casts numeric-looking data-c values (e.g. a
			// candidate name that equals its numero_documento) to a Number, so
			// String() both sides to keep this lookup working for numeric names.
			const row = (state.rows || []).find(r => String(r.name) === String(candidate)) || {};
			openSelectionDocsUploadDialog(candidate, row.missing || []);
		});
		$root.find(".action-primary").off("click").on("click", function() {
			const candidate = $(this).data("c");
			const action = $(this).data("action");
			if (action === "upload") {
				const row = (state.rows || []).find(r => String(r.name) === String(candidate)) || {};
				openSelectionDocsUploadDialog(candidate, row.missing || []);
				return;
			}
			$root.find(`.${action === "medical" ? "action-medical" : "action-send"}[data-c='${candidate}']`).first().trigger("click");
		});
		$root.find(".action-clear-filters").off("click").on("click", () => {
			state.search = "";
			state.status = "all";
			loadBoard();
		});
		$root.find(".action-go-medical").off("click").on("click", () => frappe.set_route("app", "sst_examenes_medicos"));

		$root.find(".action-medical").off("click").on("click", function() {
			const candidate = $(this).data("c");
			Promise.all([
				frappe.call("hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.get_agendamiento_autogestionado_enabled"),
				frappe.call("hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.get_candidate_cargo_info", { candidate }),
			]).then(([flag, infoResp]) => {
				const autoEnabled = !!(flag && flag.message);
				const info = (infoResp && infoResp.message) || {};
				const modoOptions = autoEnabled ? "Manual\nAutogestionado" : "Manual";
				const modoDescription = autoEnabled
					? "Manual: cambia el estado y queda en mano de SST. Autogestionado: dispara cita + email tokenizado al candidato."
					: "Solo manual disponible (autogestionado deshabilitado en este entorno).";
				// Default fecha límite: hoy + 7 días.
				const today = frappe.datetime.now_date();
				const defaultLimite = frappe.datetime.add_days(today, 7);

				// Descripción inicial del cargo: si hay precargado, mostrar nombre + tipo;
				// si no, pedir que el operador lo elija.
				const buildCargoDesc = (cargoNombre, tipoCargo) => {
					if (!cargoNombre && !tipoCargo) {
						return "Seleccioná el cargo del candidato. Determina los exámenes y las recomendaciones del correo.";
					}
					const tipoBadge = tipoCargo === "Administrativo"
						? "<span style='background:#e0e7ff;color:#3730a3;padding:2px 8px;border-radius:8px;font-size:11px;font-weight:600;'>Administrativo</span>"
						: "<span style='background:#fef3c7;color:#92400e;padding:2px 8px;border-radius:8px;font-size:11px;font-weight:600;'>Operativo</span>";
					return `<strong>${frappe.utils.escape_html(cargoNombre || "")}</strong> &nbsp; ${tipoBadge}`;
				};

				const d = new frappe.ui.Dialog({
					title: "Enviar a examen médico",
					fields: [
						{
							fieldname: "cargo",
							label: "Cargo del candidato",
							fieldtype: "Link",
							options: "Cargo",
							default: info.cargo || "",
							reqd: 1,
							description: buildCargoDesc(info.cargo_nombre, info.tipo_cargo),
							onchange() {
								const cargoVal = (d.get_value("cargo") || "").trim();
								if (!cargoVal) {
									d.fields_dict.cargo.set_description(buildCargoDesc("", ""));
									return;
								}
								frappe.call("hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.get_cargo_info", { cargo: cargoVal })
									.then(r => {
										const ci = (r && r.message) || {};
										d.fields_dict.cargo.set_description(buildCargoDesc(ci.nombre || cargoVal, ci.tipo_cargo || ""));
									});
							},
						},
						{
							fieldname: "modo",
							label: "Modo de agendamiento",
							fieldtype: "Select",
							options: modoOptions,
							default: "Manual",
							reqd: 1,
							description: modoDescription,
						},
						{
							fieldname: "fecha_limite",
							label: "Fecha límite para agendar",
							fieldtype: "Date",
							default: defaultLimite,
							depends_on: "eval:doc.modo=='Autogestionado'",
							description: "El candidato sólo verá slots hasta esta fecha (incluida). Útil para forzar que agende pronto.",
						},
					],
					primary_action_label: "Enviar",
					primary_action(values) {
						const modo = (values.modo || "Manual").toLowerCase();
						const cargoVal = (values.cargo || "").trim();
						if (!cargoVal) {
							frappe.msgprint("Tenés que elegir un cargo.");
							return;
						}
						const args = { candidate, modo, cargo: cargoVal };
						if (modo === "autogestionado" && values.fecha_limite) {
							args.fecha_limite = values.fecha_limite;
						}
						frappe.call("hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.send_to_medical_exam", args).then(() => {
							const msg = modo === "autogestionado"
								? "Candidato enviado a examen médico (autogestionado: link enviado)"
								: "Candidato enviado a examen médico (manual)";
							frappe.show_alert({ indicator: "blue", message: msg });
							d.hide();
							loadBoard();
						}).catch(err => {
							const msg = (err && (err.message || err.exc || err._server_messages)) || "No fue posible enviar a examen médico.";
							frappe.msgprint(msg);
						});
					},
				});
				d.show();
			});
		});

		$root.find(".action-reject").off("click").on("click", function() {
			const candidate = $(this).data("c");
			openSimpleDialog("Rechazar candidato", [{ fieldname: "motivo_rechazo", label: "Motivo (obligatorio)", fieldtype: "Small Text", reqd: 1 }], "Rechazar", values => {
				frappe.call("hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.reject_candidate", { candidate, motivo_rechazo: values.motivo_rechazo }).then(() => {
					frappe.show_alert({ indicator: "red", message: "Candidato rechazado" });
					loadBoard();
				});
			});
		});

		$root.find(".action-send").off("click").on("click", function() {
			const candidate = $(this).data("c");
			const row = (state.rows || []).find(r => r.name === candidate) || {};
			const isComplete = !!row.completo;
			const missing = row.missing || [];

			const baseFields = [
				{ fieldname: "pdv_destino", label: "Punto de Venta", fieldtype: "Link", options: "Punto de Venta", default: row.pdv_destino || "", reqd: 1 },
				{ fieldname: "fecha_tentativa_ingreso", label: "Fecha de Ingreso", fieldtype: "Date", default: row.fecha_tentativa_ingreso || "", reqd: 1 },
				{ fieldname: "cargo", label: "Cargo", fieldtype: "Link", options: "Cargo", default: row.cargo_postulado || "", reqd: 1 },
			];

			let dialogTitle = "Enviar a Relaciones Laborales";
			let fields = baseFields;

			if (!isComplete) {
				// Any incompleteness surfaces the motivo dialog; only the <ul> itself
				// is conditional on missing.length (is_complete=false + missing=[]
				// still needs to block on a motivo, just with nothing to list).
				const missingListHtml = missing.length > 0
					? `<ul style='margin:6px 0 0 16px;padding:0;'>${missing
						.map(m => `<li style='margin:2px 0;'>${frappe.utils.escape_html(m)}</li>`)
						.join("")}</ul>`
					: "";
				fields = [
					{
						fieldname: "incomplete_alert",
						fieldtype: "HTML",
						options: `<div class='sel-docs-note' style='border-color:#fbbf24;background:#fffbeb;color:#92400e;margin-bottom:8px;'>
							<strong>Documentación incompleta.</strong>${missing.length > 0 ? " Los siguientes documentos están pendientes:" : ""}
							${missingListHtml}
							<div style='margin-top:6px;'>Podés igualmente enviarlo indicando el motivo. El candidato quedará visible en ambas bandejas hasta completar los documentos.</div>
						</div>`,
					},
					...baseFields,
					{
						fieldname: "motivo",
						label: "Motivo del envío incompleto (obligatorio)",
						fieldtype: "Small Text",
						reqd: 1,
						description: "Justificación para enviar con documentación pendiente. Queda registrado en la trazabilidad del candidato.",
					},
				];
				dialogTitle = "Enviar a RRLL — documentación incompleta";
			}

			openSimpleDialog(dialogTitle, fields, "Enviar", values => {
				const callArgs = {
					candidate,
					pdv_destino: values.pdv_destino,
					fecha_tentativa_ingreso: values.fecha_tentativa_ingreso,
					cargo: values.cargo,
				};
				if (!isComplete) {
					callArgs.motivo = (values.motivo || "").trim();
				}
				frappe.call("hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.send_to_labor_relations", callArgs)
					.then(() => {
						const msg = isComplete
							? "Enviado a Relaciones Laborales"
							: "Enviado a RRLL con documentación incompleta. El candidato queda visible en ambas bandejas.";
						frappe.show_alert({ indicator: "green", message: msg });
						loadBoard();
					})
					.catch(err => {
						const msg = (err && (err.message || err.exc || err._server_messages)) || "No fue posible enviar a Relaciones Laborales.";
						frappe.msgprint(msg);
					});
			});
		});

		$root.find(".action-send-affiliation").off("click").on("click", function() {
			const candidate = $(this).data("c");
			const row = (state.rows || []).find(r => r.name === candidate) || {};
			openSimpleDialog("Enviar a Afiliación", [
				{ fieldname: "pdv_destino", label: "Punto de Venta", fieldtype: "Link", options: "Punto de Venta", default: row.pdv_destino || "", reqd: 1 },
				{ fieldname: "fecha_tentativa_ingreso", label: "Fecha de Ingreso", fieldtype: "Date", default: row.fecha_tentativa_ingreso || "", reqd: 1 },
				{ fieldname: "cargo", label: "Cargo", fieldtype: "Link", options: "Cargo", default: row.cargo_postulado || "", reqd: 1 },
			], "Enviar", values => {
				frappe.call("hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.send_to_affiliation", {
					candidate,
					pdv_destino: values.pdv_destino,
					fecha_tentativa_ingreso: values.fecha_tentativa_ingreso,
					cargo: values.cargo,
				}).then(() => {
					frappe.show_alert({ indicator: "green", message: "Enviado a Afiliación" });
					loadBoard();
				});
			});
		});
	};

	const loadBoard = () => {
		ensureUploadDocTypes();
		frappe.call("hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.list_candidates", { search: null }).then(r => {
			state.rows = r.message || [];
			const filteredRows = getFilteredRows();
			const summary = getSummary(state.rows);
			$root.html(`
				<div class='hubgh-board-hero'>
					<div class='hubgh-board-hero-head'>
						<div>
							<div class='hubgh-board-kickers'>
								<span class='hubgh-board-kicker'>Selección</span>
								<span class='hubgh-board-kicker'>Handoff a RRLL</span>
							</div>
							<h3 class='hubgh-board-title'>Control documental de candidatos</h3>
							<p class='hubgh-board-copy'>Compacta la revisión, deja visibles los bloqueos críticos y prioriza una sola acción primaria por candidato para no romper el flujo operativo.</p>
						</div>
						<div class='hubgh-board-meta'>
							<span class='hubgh-meta-pill'>${esc(summary.total)} candidatos activos</span>
							<span class='hubgh-meta-pill'>${esc(summary.rlReady)} listos para RRLL</span>
						</div>
					</div>
					<div class='sel-docs-summary'>
						<div class='sel-docs-summary-card'><span class='sel-docs-summary-label'>Total</span><span class='sel-docs-summary-value'>${esc(summary.total)}</span></div>
						<div class='sel-docs-summary-card'><span class='sel-docs-summary-label'>Pendientes</span><span class='sel-docs-summary-value'>${esc(summary.pending)}</span></div>
						<div class='sel-docs-summary-card'><span class='sel-docs-summary-label'>En examen</span><span class='sel-docs-summary-value'>${esc(summary.medical)}</span></div>
						<div class='sel-docs-summary-card'><span class='sel-docs-summary-label'>Listos RRLL</span><span class='sel-docs-summary-value'>${esc(summary.rlReady)}</span></div>
					</div>
					<div class='hubgh-board-shortcuts'>
						<button class='btn btn-sm btn-default go-medical-board'>Ir a exámenes médicos</button>
						<button class='btn btn-sm btn-default go-rejected-board'>Ver rechazados</button>
						<button class='btn btn-sm btn-default go-rrll-board'>Ir a contratación RRLL</button>
					</div>
				</div>
				<div class='hubgh-board-toolbar'>
					<input type='text' class='form-control filter-search' placeholder='Buscar por nombre, documento, cargo, PDV o estado' value='${esc(state.search || "")}' />
					<select class='form-control filter-status'>
						<option value='all' ${state.status === "all" ? "selected" : ""}>Todos</option>
						<option value='pending' ${state.status === "pending" ? "selected" : ""}>Con pendientes</option>
						<option value='complete' ${state.status === "complete" ? "selected" : ""}>Documentación completa</option>
						<option value='medical' ${state.status === "medical" ? "selected" : ""}>En examen médico</option>
						<option value='rl_ready' ${state.status === "rl_ready" ? "selected" : ""}>Listos para RL</option>
						<option value='in_process' ${state.status === "in_process" ? "selected" : ""}>Estado en proceso</option>
					</select>
					<div class='sel-docs-toolbar-actions'>
						<button class='btn btn-sm btn-default action-clear-filters'>Limpiar filtros</button>
					</div>
					<div class='hubgh-board-toolbar-copy'>${esc(filteredRows.length)} visibles de ${esc(state.rows.length)} registros</div>
				</div>
				<div class='sel-docs-subtitle'>Documentación y estados operativos de selección, con control de examen médico y envío a RL.</div>
				<div class='hubgh-cards-wrap'></div>
			`);

			renderCards(filteredRows);
			bindEvents();
			$root.find(".go-medical-board").off("click").on("click", () => frappe.set_route("app", "sst_examenes_medicos"));
			$root.find(".go-rejected-board").off("click").on("click", () => frappe.set_route("app", "candidatos_rechazados"));
			$root.find(".go-rrll-board").off("click").on("click", () => frappe.set_route("app", "bandeja_contratacion"));
		});
	};

	// ------------------------------------------------------------------
	// Tab "Enviados con pendientes" (PR3, 3.4.5): candidatos ya enviados a
	// afiliación/contratación cuyo avance permission-independent todavía no
	// está completo. Única acción: subir documentos (reutiliza el flujo de
	// subida ya autorizado; sin nuevo endpoint).
	// ------------------------------------------------------------------
	// ADR-6 — search/status filters own state (postHandoffSearch/postHandoffStatus),
	// deliberately not shared with the board's state.search/state.status.
	const getFilteredPostHandoffRows = () => {
		const q = (state.postHandoffSearch || "").trim().toLowerCase();
		return (state.postHandoffRows || []).filter(row => {
			if (q) {
				const blob = [row.full_name, row.name, row.numero_documento, row.pdv_destino_nombre, row.pdv_destino, row.cargo_postulado, row.estado_proceso].filter(Boolean).join(" ").toLowerCase();
				if (!blob.includes(q)) return false;
			}
			if (state.postHandoffStatus === "en_afiliacion" && row.estado_proceso !== "En afiliación") return false;
			if (state.postHandoffStatus === "listo_contratar" && row.estado_proceso !== "Listo para contratar") return false;
			if (state.postHandoffStatus === "contratado" && row.estado_proceso !== "Contratado") return false;
			return true;
		});
	};

	// Extracted from renderPostHandoffTable (ADR-6) so the search/filter handlers
	// repaint only the tbody, mirroring bindEvents:485-495's card-only repaint —
	// this preserves input focus and avoids rebuilding the toolbar on every keystroke.
	const renderPostHandoffRows = $tbody => {
		const rows = getFilteredPostHandoffRows();
		const htmlRows = rows.map(r => {
			const exemptedBadge = (r.exempted || []).length
				? `<div><span class='indicator-pill blue' title='${esc(r.exempted.join(", "))}'>Exonerado: ${esc(r.exempted.length)}</span></div>`
				: "";
			return `
			<tr>
				<td>${esc(r.full_name)}</td>
				<td>${esc(r.numero_documento)}</td>
				<td>${esc(r.pdv_destino_nombre)}</td>
				<td>${esc(r.estado_proceso)}</td>
				<td>${esc(r.avance_porcentaje)}%</td>
				<td style='font-size:12px;color:#6b7280'>${esc((r.missing || []).join(", "))}${exemptedBadge}</td>
				<td>
					<button class='btn btn-xs btn-primary action-post-handoff-upload' data-c='${esc(r.name)}'>Subir documentos</button>
					<button class='btn btn-xs btn-default action-post-handoff-exempt' data-c='${esc(r.name)}'>Exonerar</button>
				</td>
			</tr>
		`;
		}).join("");

		$tbody.html(htmlRows || "<tr><td colspan='7'>Sin candidatos para este filtro</td></tr>");

		const total = (state.postHandoffRows || []).length;
		$root.find(".post-handoff-counter").text(`${rows.length} visibles de ${total} (${rows.length}/${total})`);

		$tbody.find(".action-post-handoff-upload").off("click").on("click", function() {
			const candidate = $(this).data("c");
			const row = (state.postHandoffRows || []).find(r => String(r.name) === String(candidate)) || {};
			openSelectionDocsUploadDialog(candidate, row.missing || []);
		});
		$tbody.find(".action-post-handoff-exempt").off("click").on("click", function() {
			const candidate = $(this).data("c");
			const row = (state.postHandoffRows || []).find(r => String(r.name) === String(candidate)) || {};
			openExemptDocumentPickerDialog(candidate, row.missing || [], { onSuccess: () => loadPostHandoff() });
		});
	};

	const bindPostHandoffToolbar = () => {
		$root.find(".post-handoff-filter-search").off("input").on("input", function() {
			state.postHandoffSearch = $(this).val() || "";
			renderPostHandoffRows($root.find(".post-handoff-tbody"));
		});
		$root.find(".post-handoff-filter-status").off("change").on("change", function() {
			state.postHandoffStatus = $(this).val() || "all";
			renderPostHandoffRows($root.find(".post-handoff-tbody"));
		});
		$root.find(".post-handoff-clear-filters").off("click").on("click", () => {
			state.postHandoffSearch = "";
			state.postHandoffStatus = "all";
			renderPostHandoffTable(state.postHandoffRows);
		});
	};

	const renderPostHandoffTable = (rows) => {
		$root.html(`
			<div class='hubgh-board-hero'>
				<div class='hubgh-board-hero-head'>
					<div>
						<div class='hubgh-board-kickers'>
							<span class='hubgh-board-kicker'>Selección</span>
							<span class='hubgh-board-kicker'>Post-handoff</span>
						</div>
						<h3 class='hubgh-board-title'>Enviados con pendientes</h3>
						<p class='hubgh-board-copy'>Candidatos ya enviados (en afiliación, listos para contratar o contratados) cuya documentación todavía no está completa. Acciones disponibles: subir soportes o exonerar un documento requerido.</p>
					</div>
					<div class='hubgh-board-meta'><span class='hubgh-meta-pill'>${esc((rows || []).length)} pendientes</span></div>
				</div>
			</div>
			<div class='hubgh-board-toolbar'>
				<input type='text' class='form-control post-handoff-filter-search' placeholder='Buscar por nombre, documento, PDV, cargo o estado' value='${esc(state.postHandoffSearch || "")}' />
				<select class='form-control post-handoff-filter-status'>
					<option value='all' ${state.postHandoffStatus === "all" ? "selected" : ""}>Todos</option>
					<option value='en_afiliacion' ${state.postHandoffStatus === "en_afiliacion" ? "selected" : ""}>En afiliación</option>
					<option value='listo_contratar' ${state.postHandoffStatus === "listo_contratar" ? "selected" : ""}>Listo para contratar</option>
					<option value='contratado' ${state.postHandoffStatus === "contratado" ? "selected" : ""}>Contratado</option>
				</select>
				<div class='sel-docs-toolbar-actions'>
					<button class='btn btn-sm btn-default post-handoff-clear-filters'>Limpiar filtros</button>
				</div>
				<div class='hubgh-board-toolbar-copy post-handoff-counter'></div>
			</div>
			<div class='hubgh-table-shell' style='margin-top:12px'>
				<table class='table table-bordered hubgh-table'>
					<thead>
						<tr><th>Candidato</th><th>Documento</th><th>PDV</th><th>Estado</th><th>Avance</th><th>Faltantes</th><th></th></tr>
					</thead>
					<tbody class='post-handoff-tbody'></tbody>
				</table>
			</div>
		`);

		bindPostHandoffToolbar();
		renderPostHandoffRows($root.find(".post-handoff-tbody"));
	};

	const loadPostHandoff = () => {
		ensureUploadDocTypes();
		frappe.call("hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.list_post_handoff_candidates").then(r => {
			state.postHandoffRows = r.message || [];
			renderPostHandoffTable(state.postHandoffRows);
		});
	};

	$tabsWrap.find(".tab-board").on("click", () => {
		state.view = "board";
		setActiveTab("board");
		loadBoard();
	});
	$tabsWrap.find(".tab-post-handoff").on("click", () => {
		state.view = "post_handoff";
		setActiveTab("post_handoff");
		loadPostHandoff();
	});

	loadBoard();
};
