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
		employmentStatus: "active",
		rows: [],
		selectedEmployee: null,
		detail: null,
		uploadableTypes: null,
		loadingList: false,
		loadingDetail: false,
		upload: {
			open: false,
			documentType: "",
			personDocument: null,
			file: null,
			hasExpiry: 0,
			issueDate: "",
			validUntil: "",
			saving: false,
		},
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

	const employmentStatusLabels = { active: "Activos", retired: "Retirados", all: "Todos" };

	const resetUploadState = () => {
		state.upload = {
			open: false,
			documentType: "",
			personDocument: null,
			file: null,
			hasExpiry: 0,
			issueDate: "",
			validUntil: "",
			saving: false,
		};
	};

	const getUploadTypeMeta = (documentType) => {
		const items = Array.isArray(state.uploadableTypes) ? state.uploadableTypes : [];
		return items.find((item) => item.name === documentType) || items[0] || null;
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

	const renderBulkBatchPanel = () => `
		<div class='hub-card' style='margin-bottom:16px;'>
			<div class='hub-card__head' style='margin-bottom:12px;'>
				<div>
					<div class='hub-card__title'>Documental · subir documentos masivos</div>
					<div class='hub-card__meta'>Usá un ZIP con manifest CSV + archivos. También podés actualizar estados SST masivos desde acá.</div>
				</div>
			</div>
			<div class='hub-card__badges' style='margin-bottom:12px;'>
				<span class='${badgeClass("neutral")}'><i class='fa fa-folder-open-o'></i> Carpeta documental</span>
				<span class='${badgeClass("positive")}'><i class='fa fa-heartbeat'></i> SST masivo</span>
			</div>
			<div style='display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:12px;'>
				<div class='hub-doc-card'>
					<div class='hub-doc-card__title'>Documentos masivos</div>
					<div class='hub-doc-card__meta'>Descargá manifest + guía del ZIP y luego subí el paquete documental.</div>
					<div class='hub-doc-card__actions' style='margin-top:10px; gap:8px; flex-wrap:wrap;'>
						<a class='hub-btn' href='/assets/hubgh/templates/template_documentos_masivos_manifest.csv' download><i class='fa fa-download'></i> Manifest</a>
						<a class='hub-btn' href='/assets/hubgh/templates/template_documentos_masivos_instrucciones.csv' download><i class='fa fa-book'></i> Estructura ZIP</a>
						<button class='hub-btn hub-btn--primary btn-bulk-upload' data-doctype='Documentos Empleado'><i class='fa fa-upload'></i> Subir ZIP</button>
					</div>
				</div>
				<div class='hub-doc-card'>
					<div class='hub-doc-card__title'>Estados SST empleados</div>
					<div class='hub-doc-card__meta'>Plantilla para estado de novedad, estado destino, alertas y opciones de accidente/incapacidad.</div>
					<div class='hub-doc-card__actions' style='margin-top:10px; gap:8px; flex-wrap:wrap;'>
						<a class='hub-btn' href='/assets/hubgh/templates/template_estados_sst_empleados.csv' download><i class='fa fa-download'></i> Plantilla SST</a>
						<a class='hub-btn' href='/assets/hubgh/templates/template_estados_sst_opciones.csv' download><i class='fa fa-list'></i> Valores permitidos</a>
						<button class='hub-btn hub-btn--primary btn-bulk-upload' data-doctype='Estado SST Empleado'><i class='fa fa-upload'></i> Subir CSV</button>
					</div>
				</div>
			</div>
		</div>
	`;

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
		const $drawerShell = $root.find(".hub-drawer-shell");
		$drawerShell.toggleClass("is-open", opened);

		if (!opened) {
			resetUploadState();
			$drawerShell.find(".hub-drawer__body").html("");
			$drawerShell.find(".hub-drawer__title").text("Detalle empleado");
			$drawerShell.find(".hub-drawer__subtitle").text("");
			return;
		}

		const employeeInfo = state.detail?.employee || {};
		const summary = state.detail?.summary || {};
		const canUpload = Boolean(Number(state.detail?.permissions?.can_upload || 0));
		$drawerShell.find(".hub-drawer__title").text(employeeInfo.employee_name || employeeInfo.name || state.selectedEmployee);
		const archiveLabel = employeeInfo.employment_status === "Retirado" ? " · Archivo retirado" : "";
		$drawerShell.find(".hub-drawer__subtitle").text(`ID: ${employeeInfo.id_number || employeeInfo.name || "-"} · PDV: ${employeeInfo.branch || "-"}${archiveLabel}`);
		$drawerShell.find(".btn-add-categorized-upload").toggle(canUpload);

		if (state.loadingDetail) {
			$drawerShell.find(".hub-drawer__body").html("<div class='hub-empty'>Cargando documentos...</div>");
			return;
		}

		const uploadItems = Array.isArray(state.uploadableTypes) ? state.uploadableTypes : [];
		const uploadOptions = uploadItems.map((item) => {
			const selected = item.name === state.upload.documentType ? "selected" : "";
			return `<option value='${esc(item.name)}' ${selected}>${esc(item.label || item.name)}</option>`;
		}).join("");
		const uploadMeta = getUploadTypeMeta(state.upload.documentType);
		const uploadPanel = canUpload && state.upload.open ? `
			<div class='hub-upload-panel'>
				<div class='hub-upload-panel__head'>
					<div>
						<div class='hub-upload-panel__title'>${state.upload.personDocument ? "Actualizar documento" : "Agregar documento a la carpeta"}</div>
						<div class='hub-upload-panel__meta'>Cargá cualquier documento editable del empleado sin salir del panel lateral.</div>
					</div>
					<button class='hub-btn hub-btn--icon btn-close-upload-panel' title='Cerrar formulario'><i class='fa fa-times'></i></button>
				</div>
				<div class='hub-upload-grid'>
					<div class='hub-field'>
						<label>Categoría documental</label>
						<select class='hub-upload-select'>${uploadOptions}</select>
					</div>
					<div class='hub-field'>
						<label>Archivo</label>
						<input type='file' class='hub-upload-file' />
					</div>
					<div class='hub-field'>
						<label>Fecha de expedición</label>
						<input type='date' class='hub-upload-issue-date' value='${esc(state.upload.issueDate || "")}' />
					</div>
					${uploadMeta?.has_expiry ? `
						<div class='hub-field'>
							<label>Fecha de vencimiento</label>
							<input type='date' class='hub-upload-valid-until' value='${esc(state.upload.validUntil || "")}' />
						</div>
					` : ""}
				</div>
				<div class='hub-upload-help'>${uploadMeta?.requires_for_employee_folder ? "Documento requerido dentro de la carpeta del empleado." : "Documento adicional permitido para la carpeta del empleado."}</div>
				<div class='hub-upload-panel__actions'>
					<button class='hub-btn btn-close-upload-panel'>Cancelar</button>
					<button class='hub-btn hub-btn--primary btn-submit-upload-panel' ${state.upload.saving ? "disabled" : ""}>${state.upload.saving ? "Guardando..." : (state.upload.personDocument ? "Actualizar" : "Guardar documento")}</button>
				</div>
			</div>
		` : "";

		const renderDocCard = (d) => {
			const statusType = d.is_expired ? "negative" : (d.is_missing ? "neutral" : "positive");
			const statusLabel = d.is_expired ? "Vencido" : (d.is_missing ? "Faltante" : "Vigente");
			const expiry = d.has_expiry ? (d.valid_until ? frappe.datetime.str_to_user(d.valid_until) : "Sin fecha") : "No aplica";
			const updated = d.uploaded_on ? frappe.datetime.str_to_user(d.uploaded_on) : "Sin carga";
			const isEditable = Boolean(Number(d.is_editable || 0));

			const downloadBtn = d.file
				? `<button class='hub-btn hub-btn--icon btn-doc-download' data-url='${esc(d.file)}' title='Descargar'><i class='fa fa-download'></i></button>`
				: "";

			const replaceToken = Boolean(Number(d.can_replace || 0)) ? esc(d.person_document || "") : "";
			const updateBtn = !isEditable || !canUpload
				? ""
				: d.file
					? `<button class='hub-btn hub-btn--icon btn-doc-upload' data-document='${esc(d.document_type)}' data-person-document='${replaceToken}' title='Actualizar'><i class='fa fa-refresh'></i></button>`
					: `<button class='hub-btn hub-btn--primary btn-doc-upload' data-document='${esc(d.document_type)}' data-person-document='${replaceToken}'>Subir</button>`;

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

		$drawerShell.find(".hub-drawer__body").html(`
			${uploadPanel}
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

	const getUploadableDocumentTypes = () => {
		if (!state.selectedEmployee) return Promise.resolve([]);
		if (Array.isArray(state.uploadableTypes)) return Promise.resolve(state.uploadableTypes);
		return new Promise((resolve) => {
			frappe.call({
				method: "hubgh.hubgh.page.carpeta_documental_empleado.carpeta_documental_empleado.get_uploadable_document_types",
				args: { employee: state.selectedEmployee },
				callback: (r) => {
					state.uploadableTypes = r?.message?.items || [];
					resolve(state.uploadableTypes);
				},
				error: () => {
					state.uploadableTypes = [];
					resolve([]);
				},
			});
		});
	};

	const loadList = () => {
		state.loadingList = true;
		$root.find(".hub-grid").html("<div class='hub-empty'>Cargando empleados...</div>");
		return new Promise((resolve) => {
			frappe.call({
				method: "hubgh.hubgh.page.carpeta_documental_empleado.carpeta_documental_empleado.get_employees_with_docs_status",
				args: { search: state.search || null, employment_status: state.employmentStatus || "active" },
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
		state.uploadableTypes = null;
		resetUploadState();
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

	const openUploadPanel = ({ documentType = "", personDocument = null } = {}) => {
		if (!state.selectedEmployee) return;
		getUploadableDocumentTypes().then((items) => {
			if (!items.length) {
				frappe.msgprint({
					title: "Carpeta documental",
					indicator: "orange",
					message: "No hay categorías habilitadas para carga manual en esta carpeta.",
				});
				return;
			}
			const selected = items.find((item) => item.name === documentType) || items[0];
			state.upload.open = true;
			state.upload.documentType = selected.name;
			state.upload.personDocument = personDocument || null;
			state.upload.file = null;
			state.upload.issueDate = "";
			state.upload.validUntil = "";
			state.upload.hasExpiry = Number(selected.has_expiry || 0);
			renderDrawer();
		});
	};

	const closeUploadPanel = () => {
		resetUploadState();
		renderDrawer();
	};

	const submitUploadPanel = () => {
		if (!state.selectedEmployee || !state.upload.documentType || !state.upload.file || state.upload.saving) return;
		state.upload.saving = true;
		renderDrawer();
		uploadToFileAPI("Ficha Empleado", state.selectedEmployee, state.upload.file)
			.then((fileUrl) => new Promise((resolve, reject) => {
				const method = state.upload.personDocument
					? "hubgh.hubgh.page.carpeta_documental_empleado.carpeta_documental_empleado.replace_document"
					: "hubgh.hubgh.page.carpeta_documental_empleado.carpeta_documental_empleado.upload_document";
				frappe.call({
					method,
					args: {
						person_document: state.upload.personDocument || null,
						employee: state.selectedEmployee,
						document_type: state.upload.documentType,
						file_url: fileUrl,
						issue_date: state.upload.issueDate || null,
						valid_until: state.upload.validUntil || null,
					},
					freeze: true,
					freeze_message: "Guardando documento...",
					callback: (response) => resolve(response),
					error: (error) => reject(error),
				});
			}))
			.then(() => {
				frappe.show_alert({ indicator: "green", message: state.upload.personDocument ? "Documento actualizado" : "Documento cargado" });
				closeUploadPanel();
				loadDetail(state.selectedEmployee);
				loadList();
			})
			.catch(() => {
				state.upload.saving = false;
				renderDrawer();
				frappe.msgprint({
					title: "Carpeta documental",
					indicator: "red",
					message: "No fue posible cargar el documento. Probá nuevamente.",
				});
			});
	};

	const openBulkUpload = (doctype) => {
		if (!doctype) return;
		new frappe.ui.FileUploader({
			on_success(file) {
				frappe.call({
					method: "hubgh.hubgh.page.centro_de_datos.centro_de_datos.start_upload_data",
					args: {
						doctype,
						file_url: file.file_url,
						chunk_size: 25,
					},
					freeze: true,
					freeze_message: doctype === "Documentos Empleado" ? "Encolando ZIP documental..." : "Encolando actualización SST...",
					callback: (r) => {
						const status = r?.message || {};
						frappe.show_alert({ indicator: "blue", message: `${doctype} encolado` });
						if (!status.import_id) return;
						const poll = () => {
							frappe.call({
								method: "hubgh.hubgh.page.centro_de_datos.centro_de_datos.get_upload_status",
								args: { import_id: status.import_id },
								callback: (response) => {
									const payload = response?.message || {};
									if (payload.status === "completed" || payload.status === "failed") {
										frappe.msgprint({
											title: doctype,
											indicator: payload.status === "completed" ? (payload.counts?.errors ? "orange" : "green") : "red",
											message: `Procesadas ${payload.processed_rows || 0}/${payload.total_rows || 0}. Creados: ${payload.counts?.created || 0}. Actualizados: ${payload.counts?.updated || 0}. Errores: ${payload.counts?.errors || 0}.`,
										});
										loadList();
										if (state.selectedEmployee) loadDetail(state.selectedEmployee);
										return;
									}
									setTimeout(poll, 2500);
								},
							});
						};
						poll();
					},
				});
			},
		});
	};

	const openCategorizedUpload = () => {
		openUploadPanel();
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

	const maybeOpenDrawerFromRoute = () => {
		const options = frappe.route_options || {};
		const requestedEmployee = options.employee || options.persona;
		const shouldOpenDrawer = options.open_drawer === undefined ? Boolean(requestedEmployee) : Boolean(Number(options.open_drawer || 0));
		if (!requestedEmployee) {
			return Promise.resolve(false);
		}

		state.search = requestedEmployee;
		state.employmentStatus = options.employment_status || "all";
		$root.find(".hub-search").val(requestedEmployee);
		$root.find(".hub-status-filter").val(state.employmentStatus);
		frappe.route_options = null;

		return loadList().then(() => {
			if (!shouldOpenDrawer) {
				return true;
			}
			return loadDetail(requestedEmployee).then(() => true);
		});
	};

	$root.html(frappe.render_template("carpeta_documental_empleado"));
	$root.find(".hub-shell").prepend(renderBulkBatchPanel());

	$root.on("click", ".btn-search", () => {
		state.search = ($root.find(".hub-search").val() || "").trim();
		state.employmentStatus = $root.find(".hub-status-filter").val() || "active";
		loadList();
	});

	$root.on("change", ".hub-status-filter", () => {
		state.employmentStatus = $root.find(".hub-status-filter").val() || "active";
		loadList();
	});

	$root.on("keypress", ".hub-search", (e) => {
		if (e.key === "Enter") {
			state.search = ($root.find(".hub-search").val() || "").trim();
			state.employmentStatus = $root.find(".hub-status-filter").val() || "active";
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

	$root.on("click", ".hub-drawer-shell", function(e) {
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
		openUploadPanel({ documentType, personDocument });
	});

	$root.on("click", ".btn-add-categorized-upload", openCategorizedUpload);
	$root.on("click", ".btn-close-upload-panel", closeUploadPanel);
	$root.on("change", ".hub-upload-select", function() {
		const documentType = $(this).val() || "";
		const selected = getUploadTypeMeta(documentType);
		state.upload.documentType = documentType;
		state.upload.hasExpiry = Number(selected?.has_expiry || 0);
		if (!state.upload.hasExpiry) {
			state.upload.validUntil = "";
		}
		renderDrawer();
	});
	$root.on("change", ".hub-upload-file", function() {
		state.upload.file = this.files && this.files[0] ? this.files[0] : null;
	});
	$root.on("change", ".hub-upload-issue-date", function() {
		state.upload.issueDate = $(this).val() || "";
	});
	$root.on("change", ".hub-upload-valid-until", function() {
		state.upload.validUntil = $(this).val() || "";
	});
	$root.on("click", ".btn-submit-upload-panel", submitUploadPanel);
	$root.on("click", ".btn-download-zip", downloadZip);
	$root.on("click", ".btn-bulk-upload", function() {
		openBulkUpload($(this).data("doctype"));
	});

	$(wrapper).bind("show", function() {
		maybeOpenDrawerFromRoute();
	});

	maybeOpenDrawerFromRoute().then((openedFromRoute) => {
		if (!openedFromRoute) {
			loadList();
		}
	});
};
