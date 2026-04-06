frappe.pages["bandeja_afiliaciones"].on_page_load = function(wrapper) {
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
		title: "RRLL - Gestión de afiliaciones",
		single_column: true,
	});

	(window.hubghBandejasUI || { injectBaseStyles() {} }).injectBaseStyles();
	const $root = $("<div></div>").appendTo(page.body);
	const TYPE_META = {
		arl: { label: "ARL", field: "arl_afiliado" },
		eps: { label: "EPS", field: "eps_afiliado" },
		afp: { label: "AFP", field: "afp_afiliado" },
		cesantias: { label: "Cesantías", field: "cesantias_afiliado" },
		caja: { label: "Caja", field: "caja_afiliado" },
	};
	const SIESA_META_BY_TYPE = {
		eps: { fieldname: "eps_siesa", label: "EPS (SIESA)", doctype: "Entidad EPS Siesa" },
		afp: { fieldname: "afp_siesa", label: "AFP (SIESA)", doctype: "Entidad AFP Siesa" },
		cesantias: { fieldname: "cesantias_siesa", label: "Cesantías (SIESA)", doctype: "Entidad Cesantias Siesa" },
	};
	const TYPE_ORDER = ["arl", "eps", "afp", "cesantias", "caja"];
	let state = { rows: [], search: "", status: "all", includeCompleted: 0 };

	const esc = value => frappe.utils.escape_html(value == null ? "" : String(value));
	const yesNoBadge = ok => ok
		? "<span class='indicator-pill green'>Completo</span>"
		: "<span class='indicator-pill orange'>Pendiente</span>";

	const getTypeState = (row, type) => {
		const fromApi = row.afiliaciones_estado && row.afiliaciones_estado[type];
		if (fromApi) return !!(fromApi.afiliado || fromApi.completo);
		const fallbackField = TYPE_META[type].field;
		const legacy = row.afiliacion || {};
		return !!legacy[fallbackField];
	};

	const getFilteredRows = () => {
		const q = (state.search || "").trim().toLowerCase();
		return (state.rows || []).filter(row => {
			if (q) {
				const blob = [row.full_name, row.numero_documento, row.pdv_destino_nombre, row.pdv_destino, row.cargo_postulado]
					.filter(Boolean)
					.join(" ")
					.toLowerCase();
				if (!blob.includes(q)) return false;
			}

			if (state.status === "priority" && !row.prioridad_alta) return false;
			if (state.status === "arl_pending" && getTypeState(row, "arl")) return false;
			if (state.status === "pending_any" && TYPE_ORDER.every(t => getTypeState(row, t))) return false;
			if (state.status === "complete_all" && !TYPE_ORDER.every(t => getTypeState(row, t))) return false;

			return true;
		});
	};

	const getNextPendingType = row => TYPE_ORDER.find(type => !getTypeState(row, type)) || TYPE_ORDER[0];
	const isFullyComplete = row => TYPE_ORDER.every(type => getTypeState(row, type));

	const renderCards = rows => {
		const cards = (rows || []).map(r => {
			const pdvLabel = r.pdv_destino_nombre || r.pdv_destino || "";
			const nextPendingType = getNextPendingType(r);
			const completeAll = isFullyComplete(r);
			const primaryLabel = completeAll ? "Marcar completo" : `Gestionar ${TYPE_META[nextPendingType].label}`;
			const badges = TYPE_ORDER.map(type => {
				const isDone = getTypeState(r, type);
				return `
					<div class='aff-badge ${isDone ? "is-complete" : "is-pending"}'>
						<span class='aff-badge-label'>${esc(TYPE_META[type].label)}</span>
						${yesNoBadge(isDone)}
					</div>
				`;
			}).join("");

			const prioridad = r.prioridad_alta
				? "<span class='indicator-pill red'>Prioridad alta</span>"
				: "";

			const diasIngreso = r.dias_restantes_ingreso == null
				? ""
				: `<span class='text-muted'>Ingreso en ${esc(r.dias_restantes_ingreso)} día(s)</span>`;

			return `
				<div class='aff-card' data-c='${esc(r.name)}'>
					<div class='aff-card-head'>
						<div class='aff-main'>
							<div class='aff-title-row'>
								<button type='button' class='btn btn-link btn-xs aff-name btn-cross-name' data-c='${esc(r.name)}'>${esc(r.full_name || r.name)}</button>
								${prioridad}
							</div>
							<div class='aff-meta'>CC ${esc(r.numero_documento || "-")}</div>
							<div class='aff-submeta'>
								<span>${esc(r.cargo_postulado || "Sin cargo")}</span>
								<span class='aff-dot'>•</span>
								<span title='${esc(r.pdv_destino || "")}'>${esc(pdvLabel || "Sin PDV")}</span>
							</div>
						</div>
						<div class='aff-right'>
							<div class='aff-general-state'>${yesNoBadge((r.afiliacion && r.afiliacion.estado_general) === "Completado")}</div>
							<div class='aff-time'>${diasIngreso}</div>
						</div>
					</div>
					<div class='aff-card-badges'>${badges}</div>
					<div class='aff-actions'>
						${completeAll
							? `<button class='btn btn-xs btn-success btn-complete' data-c='${esc(r.name)}'>${esc(primaryLabel)}</button>`
							: `<button class='btn btn-xs btn-primary btn-open-type' data-c='${esc(r.name)}' data-t='${esc(nextPendingType)}'>${esc(primaryLabel)}</button>`}
						<button class='btn btn-xs btn-link btn-detail' data-c='${esc(r.name)}'>Detalle</button>
						<button class='btn btn-xs btn-link btn-cross-name' data-c='${esc(r.name)}'>Cruce contratación</button>
					</div>
				</div>
			`;
		}).join("");

		$root.find(".cards-wrap").html(cards || "<div class='hubgh-empty'><span class='hubgh-empty-title'>Sin candidatos para esta combinación</span><p class='hubgh-empty-copy'>Limpiá los filtros o habilitá completos para recuperar contexto de afiliaciones.</p><div style='display:flex;gap:8px;flex-wrap:wrap;margin-top:12px'><button class='btn btn-sm btn-default btn-clear-filters'>Limpiar filtros</button><button class='btn btn-sm btn-primary btn-go-contracts'>Formalización</button></div></div>");
	};

	const refreshUI = () => renderCards(getFilteredRows());

	const formatCrossValue = value => {
		if (value === null || value === undefined) return "—";
		if (typeof value === "string" && !value.trim()) return "—";
		return esc(value);
	};

	const crossRow = (label, value) => `
		<div class='cross-row'>
			<div class='cross-label'>${esc(label)}</div>
			<div class='cross-value'>${formatCrossValue(value)}</div>
		</div>
	`;

	const crossSection = (title, fields) => `
		<div class='cross-section'>
			<div class='cross-section-title'>${esc(title)}</div>
			<div class='cross-grid'>${fields.join("")}</div>
		</div>
	`;

	const openContractSnapshot = candidate => {
		frappe.call("hubgh.hubgh.contratacion_service.affiliation_contract_snapshot", { candidate })
			.then(r => {
				const snapshot = r.message || {};
				const blocks = snapshot.blocks || {};
				const personales = blocks.personales || {};
				const contacto = blocks.contacto || {};
				const bancarios = blocks.bancarios || {};
				const laborales = blocks.laborales || {};
				const seguridad = blocks.seguridad_social || {};

				const dialog = new frappe.ui.Dialog({
					title: `Datos de Cruce de Contratación: ${(snapshot.candidate && snapshot.candidate.full_name) || candidate}`,
					fields: [{
						fieldtype: "HTML",
						fieldname: "contract_snapshot_html",
						options: [
							crossSection("Personales básicos", [
								crossRow("Tipo documento", personales.tipo_documento),
								crossRow("Número documento", personales.numero_documento),
								crossRow("Nombres", personales.nombres),
								crossRow("Primer apellido", personales.primer_apellido),
								crossRow("Segundo apellido", personales.segundo_apellido),
								crossRow("Fecha nacimiento", personales.fecha_nacimiento),
								crossRow("Fecha expedición", personales.fecha_expedicion),
							]),
							crossSection("Contacto / residencia", [
								crossRow("Dirección", contacto.direccion),
								crossRow("Barrio", contacto.barrio),
								crossRow("Ciudad", contacto.ciudad),
								crossRow("Departamento", contacto.departamento_residencia_siesa),
								crossRow("País", contacto.pais_residencia_siesa),
								crossRow("Celular", contacto.celular),
								crossRow("Email", contacto.email),
							]),
							crossSection("Bancarios", [
								crossRow("Banco", bancarios.banco_siesa),
								crossRow("Tipo cuenta", bancarios.tipo_cuenta_bancaria),
								crossRow("Número cuenta", bancarios.numero_cuenta_bancaria),
							]),
							crossSection("Laborales", [
								crossRow("PDV", laborales.pdv_destino),
								crossRow("Cargo", laborales.cargo_postulado),
								crossRow("Salario", laborales.salario),
								crossRow("Tipo contrato", laborales.tipo_contrato),
								crossRow("Fecha tentativa ingreso", laborales.fecha_tentativa_ingreso),
								crossRow("Fecha ingreso", laborales.fecha_ingreso),
								crossRow("Fecha fin contrato", laborales.fecha_fin_contrato),
								crossRow("Horas trabajadas mes", laborales.horas_trabajadas_mes),
							]),
							crossSection("Seguridad social", [
								crossRow("EPS", seguridad.eps_siesa),
								crossRow("AFP", seguridad.afp_siesa),
								crossRow("Cesantías", seguridad.cesantias_siesa),
								crossRow("CCF", seguridad.ccf_siesa),
								crossRow("ARL", seguridad.arl_codigo_siesa),
							]),
						].join(""),
					}],
					primary_action_label: "Cerrar",
					primary_action() {
						dialog.hide();
					},
				});

				dialog.show();
			});
	};

	const openDetail = (candidate, initialType = "arl") => {
		const uploadToFileAPI = file => {
			const formData = new FormData();
			formData.append("file", file);
			formData.append("is_private", 1);
			formData.append("doctype", "Candidato");
			formData.append("docname", candidate);
			return fetch("/api/method/upload_file", {
				method: "POST",
				body: formData,
				credentials: "same-origin",
				headers: { "X-Frappe-CSRF-Token": frappe.csrf_token },
			})
				.then(resp => resp.json())
				.then(resp => {
					if (!resp.message?.file_url) throw new Error("upload_error");
					return resp.message.file_url;
				});
		};

		frappe.call("hubgh.hubgh.page.bandeja_afiliaciones.bandeja_afiliaciones.affiliation_detail", { candidate })
			.then(r => {
				const detail = r.message || {};
				const types = detail.affiliations || {};
				const candidateData = detail.candidate || {};
				const toTypeKey = label => TYPE_ORDER.find(k => TYPE_META[k].label === label) || "arl";
				const typeDrafts = TYPE_ORDER.reduce((acc, key) => {
					const data = types[key] || {};
					acc[key] = {
						afiliado: data.afiliado ? 1 : 0,
						fecha_afiliacion: data.fecha_afiliacion || null,
						numero_afiliacion: data.numero_afiliacion || null,
						certificado: data.certificado || null,
					};
					return acc;
				}, {});
				let currentTypeKey = TYPE_ORDER.includes(initialType) ? initialType : "arl";
				const dialog = new frappe.ui.Dialog({
					title: `Afiliación: ${candidateData.full_name || candidate}`,
					fields: [
						{
							fieldtype: "Select",
							fieldname: "affiliation_type",
							label: "Tipo",
							options: TYPE_ORDER.map(k => `${TYPE_META[k].label}\n`).join("").trim(),
							default: TYPE_META.arl.label,
							reqd: 1,
						},
						{ fieldname: "afiliado", label: "Afiliado", fieldtype: "Check" },
						{ fieldname: "fecha_afiliacion", label: "Fecha afiliación", fieldtype: "Date" },
						{ fieldname: "numero_afiliacion", label: "Número afiliación", fieldtype: "Data" },
						{ fieldname: "siesa_entity", label: "Entidad (SIESA)", fieldtype: "Link", options: "Entidad EPS Siesa", hidden: 1 },
						{ fieldname: "certificado", fieldtype: "Data", hidden: 1 },
						{ fieldname: "certificado_preview", label: "Certificado", fieldtype: "HTML" },
						{ fieldname: "upload_certificado", label: "Subir certificado", fieldtype: "Button" },
						{ fieldname: "clear_certificado", label: "Quitar certificado", fieldtype: "Button" },
					],
					primary_action_label: "Guardar tipo",
					primary_action(values) {
						const selectedType = toTypeKey(values.affiliation_type);
						typeDrafts[selectedType] = {
							afiliado: values.afiliado ? 1 : 0,
							fecha_afiliacion: values.fecha_afiliacion || null,
							numero_afiliacion: values.numero_afiliacion || null,
							certificado: values.certificado || null,
						};

						const siesaMeta = SIESA_META_BY_TYPE[selectedType];
						const siesaValue = siesaMeta ? (values.siesa_entity || null) : null;
						const payload = {
							data: {
								[`${selectedType}_afiliado`]: typeDrafts[selectedType].afiliado ? 1 : 0,
								[`${selectedType}_fecha_afiliacion`]: typeDrafts[selectedType].fecha_afiliacion,
								[`${selectedType}_numero_afiliacion`]: typeDrafts[selectedType].numero_afiliacion,
								[`${selectedType}_certificado`]: typeDrafts[selectedType].certificado,
							},
						};
						if (siesaMeta) payload.data[siesaMeta.fieldname] = siesaValue;
						frappe.call("hubgh.hubgh.page.bandeja_afiliaciones.bandeja_afiliaciones.save_affiliation", {
							candidate,
							affiliation_type: selectedType,
							payload: JSON.stringify(payload),
						}).then(() => {
							frappe.show_alert({ indicator: "green", message: `Afiliación ${TYPE_META[selectedType].label} guardada` });
							dialog.hide();
							load();
						});
					},
				});

					const updateCertificatePreview = fileUrl => {
						const html = fileUrl
							? `<a href='${esc(fileUrl)}' target='_blank' rel='noopener'>${esc(fileUrl.split("/").pop() || fileUrl)}</a>`
							: "<span class='text-muted'>Sin certificado cargado</span>";
						dialog.fields_dict.certificado_preview.$wrapper.html(html);
					};

					const captureDraftFromForm = typeKey => {
						if (!TYPE_ORDER.includes(typeKey)) return;
						typeDrafts[typeKey] = {
							afiliado: dialog.get_value("afiliado") ? 1 : 0,
							fecha_afiliacion: dialog.get_value("fecha_afiliacion") || null,
							numero_afiliacion: dialog.get_value("numero_afiliacion") || null,
							certificado: dialog.get_value("certificado") || null,
						};
					};

					const setValuesFromType = typeKey => {
						const data = typeDrafts[typeKey] || {};
						const siesaMeta = SIESA_META_BY_TYPE[typeKey] || null;
						const siesaValue = siesaMeta ? (candidateData[siesaMeta.fieldname] || null) : null;
						dialog.set_value("afiliado", data.afiliado ? 1 : 0);
						dialog.set_value("fecha_afiliacion", data.fecha_afiliacion || null);
						dialog.set_value("numero_afiliacion", data.numero_afiliacion || null);
						dialog.set_value("certificado", data.certificado || null);

						dialog.set_df_property("siesa_entity", "hidden", !siesaMeta);
						dialog.set_df_property("siesa_entity", "reqd", !!siesaMeta);
						dialog.set_df_property("siesa_entity", "label", siesaMeta ? siesaMeta.label : "Entidad (SIESA)");
						dialog.set_df_property("siesa_entity", "options", siesaMeta ? siesaMeta.doctype : "Entidad EPS Siesa");
						dialog.refresh_field("siesa_entity");
						dialog.set_value("siesa_entity", siesaValue);
						updateCertificatePreview(data.certificado || null);
					};

					dialog.fields_dict.upload_certificado.input.onclick = () => {
						const picker = $("<input type='file' class='d-none' />");
						picker.on("change", function() {
							const file = this.files && this.files[0];
							if (!file) return;
							uploadToFileAPI(file)
								.then(fileUrl => {
									dialog.set_value("certificado", fileUrl);
									typeDrafts[currentTypeKey].certificado = fileUrl;
									updateCertificatePreview(fileUrl);
									frappe.show_alert({ indicator: "green", message: "Certificado cargado" });
								});
						});
						picker.trigger("click");
					};

					dialog.fields_dict.clear_certificado.input.onclick = () => {
						dialog.set_value("certificado", null);
						typeDrafts[currentTypeKey].certificado = null;
						updateCertificatePreview(null);
					};

					dialog.fields_dict.affiliation_type.df.onchange = () => {
						captureDraftFromForm(currentTypeKey);
						const selectedLabel = dialog.get_value("affiliation_type");
						const typeKey = toTypeKey(selectedLabel);
						currentTypeKey = typeKey;
						setValuesFromType(typeKey);
					};

					dialog.show();
					dialog.set_value("affiliation_type", TYPE_META[currentTypeKey]?.label || TYPE_META.arl.label);
					setValuesFromType(currentTypeKey);
			});
	};

	const bindEvents = () => {
		$root.find(".btn-detail").off("click").on("click", function() {
			const candidate = $(this).data("c");
			openDetail(candidate);
		});

		$root.find(".btn-open-type").off("click").on("click", function() {
			const candidate = $(this).data("c");
			const type = $(this).data("t") || "arl";
			openDetail(candidate, String(type));
		});

		$root.find(".btn-cross-name").off("click").on("click", function() {
			const candidate = $(this).data("c");
			openContractSnapshot(candidate);
		});

		$root.find(".btn-clear-filters").off("click").on("click", () => {
			state.search = "";
			state.status = "all";
			refreshUI();
			bindEvents();
		});

		$root.find(".btn-complete").off("click").on("click", function() {
			const candidate = $(this).data("c");
			frappe.call("hubgh.hubgh.page.bandeja_afiliaciones.bandeja_afiliaciones.mark_affiliation_complete", { candidate })
				.then(() => {
					frappe.show_alert({ indicator: "green", message: "Afiliación completada" });
					load();
				});
		});

		$root.find(".filter-search").off("input").on("input", function() {
			state.search = $(this).val();
			refreshUI();
			bindEvents();
		});

		$root.find(".filter-status").off("change").on("change", function() {
			state.status = $(this).val();
			refreshUI();
			bindEvents();
		});

		$root.find(".filter-include-completed").off("change").on("change", function() {
			state.includeCompleted = $(this).is(":checked") ? 1 : 0;
			load();
		});
	};

	const load = () => {
		frappe.call("hubgh.hubgh.page.bandeja_afiliaciones.bandeja_afiliaciones.affiliation_candidates", {
			include_completed: state.includeCompleted ? 1 : 0,
		})
			.then(r => {
				state.rows = r.message || [];
				refreshUI();
				bindEvents();
			});
	};

	$root.html(`
		<style>
			.aff-shell { display: grid; gap: 12px; }
			.aff-toolbar {
				display: flex;
				gap: 10px;
				align-items: center;
				background: #fff;
				border: 1px solid #e2e8f0;
				border-radius: 12px;
				padding: 10px 12px;
			}
			.aff-toolbar .filter-search { max-width: 480px; }
			.aff-toolbar .filter-status { max-width: 240px; }
			.cards-wrap { display: grid; gap: 12px; }
			.aff-card {
				background: #fff;
				border: 1px solid #e2e8f0;
				border-radius: 14px;
				padding: 14px;
				display: grid;
				gap: 12px;
			}
			.aff-card-head { display: flex; justify-content: space-between; gap: 14px; align-items: flex-start; }
			.aff-title-row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
			.aff-name { font-size: 15px; font-weight: 700; color: #1f2937; padding: 0; margin: 0; }
			.aff-name:hover, .aff-name:focus { color: #2563eb; text-decoration: underline; }
			.aff-meta, .aff-submeta, .aff-time { color: #64748b; font-size: 12px; }
			.aff-submeta { display: flex; gap: 6px; align-items: center; }
			.aff-dot { color: #94a3b8; }
			.aff-right { text-align: right; }
			.aff-card-badges { display: grid; grid-template-columns: repeat(5, minmax(120px, 1fr)); gap: 8px; }
			.aff-badge {
				display: flex;
				justify-content: space-between;
				align-items: center;
				border: 1px solid #e2e8f0;
				border-radius: 10px;
				padding: 8px 10px;
				background: #f8fafc;
			}
			.aff-badge.is-complete { border-color: #86efac; background: #f0fdf4; }
			.aff-badge.is-pending { border-color: #fed7aa; background: #fff7ed; }
			.aff-badge-label { font-size: 12px; font-weight: 600; color: #475569; }
			.aff-actions { display: flex; gap: 8px; justify-content: flex-end; }
			.aff-actions .btn-link { padding: 0 2px; }
			.cross-section { border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px; margin-bottom: 10px; }
			.cross-section-title { font-size: 12px; font-weight: 700; color: #334155; margin-bottom: 8px; text-transform: uppercase; letter-spacing: .03em; }
			.cross-grid { display: grid; grid-template-columns: repeat(2, minmax(220px, 1fr)); gap: 6px 12px; }
			.cross-row { display: grid; grid-template-columns: 150px 1fr; gap: 8px; align-items: start; }
			.cross-label { color: #64748b; font-size: 12px; }
			.cross-value { color: #1f2937; font-size: 12px; font-weight: 600; word-break: break-word; }
		</style>
			<div class='aff-shell'>
				<div class='hubgh-board-hero'>
					<div class='hubgh-board-hero-head'>
						<div>
							<div class='hubgh-board-kickers'><span class='hubgh-board-kicker'>RRLL</span><span class='hubgh-board-kicker'>Seguridad social</span></div>
							<h3 class='hubgh-board-title'>Afiliaciones por candidato</h3>
							<p class='hubgh-board-copy'>Compactá el estado por entidad, mantené visibles los cruces SIESA y usá una sola acción primaria para cerrar afiliaciones.</p>
						</div>
						<div class='hubgh-board-meta'><span class='hubgh-meta-pill'>${state.rows.length} candidatos en cola</span></div>
					</div>
					<div class='hubgh-board-shortcuts'>
						<button class='btn btn-sm btn-default btn-go-contracts'>Ir a contratación</button>
						<button class='btn btn-sm btn-default btn-go-reportes'>Ver reportes SIESA</button>
						<button class='btn btn-sm btn-default btn-go-docs'>Carpeta documental</button>
					</div>
				</div>
				<div class='aff-toolbar'>
					<input class='form-control filter-search' placeholder='Buscar por nombre, documento, cargo o PDV' />
					<select class='form-control filter-status'>
					<option value='all'>Todos</option>
				<option value='priority'>Prioridad alta</option>
				<option value='arl_pending'>ARL pendiente</option>
					<option value='pending_any'>Con pendientes</option>
					<option value='complete_all'>Todo completo</option>
					</select>
					<label class='text-muted' style='display:flex;gap:6px;align-items:center;margin:0;'>
						<input type='checkbox' class='filter-include-completed' ${state.includeCompleted ? "checked" : ""} />
						Incluir completos
					</label>
					<button class='btn btn-sm btn-default btn-clear-filters'>Limpiar filtros</button>
				</div>
				<div class='cards-wrap'></div>
			</div>
		`);
		$root.find('.btn-go-contracts').on('click', () => frappe.set_route('app', 'bandeja_contratacion'));
		$root.find('.btn-go-reportes').on('click', () => frappe.set_route('app', 'reportes_siesa'));
		$root.find('.btn-go-docs').on('click', () => frappe.set_route('app', 'carpeta_documental_empleado'));
	load();
};
