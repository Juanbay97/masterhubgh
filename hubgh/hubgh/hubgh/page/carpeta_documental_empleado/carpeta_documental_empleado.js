frappe.pages["carpeta_documental_empleado"].on_page_load = function(wrapper) {
	frappe.require("/assets/hubgh/css/carpeta_documental_empleado.css");
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
		title: "RRLL - Carpeta documental del empleado",
		single_column: true,
	});

	const state = {
		search: "",
		rows: [],
		selectedEmployee: null,
		detail: null,
		loadingList: false,
		loadingDetail: false,
	};

	const $root = $("<div class='hub-folder-page'></div>").appendTo(page.body);

	const initials = (name) => {
		const text = String(name || "").trim();
		if (!text) return "--";
		const parts = text.split(/\s+/).filter(Boolean);
		if (!parts.length) return "--";
		return (parts[0][0] + (parts[1] ? parts[1][0] : "")).toUpperCase();
	};

	const esc = (value) => frappe.utils.escape_html(String(value || ""));

	const badgeClass = (type) => {
		if (type === "negative") return "hub-badge hub-badge--negative";
		if (type === "positive") return "hub-badge hub-badge--positive";
		return "hub-badge hub-badge--neutral";
	};

	const renderList = () => {
		const cards = (state.rows || []).map((row) => {
			const missing = Number(row.missing_count || 0);
			const expired = Number(row.expired_count || 0);
			const uploaded = Number(row.uploaded_count || 0);
			const uploadedAny = Number(row.uploaded_any_count || 0);
			const total = Number(row.total_required || 0);
			const progress = Number(row.progress_percent || 0);
			const statusBadge = expired > 0
				? `<span class='${badgeClass("negative")}'><i class='fa fa-exclamation-circle'></i> ${expired} Vencido${expired > 1 ? "s" : ""}</span>`
				: (missing > 0
					? `<span class='${badgeClass("neutral")}'><i class='fa fa-folder-open-o'></i> ${missing} Faltante${missing > 1 ? "s" : ""}</span>`
					: `<span class='${badgeClass("positive")}'><i class='fa fa-check'></i> Al día</span>`);

			return `
				<button class='hub-card hub-employee-card btn-open-drawer' data-employee='${esc(row.employee)}'>
					<div class='hub-card__head'>
						<div class='hub-avatar'>${esc(initials(row.employee_name || row.employee))}</div>
						<div>
							<div class='hub-card__title'>${esc(row.employee_name || row.employee)}</div>
							<div class='hub-card__meta'>ID: ${esc(row.id_number || row.employee)} · PDV: ${esc(row.branch || "-")}</div>
						</div>
					</div>
					<div class='hub-progress'>
						<div class='hub-progress__bar' style='width:${Math.min(Math.max(progress, 0), 100)}%'></div>
					</div>
					<div class='hub-card__meta'>${uploaded}/${total} requeridos cargados (${progress}%) · ${uploadedAny} archivos totales</div>
					<div class='hub-card__badges'>
						${statusBadge}
						${uploadedAny > 0 ? `<span class='${badgeClass("positive")}'><i class='fa fa-paperclip'></i> ${uploadedAny} cargado${uploadedAny > 1 ? "s" : ""}</span>` : ""}
						${missing > 0 ? `<span class='${badgeClass("neutral")}'><i class='fa fa-minus-circle'></i> ${missing} Faltante${missing > 1 ? "s" : ""}</span>` : ""}
					</div>
				</button>
			`;
		}).join("");

		$root.find(".hub-grid").html(
			cards || "<div class='hub-empty'>No se encontraron empleados para el filtro aplicado.</div>"
		);
	};

	const renderDrawer = () => {
		const opened = Boolean(state.selectedEmployee);
		const $overlay = $root.find(".hub-drawer-overlay");
		$overlay.toggleClass("is-open", opened);

		if (!opened) {
			$overlay.find(".hub-drawer__body").html("");
			$overlay.find(".hub-drawer__title").text("Detalle empleado");
			$overlay.find(".hub-drawer__subtitle").text("");
			return;
		}

		const employeeInfo = state.detail?.employee || {};
		const summary = state.detail?.summary || {};
		$overlay.find(".hub-drawer__title").text(employeeInfo.employee_name || employeeInfo.name || state.selectedEmployee);
		$overlay.find(".hub-drawer__subtitle").text(`ID: ${employeeInfo.id_number || employeeInfo.name || "-"} · PDV: ${employeeInfo.branch || "-"}`);

		if (state.loadingDetail) {
			$overlay.find(".hub-drawer__body").html("<div class='hub-empty'>Cargando documentos...</div>");
			return;
		}

		const renderDocCard = (d) => {
			const statusType = d.is_expired ? "negative" : (d.is_missing ? "neutral" : "positive");
			const statusLabel = d.is_expired ? "Vencido" : (d.is_missing ? "Faltante" : "Vigente");
			const expiry = d.has_expiry ? (d.valid_until ? frappe.datetime.str_to_user(d.valid_until) : "Sin fecha") : "No aplica";
			const updated = d.uploaded_on ? frappe.datetime.str_to_user(d.uploaded_on) : "Sin carga";
			const isEditable = Boolean(Number(d.is_editable || 0));

			const downloadBtn = d.file
				? `<button class='hub-btn hub-btn--icon btn-doc-download' data-url='${esc(d.file)}' title='Descargar'><i class='fa fa-download'></i></button>`
				: "";

			const updateBtn = !isEditable
				? ""
				: d.file
					? `<button class='hub-btn hub-btn--icon btn-doc-upload' data-document='${esc(d.document_type)}' data-person-document='${esc(d.person_document || "")}' title='Actualizar'><i class='fa fa-refresh'></i></button>`
					: `<button class='hub-btn hub-btn--primary btn-doc-upload' data-document='${esc(d.document_type)}' data-person-document='${esc(d.person_document || "")}'>Subir</button>`;

			return `
				<div class='hub-doc-card ${d.is_expired ? "is-expired" : ""}'>
					<div class='hub-doc-card__left'>
						<div class='hub-doc-card__title'>${esc(d.document_label || d.document_type)}</div>
						<div class='hub-doc-card__meta'>Actualizado: ${esc(updated)}</div>
						<div class='hub-doc-card__meta'>Vencimiento: ${esc(expiry)}</div>
					</div>
					<div class='hub-doc-card__right'>
						<span class='${badgeClass(statusType)}'>${esc(statusLabel)}</span>
						<div class='hub-doc-card__actions'>
							${downloadBtn}
							${updateBtn}
						</div>
					</div>
				</div>
			`;
		};

		const requiredDocs = state.detail?.required_documents || state.detail?.documents?.filter(d => !d.is_extra) || [];
		const rrllDocs = state.detail?.selection_rrll_documents || [];
		const sstDocs = state.detail?.sst_documents || [];
		const contractDocs = state.detail?.contract_documents || [];
		const disciplinaryDocs = state.detail?.disciplinary_documents || [];
		const otherDocs = state.detail?.other_documents || state.detail?.documents?.filter(d => d.is_extra) || [];

		const requiredRows = requiredDocs.map(renderDocCard).join("");
		const rrllRows = rrllDocs.map(renderDocCard).join("");
		const sstRows = sstDocs.map(renderDocCard).join("");
		const contractRows = contractDocs.map(renderDocCard).join("");
		const disciplinaryRows = disciplinaryDocs.map(renderDocCard).join("");
		const otherRows = otherDocs.map(renderDocCard).join("");

		$overlay.find(".hub-drawer__body").html(`
			<div class='hub-drawer__summary'>
				<span class='${badgeClass("neutral")}'><i class='fa fa-file-text-o'></i> ${summary.total_required || 0} requeridos</span>
				<span class='${badgeClass("positive")}'><i class='fa fa-check'></i> ${summary.uploaded_count || 0} cargados</span>
				<span class='${badgeClass("neutral")}'><i class='fa fa-minus-circle'></i> ${summary.missing_count || 0} faltantes</span>
				<span class='${badgeClass("negative")}'><i class='fa fa-exclamation-circle'></i> ${summary.expired_count || 0} vencidos</span>
			</div>
			<div>
				<div class='hub-card__title' style='margin-bottom:8px'>Documentos requeridos (con espacios de carga)</div>
				${requiredRows || "<div class='hub-empty'>No hay documentos requeridos configurados.</div>"}
			</div>
			<div>
				<div class='hub-card__title' style='margin-bottom:8px'>Selección / RRLL</div>
				${rrllRows || "<div class='hub-empty'>Sin documentos de Selección/RRLL.</div>"}
			</div>
			<div>
				<div class='hub-card__title' style='margin-bottom:8px'>SST / Exámenes médicos</div>
				${sstRows || "<div class='hub-empty'>Sin documentos SST para este empleado.</div>"}
			</div>
			<div>
				<div class='hub-card__title' style='margin-bottom:8px'>Contractuales (Contrato / Otrosí)</div>
				${contractRows || "<div class='hub-empty'>Sin documentos contractuales para este empleado.</div>"}
			</div>
			<div>
				<div class='hub-card__title' style='margin-bottom:8px'>Disciplinarios</div>
				${disciplinaryRows || "<div class='hub-empty'>Sin documentos disciplinarios para este empleado.</div>"}
			</div>
			<div>
				<div class='hub-card__title' style='margin-bottom:8px'>Otros</div>
				${otherRows || "<div class='hub-empty'>Sin documentos adicionales en esta sección.</div>"}
			</div>
		`);
	};

	const loadList = () => {
		state.loadingList = true;
		$root.find(".hub-grid").html("<div class='hub-empty'>Cargando empleados...</div>");
		return new Promise((resolve) => {
			frappe.call({
				method: "hubgh.hubgh.page.carpeta_documental_empleado.carpeta_documental_empleado.get_employees_with_docs_status",
				args: { search: state.search || null },
				callback: (r) => {
					state.rows = r?.message?.rows || [];
					renderList();
					state.loadingList = false;
					resolve(r);
				},
				error: () => {
					state.loadingList = false;
					$root.find(".hub-grid").html("<div class='hub-empty'>No fue posible cargar empleados.</div>");
					resolve(null);
				},
			});
		});
	};

	const loadDetail = (employee) => {
		state.selectedEmployee = employee;
		state.loadingDetail = true;
		renderDrawer();
		return new Promise((resolve) => {
			frappe.call({
				method: "hubgh.hubgh.page.carpeta_documental_empleado.carpeta_documental_empleado.get_employee_documents",
				args: { employee },
				callback: (r) => {
					state.detail = r?.message || { employee: null, documents: [] };
					state.loadingDetail = false;
					renderDrawer();
					resolve(r);
				},
				error: () => {
					state.loadingDetail = false;
					state.detail = { employee: null, documents: [] };
					renderDrawer();
					resolve(null);
				},
			});
		});
	};

	const openUpload = ({ documentType, personDocument }) => {
		if (!state.selectedEmployee || !documentType) return;
		new frappe.ui.FileUploader({
			on_success(file) {
				const method = personDocument
					? "hubgh.hubgh.page.carpeta_documental_empleado.carpeta_documental_empleado.replace_document"
					: "hubgh.hubgh.page.carpeta_documental_empleado.carpeta_documental_empleado.upload_document";
				frappe.call({
					method,
					args: {
						person_document: personDocument || null,
						employee: state.selectedEmployee,
						document_type: documentType,
						file_url: file.file_url,
					},
					freeze: true,
					freeze_message: "Guardando documento...",
					callback: () => {
						frappe.show_alert({ indicator: "green", message: "Documento actualizado" });
						loadDetail(state.selectedEmployee);
						loadList();
					},
				});
			},
		});
	};

	const downloadZip = () => {
		if (!state.selectedEmployee) return;
		frappe.call({
			method: "hubgh.hubgh.page.carpeta_documental_empleado.carpeta_documental_empleado.download_employee_documents_zip",
			args: { employee: state.selectedEmployee },
			callback: (r) => {
				if (!r || !r.message) return;
				window.open(r.message, "_blank");
			},
		});
	};

	$root.html(frappe.render_template("carpeta_documental_empleado"));

	$root.on("click", ".btn-search", () => {
		state.search = ($root.find(".hub-search").val() || "").trim();
		loadList();
	});

	$root.on("keypress", ".hub-search", (e) => {
		if (e.key === "Enter") {
			state.search = ($root.find(".hub-search").val() || "").trim();
			loadList();
		}
	});

	$root.on("click", ".btn-open-drawer", function() {
		const employee = $(this).data("employee");
		loadDetail(employee);
	});

	$root.on("click", ".btn-close-drawer", () => {
		state.selectedEmployee = null;
		state.detail = null;
		renderDrawer();
	});

	$root.on("click", ".hub-drawer-overlay", function(e) {
		if (e.target !== this) return;
		state.selectedEmployee = null;
		state.detail = null;
		renderDrawer();
	});

	$(document).on("keydown.hub_folder_drawer", (e) => {
		if (e.key === "Escape" && state.selectedEmployee) {
			state.selectedEmployee = null;
			state.detail = null;
			renderDrawer();
		}
	});

	$root.on("click", ".btn-doc-download", function() {
		const url = $(this).data("url");
		if (url) window.open(url, "_blank");
	});

	$root.on("click", ".btn-doc-upload", function() {
		const documentType = $(this).data("document");
		const personDocument = $(this).data("person-document");
		openUpload({ documentType, personDocument });
	});

	$root.on("click", ".btn-download-zip", downloadZip);

	loadList();
};
