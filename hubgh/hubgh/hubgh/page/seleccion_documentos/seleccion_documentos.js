frappe.pages["seleccion_documentos"].on_page_load = function(wrapper) {
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

	const REQUIRED_SELECTION_DOCS = [
		"Carta Oferta",
		"SAGRILAFT",
		"Autorización de Descuento",
		"Autorización de Ingreso",
	];

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

	const $root = $("<div class='hubgh-board-shell'></div>").appendTo(page.body);
	let state = { rows: [], search: "", status: "all" };
	const esc = ui.esc;

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
	const canShowSendToRL = row => !!(row?.can_manage && (row?.concepto_medico || "") === "Favorable" && !isInMedicalExam(row));
	const getPrimaryAction = row => {
		if (canSendToRL(row)) {
			return { type: "send", label: "Enviar a RRLL", tone: "btn-primary", copy: "Handoff listo para formalización" };
		}
		if (row?.can_manage && !isInMedicalExam(row) && !hasResolvedMedicalConcept(row) && !canShowSendToRL(row)) {
			return { type: "medical", label: "Enviar a examen", tone: "btn-warning", copy: "Siguiente paso operativo" };
		}
		return { type: "upload", label: "Cargar soporte", tone: "btn-default", copy: "Completá lo pendiente sin salir" };
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
					loadBoard();
				});
		});
		picker.trigger("click");
	};

	const openSelectionDocsUploadDialog = (candidate, docTypes = []) => {
		const normalized = (docTypes || []).map(row => ({
			name: row?.name || "",
			label: row?.label || row?.name || "",
			required_for_hiring: Number(row?.required_for_hiring || 0),
		})).filter(row => row.name);
		const source = normalized.length
			? normalized
			: REQUIRED_SELECTION_DOCS.map(name => ({ name, label: name, required_for_hiring: 0 }));
		const options = source
			.map(row => row.name)
			.join("\n");
		openSimpleDialog("Subir documento de selección", [{ fieldname: "document_type", label: "Documento", fieldtype: "Select", options, reqd: 1 }], "Subir", values => {
			quickUpload(candidate, values.document_type);
		});
	};

	const openDetail = candidate => {
		frappe.call("hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.candidate_detail", { candidate })
			.then(r => {
				const data = r.message || {};
				const progress = data.progress || {};
				const uploadDocTypes = data.upload_doc_types || [];
				const completionTone = progress.is_complete ? "green" : "orange";
				const completionLabel = progress.is_complete ? "Documentación completa" : "Documentación incompleta";
				const candidateData = data.candidate || {};
				const statusByDoc = (data.selection_doc_status || []).reduce((acc, row) => {
					acc[row.document_type] = row;
					return acc;
				}, {});

				const requiredDocsHtml = REQUIRED_SELECTION_DOCS.map(docType => {
					const rowStatus = statusByDoc[docType] || { uploaded_ok: false, required: docType === "SAGRILAFT" ? 1 : 0 };
					const requiredTag = rowStatus.required ? "<span class='indicator-pill red'>Requerido</span>" : "<span class='indicator-pill blue'>Opcional</span>";
					return `
						<div class='sel-req-doc'>
							<div class='sel-req-doc-title'>${esc(docType)}</div>
							<div>${requiredTag} ${ui.yesNoBadge(!!rowStatus.uploaded_ok)}</div>
						</div>
					`;
				}).join("");

				const docsHtml = (data.documents || []).map(d => `
					<tr>
						<td>${esc(d.document_type || "")}</td>
						<td>${esc(d.status || "Pendiente")}</td>
						<td>${esc(d.uploaded_by || "")}</td>
						<td>${frappe.datetime.str_to_user(d.uploaded_on || "") || ""}</td>
						<td>${d.file ? `<a href='${d.file}' target='_blank'>Ver</a>` : ""}</td>
					</tr>
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
					</div>
					<div class='sel-docs-table-wrap'>
						<table class='table table-sm'>
							<thead><tr><th>Tipo</th><th>Estado</th><th>Subido por</th><th>Fecha</th><th>Archivo</th></tr></thead>
							<tbody>${docsHtml || "<tr><td colspan='5' class='text-muted'>Sin documentos</td></tr>"}</tbody>
						</table>
					</div>
				`);

				dialog.fields_dict.content.$wrapper.find(".btn-download-zip").on("click", () => {
					frappe.call("hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.download_candidate_documents_zip", { candidate }).then(resp => {
						if (resp.message) window.open(resp.message, "_blank");
					});
				});
				dialog.fields_dict.content.$wrapper.find(".btn-upload-selection-doc").on("click", () => openSelectionDocsUploadDialog(candidate, uploadDocTypes));
				dialog.show();
				cleanupModal(dialog);
			});
	};

	const getFilteredRows = () => {
		const q = (state.search || "").trim().toLowerCase();
		return (state.rows || []).filter(row => {
			if (q) {
				const blob = [row.full_name, row.name, row.numero_documento, row.pdv_destino, row.cargo_postulado, row.estado_proceso].filter(Boolean).join(" ").toLowerCase();
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
		const cards = (rows || []).map(row => {
			const porcentaje = Number(row.avance_porcentaje || 0);
			const progressTone = row.completo ? "green" : (porcentaje >= 100 ? "green" : (porcentaje >= 50 ? "blue" : "orange"));
			const inMedical = isInMedicalExam(row);
			const manageEnabled = !!row.can_manage;
			const primary = getPrimaryAction(row);

			return `
				<div class='hubgh-card' data-c='${esc(row.name)}'>
					<div class='hubgh-card-head'>
						<div class='hubgh-main'>
							<div class='hubgh-title-row'>
								<button type='button' class='btn btn-link btn-xs hubgh-name action-detail' data-c='${esc(row.name)}'>${esc(row.full_name || row.name)}</button>
								${processBadge(row.estado_proceso)}
								${conceptBadge(row.concepto_medico)}
							</div>
							<div class='hubgh-meta'>CC ${esc(row.numero_documento || "-")}</div>
							<div class='hubgh-submeta'>
								<span>${esc(row.cargo_postulado || "Sin cargo")}</span>
								<span class='hubgh-dot'>•</span>
								<span>${esc(row.pdv_destino || "Sin PDV")}</span>
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
		$root.find(".action-upload-selection").off("click").on("click", function() { openSelectionDocsUploadDialog($(this).data("c")); });
		$root.find(".action-primary").off("click").on("click", function() {
			const candidate = $(this).data("c");
			const action = $(this).data("action");
			if (action === "upload") {
				openSelectionDocsUploadDialog(candidate);
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
			frappe.call("hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.send_to_medical_exam", { candidate }).then(() => {
				frappe.show_alert({ indicator: "blue", message: "Candidato enviado a examen médico" });
				loadBoard();
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
			openSimpleDialog("Enviar a RL", [
				{ fieldname: "pdv_destino", label: "Punto de Venta", fieldtype: "Link", options: "Punto de Venta", reqd: 1 },
				{ fieldname: "fecha_tentativa_ingreso", label: "Fecha de Ingreso", fieldtype: "Date", reqd: 1 },
			], "Enviar", values => {
				frappe.call("hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.send_to_labor_relations", {
					candidate,
					pdv_destino: values.pdv_destino,
					fecha_tentativa_ingreso: values.fecha_tentativa_ingreso,
				}).then(() => {
					frappe.show_alert({ indicator: "green", message: "Enviado a Relaciones Laborales" });
					loadBoard();
				});
			});
		});
	};

	const loadBoard = () => {
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

	loadBoard();
};
