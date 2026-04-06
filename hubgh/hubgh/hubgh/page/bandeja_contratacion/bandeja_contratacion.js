frappe.pages["bandeja_contratacion"].on_page_load = function(wrapper) {
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
		title: "RRLL - Formalizacion de contratacion",
		single_column: true,
	});

	(window.hubghBandejasUI || { injectBaseStyles() {} }).injectBaseStyles();
	const $root = $("<div class='hubgh-board-shell'></div>").appendTo(page.body);
	const esc = value => frappe.utils.escape_html(value == null ? "" : String(value));
	let state = { rows: [], search: "", status: "idle", error: "" };

	const formatTentativeDate = value => {
		if (!value) return "-";
		try {
			return frappe.datetime.str_to_user(value) || value;
		} catch (error) {
			return value;
		}
	};

	const bindCommonActions = () => {
		$root.find(".btn-reportes, .go-siesa").off("click").on("click", function() {
			frappe.set_route("app", "reportes_siesa");
		});

		$root.find(".btn-afiliaciones").off("click").on("click", function() {
			frappe.set_route("app", "bandeja_afiliaciones");
		});
	};

	const renderFrame = (contentHtml, metaLabel) => {
		$root.html(`
			<div class='hubgh-board-hero'>
				<div class='hubgh-board-hero-head'>
					<div>
						<div class='hubgh-board-kickers'><span class='hubgh-board-kicker'>RRLL</span><span class='hubgh-board-kicker'>Contrato + SIESA</span></div>
						<h3 class='hubgh-board-title'>Formalizacion operativa</h3>
						<p class='hubgh-board-copy'>Esta bandeja concentra el ultimo paso antes de activar el contrato y exportar conectores SIESA, con una sola accion primaria por candidato.</p>
					</div>
					<div class='hubgh-board-meta'><span class='hubgh-meta-pill'>${esc(metaLabel)}</span></div>
				</div>
				<div class='hubgh-board-shortcuts'>
					<button class='btn btn-sm btn-primary btn-reportes'>Abrir reportes SIESA</button>
					<button class='btn btn-sm btn-default btn-afiliaciones'>Ver afiliaciones</button>
				</div>
			</div>
			${contentHtml}
		`);

		bindCommonActions();
	};

	const renderLoading = () => {
		renderFrame(`
			<div class='hubgh-empty'>
				<span class='hubgh-empty-title'>Cargando candidatos listos para contrato</span>
				<p class='hubgh-empty-copy'>Estamos consultando el handoff desde Seleccion y afiliaciones.</p>
			</div>
		`, "Cargando bandeja...");
	};

	const renderError = message => {
		renderFrame(`
			<div class='hubgh-empty'>
				<span class='hubgh-empty-title'>No pudimos renderizar la bandeja de contratacion</span>
				<p class='hubgh-empty-copy'>${esc(message || "Ocurrio un error inesperado al cargar la cola operativa.")}</p>
				<div style='display:flex;gap:8px;flex-wrap:wrap;margin-top:12px'>
					<button class='btn btn-sm btn-primary btn-retry'>Reintentar</button>
					<button class='btn btn-sm btn-default btn-afiliaciones'>Ver afiliaciones</button>
				</div>
			</div>
		`, "Carga con incidencias");

		$root.find(".btn-retry").off("click").on("click", function() {
			load();
		});
	};

	const getFilteredRows = () => {
		const q = (state.search || "").trim().toLowerCase();
		return (state.rows || []).filter(row => {
			if (!q) return true;
			const blob = [row.full_name, row.numero_documento, row.fecha_tentativa_ingreso].filter(Boolean).join(" ").toLowerCase();
			return blob.includes(q);
		});
	};

	const render = () => {
		const rows = getFilteredRows();
		const htmlCards = rows.map(r => `
			<div class='hubgh-card'>
				<div class='hubgh-card-head'>
					<div class='hubgh-main'>
						<div class='hubgh-title-row'>
							<div class='hubgh-name'>${esc(r.full_name || "")}</div>
							<span class='indicator-pill blue'>Listo para formalizar</span>
						</div>
						<div class='hubgh-meta'>CC ${esc(r.numero_documento || "-")}</div>
						<div class='hubgh-submeta'>
							<span>Ingreso tentativo: ${esc(formatTentativeDate(r.fecha_tentativa_ingreso))}</span>
						</div>
						<div class='hubgh-badges-grid'>
							<div class='hubgh-badge is-complete'>
								<span class='hubgh-badge-label'>Documento</span>
								<span>${esc(r.numero_documento || "-")}</span>
							</div>
							<div class='hubgh-badge is-pending'>
								<span class='hubgh-badge-label'>Accion primaria</span>
								<span>Crear contrato</span>
							</div>
						</div>
					</div>
				</div>
				<div class='hubgh-actions'>
					<button class='btn btn-xs btn-primary btn-create' data-c='${esc(r.name)}'>Crear contrato</button>
					<button class='btn btn-xs btn-link go-siesa'>Reportes SIESA</button>
				</div>
			</div>
		`).join("");

		renderFrame(`
			<div class='hubgh-board-toolbar'>
				<input type='text' class='form-control filter-search' placeholder='Buscar por nombre, documento o fecha tentativa' value='${esc(state.search || "")}' />
				<button class='btn btn-sm btn-default btn-clear-filters'>Limpiar filtros</button>
				<div class='hubgh-board-toolbar-copy'>${rows.length} visibles de ${state.rows.length}</div>
			</div>
			<div class='hubgh-cards-wrap'>${htmlCards || "<div class='hubgh-empty'><span class='hubgh-empty-title'>Sin candidatos listos para contrato</span><p class='hubgh-empty-copy'>Cuando Seleccion y afiliaciones dejen el handoff completo, aca queda visible la creacion del contrato y el salto a SIESA.</p><div style='display:flex;gap:8px;flex-wrap:wrap;margin-top:12px'><button class='btn btn-sm btn-default btn-clear-filters'>Limpiar filtros</button><button class='btn btn-sm btn-primary btn-afiliaciones'>Ver afiliaciones</button></div></div>"}</div>
		`, `${rows.length} candidatos listos`);

		$root.find(".filter-search").off("input").on("input", function() {
			state.search = $(this).val() || "";
			render();
		});

		$root.find(".btn-clear-filters").off("click").on("click", function() {
			state.search = "";
			render();
		});

		$root.find(".btn-create").off("click").on("click", function() {
			const candidate = $(this).data("c");
			frappe.call("hubgh.hubgh.contratacion_service.affiliation_contract_snapshot", { candidate })
				.then(snap => {
					const blocks = (snap.message && snap.message.blocks) || {};
					const laborales = blocks.laborales || {};
					const bancarios = blocks.bancarios || {};
					const contacto = blocks.contacto || {};
					const seguridad = blocks.seguridad_social || {};

					const d = new frappe.ui.Dialog({
						title: "Crear contrato",
						fields: [
							{ fieldname: "numero_contrato", label: "Numero Contrato", fieldtype: "Int", default: 1, reqd: 1 },
							{ fieldname: "tipo_contrato", label: "Tipo Contrato", fieldtype: "Select", options: "Indefinido\nFijo\nAprendizaje Lectiva\nAprendizaje Productiva", default: laborales.tipo_contrato || "Indefinido", reqd: 1 },
							{ fieldname: "fecha_ingreso", label: "Fecha Ingreso", fieldtype: "Date", default: laborales.fecha_ingreso || laborales.fecha_tentativa_ingreso, reqd: 1 },
							{ fieldname: "fecha_fin_contrato", label: "Fecha Fin Contrato", fieldtype: "Date", default: laborales.fecha_fin_contrato || "" },
							{ fieldname: "salario", label: "Salario", fieldtype: "Currency", default: laborales.salario || 0, reqd: 1 },
							{ fieldname: "horas_trabajadas_mes", label: "Horas Mes", fieldtype: "Float", default: laborales.horas_trabajadas_mes || 220 },
							{ fieldtype: "Section Break", label: "Laborales y bancarios" },
							{ fieldname: "pdv_destino", label: "PDV Destino", fieldtype: "Link", options: "Punto de Venta", default: laborales.pdv_destino || "" },
							{ fieldname: "cargo", label: "Cargo", fieldtype: "Link", options: "Cargo", default: laborales.cargo_postulado || "" },
							{ fieldtype: "Column Break" },
							{ fieldname: "banco_siesa", label: "Banco", fieldtype: "Link", options: "Banco Siesa", default: bancarios.banco_siesa || "" },
							{ fieldname: "tipo_cuenta_bancaria", label: "Tipo Cuenta", fieldtype: "Select", options: "Ahorros\nCorriente\nTarjeta Prepago", default: bancarios.tipo_cuenta_bancaria || "Ahorros" },
							{ fieldname: "numero_cuenta_bancaria", label: "Numero Cuenta", fieldtype: "Data", default: bancarios.numero_cuenta_bancaria || "" },
							{ fieldtype: "Section Break", label: "Seguridad social" },
							{ fieldname: "eps_siesa", label: "EPS", fieldtype: "Link", options: "Entidad EPS Siesa", default: seguridad.eps_siesa || "" },
							{ fieldname: "afp_siesa", label: "AFP", fieldtype: "Link", options: "Entidad AFP Siesa", default: seguridad.afp_siesa || "" },
							{ fieldtype: "Column Break" },
							{ fieldname: "cesantias_siesa", label: "Cesantias", fieldtype: "Link", options: "Entidad Cesantias Siesa", default: seguridad.cesantias_siesa || "" },
							{ fieldname: "ccf_siesa", label: "CCF", fieldtype: "Link", options: "Entidad CCF Siesa", default: seguridad.ccf_siesa || "" },
							{ fieldtype: "Section Break", label: "Campos SIESA" },
							{ fieldname: "tipo_cotizante_siesa", label: "Tipo Cotizante", fieldtype: "Link", options: "Tipo Cotizante Siesa" },
							{ fieldname: "centro_costos_siesa", label: "Centro Costos", fieldtype: "Link", options: "Centro Costos Siesa" },
							{ fieldtype: "Column Break" },
							{ fieldname: "unidad_negocio_siesa", label: "Unidad Negocio", fieldtype: "Link", options: "Unidad Negocio Siesa" },
							{ fieldname: "centro_trabajo_siesa", label: "Centro Trabajo", fieldtype: "Link", options: "Centro Trabajo Siesa" },
							{ fieldname: "grupo_empleados_siesa", label: "Grupo Empleados", fieldtype: "Link", options: "Grupo Empleados Siesa" },
							{ fieldtype: "Section Break", label: "Complementarios (para estado completo)" },
							{ fieldname: "direccion", label: "Direccion", fieldtype: "Data", default: contacto.direccion || "" },
							{ fieldname: "celular", label: "Celular", fieldtype: "Data", default: contacto.celular || "" },
							{ fieldtype: "Column Break" },
							{ fieldname: "email", label: "Email", fieldtype: "Data", default: contacto.email || "" },
							{ fieldname: "ciudad_residencia_siesa", label: "Ciudad Residencia", fieldtype: "Data", default: contacto.ciudad || "" },
							{ fieldtype: "Section Break", label: "Documento de contrato" },
							{ fieldname: "contrato_firmado", label: "Contrato Firmado", fieldtype: "Attach", description: "Adjunta el contrato firmado (opcional, recomendado)" },
						],
						primary_action_label: "Guardar",
						primary_action(values) {
							frappe.call("hubgh.hubgh.page.bandeja_contratacion.bandeja_contratacion.create_contract", {
								candidate,
								payload: JSON.stringify(values),
							}).then(res => {
								const contract = res.message && res.message.name;
								if (!contract) return;
								frappe.call("hubgh.hubgh.page.bandeja_contratacion.bandeja_contratacion.submit_contract", {
									contract,
									signed_file_url: values.contrato_firmado || null,
								}).then(() => {
									frappe.show_alert({ indicator: "green", message: "Contrato creado y activado" });
									d.hide();
									load();
								});
							}).catch(err => {
								const msg = (err && err.message) || "No fue posible crear el contrato";
								frappe.msgprint(msg);
							});
						},
					});

					d.fields_dict.ccf_siesa.get_query = () => ({
						filters: {
							enabled: 1,
							code: ["in", ["001", "002"]],
						},
					});

					d.fields_dict.unidad_negocio_siesa.get_query = () => ({
						filters: { enabled: 1 },
					});

					d.fields_dict.centro_trabajo_siesa.get_query = () => ({
						filters: { enabled: 1 },
					});

					d.show();
				})
				.catch(err => {
					const msg = (err && (err.message || err.exc || err._server_messages)) || "No fue posible cargar el snapshot de contratacion.";
					frappe.msgprint(msg);
				});
		});
	};

	const load = () => {
		state.status = "loading";
		state.error = "";
		renderLoading();
		frappe.call("hubgh.hubgh.page.bandeja_contratacion.bandeja_contratacion.contract_candidates")
			.then(r => {
				state.rows = r.message || [];
				state.status = "ready";
				render();
			})
			.catch(err => {
				state.rows = [];
				state.status = "error";
				state.error = (err && (err.message || err.exc || err._server_messages)) || "No fue posible consultar candidatos listos para contrato.";
				renderError(state.error);
			});
	};

	load();
};
