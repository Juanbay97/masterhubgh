frappe.pages["sst_examenes_medicos"].on_page_load = function(wrapper) {
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
		title: "SST - Exámenes médicos",
		single_column: true,
	});
	injectSstExamScrollStyles();
	const ui = window.hubghBandejasUI || { injectBaseStyles() {}, injectScopedStyles() {} };
	ui.injectBaseStyles();
	ui.injectScopedStyles("sst-examenes-medicos", `
		.sst-exams-toolbar-actions { display: flex; gap: 8px; flex-wrap: wrap; margin-left: auto; }
		.sst-exams-card-copy { color: #475569; font-size: 12px; font-weight: 600; }
		.sst-exams-secondary-actions { display: flex; gap: 6px; flex-wrap: wrap; justify-content: flex-end; width: 100%; }
		.sst-exams-secondary-actions .btn-link { padding: 0 2px; }
		.sst-exams-empty-actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 12px; }
		@media (max-width: 768px) {
			.sst-exams-toolbar-actions { margin-left: 0; width: 100%; }
		}
	`);

	const $root = $("<div class='hubgh-board-shell'></div>").appendTo(page.body);
	const esc = value => frappe.utils.escape_html(value == null ? "" : String(value));
	let state = { rows: [], historyRows: [], search: "", historySearch: "", status: "all" };

	const conceptBadge = concept => {
		const c = (concept || "Pendiente").toLowerCase();
		if (c === "favorable") return "<span class='indicator-pill green'>Favorable</span>";
		if (c === "desfavorable") return "<span class='indicator-pill red'>Desfavorable</span>";
		if (c === "aplazado") return "<span class='indicator-pill orange'>Aplazado</span>";
		return `<span class='indicator-pill gray'>${esc(concept || "Pendiente")}</span>`;
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

	const quickUploadExam = candidate => {
		const picker = $("<input type='file' class='d-none' />");
		picker.on("change", function() {
			const file = this.files[0];
			if (!file) return;
			uploadToFileAPI("Candidato", candidate, file)
				.then(fileUrl => frappe.call("hubgh.hubgh.page.sst_examenes_medicos.sst_examenes_medicos.upload_medical_exam_document", {
					candidate,
					file_url: fileUrl,
				}))
				.then(() => {
					frappe.show_alert({ indicator: "green", message: "Examen médico cargado" });
					load();
				});
		});
		picker.trigger("click");
	};

	const setConcept = candidate => {
		const dialog = new frappe.ui.Dialog({
			title: "Definir concepto médico",
			fields: [
				{ fieldname: "concepto_medico", label: "Concepto", fieldtype: "Select", options: "Favorable\nDesfavorable\nAplazado", reqd: 1 },
				{ fieldname: "notes", label: "Observación", fieldtype: "Small Text" },
			],
		});
		dialog.set_primary_action("Guardar", () => {
			const values = dialog.get_values() || {};
			frappe.call("hubgh.hubgh.page.sst_examenes_medicos.sst_examenes_medicos.set_medical_concept", {
				candidate,
				concepto_medico: values.concepto_medico,
				notes: values.notes,
			}).then(() => {
				frappe.show_alert({ indicator: "green", message: "Concepto médico actualizado" });
				dialog.hide();
				load();
			});
		});
		dialog.show();
	};

	const getFilteredRows = () => {
		const q = (state.search || "").trim().toLowerCase();
		return (state.rows || []).filter(row => {
			if (state.status === "upload_pending" && row.has_exam_document) return false;
			if (state.status === "ready_concept" && !row.has_exam_document) return false;
			if (!q) return true;
			const blob = [row.full_name, row.numero_documento, row.pdv_destino_nombre, row.pdv_destino, row.cargo_postulado, row.concepto_medico].filter(Boolean).join(" ").toLowerCase();
			return blob.includes(q);
		});
	};

	const getPrimaryAction = row => row.has_exam_document
		? { type: "concept", label: "Definir concepto", copy: "Ya está el soporte; cerrá el concepto" }
		: { type: "upload", label: "Subir examen", copy: "Primero cargá el soporte clínico" };

	const getFilteredHistoryRows = () => {
		const q = (state.historySearch || "").trim().toLowerCase();
		return (state.historyRows || []).filter(row => {
			if (!q) return true;
			const blob = [
				row.full_name,
				row.numero_documento,
				row.pdv_destino_nombre,
				row.pdv_destino,
				row.cargo_postulado,
				row.concepto_medico,
				row.estado_proceso,
			].filter(Boolean).join(" ").toLowerCase();
			return blob.includes(q);
		});
	};

	const renderCards = rows => {
		const cards = (rows || []).map(row => {
			const primary = getPrimaryAction(row);
			const pdvLabel = row.pdv_destino_nombre || row.pdv_destino || "";
			return `
			<div class='hubgh-card'>
				<div class='hubgh-card-head'>
					<div class='hubgh-main'>
						<div class='hubgh-title-row'>
							<div class='hubgh-name'>${esc(row.full_name || row.name)}</div>
							${conceptBadge(row.concepto_medico)}
						</div>
						<div class='hubgh-meta'>CC ${esc(row.numero_documento || "-")}</div>
						<div class='hubgh-submeta'>
							<span>${esc(row.cargo_postulado || "Sin cargo")}</span>
							<span class='hubgh-dot'>•</span>
							<span title='${esc(row.pdv_destino || "")}'>${esc(pdvLabel || "Sin PDV")}</span>
							<span class='hubgh-dot'>•</span>
							<span>Enviado: ${esc(frappe.datetime.str_to_user(row.fecha_envio_examen_medico || "") || "-")}</span>
						</div>
					</div>
				</div>
				<div class='hubgh-badges-grid'>
					<div class='hubgh-badge ${row.has_exam_document ? "is-complete" : "is-pending"}'>
						<span class='hubgh-badge-label'>Documento examen</span>
						${row.has_exam_document ? "<span class='indicator-pill green'>Cargado</span>" : "<span class='indicator-pill orange'>Pendiente</span>"}
					</div>
					<div class='hubgh-badge ${Number(row.dias_pendientes || 0) >= 3 ? "is-pending" : "is-complete"}'>
						<span class='hubgh-badge-label'>Espera</span>
						<span>${esc(row.dias_pendientes || 0)} día(s)</span>
					</div>
				</div>
				<div class='hubgh-actions'>
					<div class='sst-exams-card-copy'>${esc(primary.copy)}</div>
					<button class='btn btn-xs btn-primary action-primary' data-c='${esc(row.name)}' data-action='${esc(primary.type)}'>${esc(primary.label)}</button>
					<div class='sst-exams-secondary-actions'>
						${primary.type === "upload" ? "" : `<button class='btn btn-xs btn-link action-upload-exam' data-c='${esc(row.name)}'>Subir examen</button>`}
						${primary.type === "concept" ? "" : `<button class='btn btn-xs btn-link action-set-concept' data-c='${esc(row.name)}'>Definir concepto</button>`}
					</div>
				</div>
			</div>
		`;
		}).join("");

		$root.find(".hubgh-cards-wrap").html(cards || `
			<div class='hubgh-empty'>
				<span class='hubgh-empty-title'>No hay pendientes en esta cola</span>
				<p class='hubgh-empty-copy'>Cuando Selección envía candidatos a examen, acá priorizás primero el cargue y después el concepto.</p>
				<div class='sst-exams-empty-actions'>
					<button class='btn btn-sm btn-default action-clear-pending-filters'>Limpiar filtros</button>
					<button class='btn btn-sm btn-primary action-go-selection'>Volver a selección</button>
				</div>
			</div>
		`);
	};

	const renderHistoryCards = rows => {
		const cards = (rows || []).map(row => {
			const pdvLabel = row.pdv_destino_nombre || row.pdv_destino || "";
			return `
			<div class='hubgh-card'>
				<div class='hubgh-card-head'>
					<div class='hubgh-main'>
						<div class='hubgh-title-row'>
							<div class='hubgh-name'>${esc(row.full_name || row.name)}</div>
							${conceptBadge(row.concepto_medico)}
						</div>
						<div class='hubgh-meta'>CC ${esc(row.numero_documento || "-")}</div>
						<div class='hubgh-submeta'>
							<span>${esc(row.cargo_postulado || "Sin cargo")}</span>
							<span class='hubgh-dot'>•</span>
							<span title='${esc(row.pdv_destino || "")}'>${esc(pdvLabel || "Sin PDV")}</span>
							<span class='hubgh-dot'>•</span>
							<span>Estado: ${esc(row.estado_proceso || "-")}</span>
						</div>
					</div>
				</div>
				<div class='hubgh-badges-grid'>
					<div class='hubgh-badge ${row.has_exam_document ? "is-complete" : "is-pending"}'>
						<span class='hubgh-badge-label'>Documento examen</span>
						${row.has_exam_document ? "<span class='indicator-pill green'>Cargado</span>" : "<span class='indicator-pill orange'>Pendiente</span>"}
					</div>
				</div>
			</div>
		`;
		}).join("");

		$root.find(".hubgh-history-wrap").html(cards || `
			<div class='hubgh-empty'>
				<span class='hubgh-empty-title'>Sin histórico con concepto</span>
				<p class='hubgh-empty-copy'>Cuando se cierre la evaluación médica, el histórico queda disponible para trazabilidad clínica-operativa.</p>
				<div class='sst-exams-empty-actions'>
					<button class='btn btn-sm btn-default action-clear-history-filters'>Limpiar búsqueda</button>
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

		$root.find(".history-filter-search").off("input").on("input", function() {
			state.historySearch = $(this).val() || "";
			renderHistoryCards(getFilteredHistoryRows());
			bindEvents();
		});

		$root.find(".action-primary").off("click").on("click", function() {
			const candidate = $(this).data("c");
			const action = $(this).data("action");
			if (action === "upload") {
				quickUploadExam(candidate);
				return;
			}
			setConcept(candidate);
		});

		$root.find(".action-upload-exam").off("click").on("click", function() {
			quickUploadExam($(this).data("c"));
		});

		$root.find(".action-set-concept").off("click").on("click", function() {
			setConcept($(this).data("c"));
		});

		$root.find(".action-clear-pending-filters").off("click").on("click", () => {
			state.search = "";
			state.status = "all";
			load();
		});

		$root.find(".action-clear-history-filters").off("click").on("click", () => {
			state.historySearch = "";
			load();
		});

		$root.find(".action-go-selection").off("click").on("click", () => frappe.set_route("app", "seleccion_documentos"));
	};

	const load = () => {
		Promise.all([
			frappe.call("hubgh.hubgh.page.sst_examenes_medicos.sst_examenes_medicos.list_medical_exam_candidates"),
			frappe.call("hubgh.hubgh.page.sst_examenes_medicos.sst_examenes_medicos.list_medical_exam_history"),
		]).then(([pendingRes, historyRes]) => {
			state.rows = pendingRes?.message || [];
			state.historyRows = historyRes?.message || [];
			$root.find(".pending-count").text(`Pendientes: ${state.rows.length}`);
			$root.find(".history-count").text(`Histórico: ${state.historyRows.length}`);
			renderCards(getFilteredRows());
			renderHistoryCards(getFilteredHistoryRows());
			bindEvents();
		});
	};

	$root.html(`
		<div class='hubgh-board-hero'>
			<div class='hubgh-board-hero-head'>
				<div>
					<div class='hubgh-board-kickers'><span class='hubgh-board-kicker'>SST</span><span class='hubgh-board-kicker'>Selección</span></div>
					<h3 class='hubgh-board-title'>Conceptos médicos y soportes</h3>
					<p class='hubgh-board-copy'>La cola pendiente prioriza una sola acción primaria: cargar examen y definir concepto. El histórico conserva trazabilidad sin meter ruido.</p>
				</div>
				<div class='hubgh-board-meta'>
					<span class='hubgh-meta-pill pending-count'>Pendientes: 0</span>
					<span class='hubgh-meta-pill history-count'>Histórico: 0</span>
				</div>
			</div>
			<div class='hubgh-board-shortcuts'>
				<button class='btn btn-sm btn-default go-selection-board'>Volver a selección</button>
				<button class='btn btn-sm btn-default go-rejected-board'>Ver rechazados</button>
				<button class='btn btn-sm btn-default go-sst-board'>Centro SST</button>
			</div>
		</div>
		<div class='hubgh-board-toolbar'>
			<input type='text' class='form-control filter-search' placeholder='Buscar por nombre, documento, cargo, PDV o concepto' />
			<select class='form-control filter-status'>
				<option value='all'>Todos</option>
				<option value='upload_pending'>Falta soporte</option>
				<option value='ready_concept'>Listos para concepto</option>
			</select>
			<div class='sst-exams-toolbar-actions'>
				<button class='btn btn-sm btn-default action-clear-pending-filters'>Limpiar filtros</button>
			</div>
			<div class='hubgh-board-toolbar-copy'>Pendientes visibles</div>
		</div>
		<div class='sel-docs-subtitle'>Candidatos en estado "En Examen Médico" para cargue de examen y definición de concepto.</div>
		<div class='hubgh-cards-wrap hubgh-scroll-wrap'></div>
		<hr style='margin:16px 0;'>
		<div class='hubgh-board-toolbar'>
			<input type='text' class='form-control history-filter-search' placeholder='Buscar historial por nombre, documento, cargo, PDV, estado o concepto' />
			<div class='hubgh-board-toolbar-copy'>Histórico visible</div>
		</div>
		<div class='sel-docs-subtitle'>Exámenes realizados con concepto médico definido (histórico).</div>
		<div class='hubgh-history-wrap hubgh-scroll-wrap'></div>
	`);

	$root.find(".go-selection-board").on("click", () => frappe.set_route("app", "seleccion_documentos"));
	$root.find(".go-rejected-board").on("click", () => frappe.set_route("app", "candidatos_rechazados"));
	$root.find(".go-sst-board").on("click", () => frappe.set_route("app", "sst_bandeja"));

	load();
};

function injectSstExamScrollStyles() {
	if (document.getElementById("sst-examenes-scroll-styles")) return;
	const style = document.createElement("style");
	style.id = "sst-examenes-scroll-styles";
	style.innerHTML = `
		.hubgh-scroll-wrap {
			max-height: 760px;
			overflow-y: auto;
			overflow-x: hidden;
			padding-right: 6px;
		}
		@media (max-width: 768px) {
			.hubgh-scroll-wrap { max-height: none; }
		}
	`;
	document.head.appendChild(style);
}
