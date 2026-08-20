frappe.pages["seleccion_cruce_contratacion"].on_page_load = function(wrapper) {
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
		title: "Cruce Selección - Contratación",
		single_column: true,
	});

	const ui = window.hubghBandejasUI || { injectBaseStyles() {} };
	ui.injectBaseStyles();
	const esc = value => frappe.utils.escape_html(value == null ? "" : String(value));

	const $root = $("<div class='seleccion-cruce-contratacion hubgh-board-shell'></div>").appendTo(page.body);

	const getFilters = () => ({
		estado: $root.find(".f-estado").val() || null,
		pdv: $root.find(".f-pdv").val() || null,
		fecha_desde: $root.find(".f-desde").val() || null,
		fecha_hasta: $root.find(".f-hasta").val() || null,
		search: $root.find(".f-search").val() || null,
	});

	const renderRows = (rows) => {
		const htmlRows = (rows || []).map(r => `
			<tr>
				<td>${esc(r.full_name)}</td>
				<td>${esc(r.numero_documento)}</td>
				<td>${esc(r.pdv_destino_nombre)}</td>
				<td>${esc(r.cargo_postulado)}</td>
				<td>${esc(r.estado_proceso)}</td>
				<td>${esc(r.fecha_tentativa_ingreso)}</td>
			</tr>
		`).join("");

		$root.find(".table-wrap").html(`
			<div class='hubgh-table-shell'>
				<table class='table table-bordered hubgh-table'>
					<thead>
						<tr>
							<th>Candidato</th><th>Documento</th><th>PDV</th><th>Cargo</th><th>Estado</th><th>Ingreso</th>
						</tr>
					</thead>
					<tbody>${htmlRows || "<tr><td colspan='6'>Sin resultados</td></tr>"}</tbody>
				</table>
			</div>
		`);
		$root.find(".result-pill").text(`${(rows || []).length} registros`);
	};

	const load = () => {
		frappe.call("hubgh.hubgh.page.seleccion_cruce_contratacion.seleccion_cruce_contratacion.list_cruce_candidates", getFilters())
			.then(r => renderRows(r.message || []));
	};

	$root.html(`
		<div class='hubgh-board-hero'>
			<div class='hubgh-board-hero-head'>
				<div>
					<div class='hubgh-board-kickers'><span class='hubgh-board-kicker'>Selección</span><span class='hubgh-board-kicker'>Cruce</span></div>
					<h3 class='hubgh-board-title'>Cruce de selección para contratación</h3>
					<p class='hubgh-board-copy'>Consulta el cruce operativo por estado, PDV y fecha, y exporta el archivo Excel con las 49 columnas del template.</p>
				</div>
				<div class='hubgh-board-meta'><span class='hubgh-meta-pill result-pill'>0 registros</span></div>
			</div>
		</div>
		<div class='filters hubgh-board-toolbar' style='align-items:end'>
			<div><label>Buscar</label><input type='text' class='form-control f-search' placeholder='Nombre o documento'></div>
			<div><label>Estado</label>
				<select class='form-control f-estado'>
					<option value=''>Todos</option>
					<option value='En documentación'>En documentación</option>
					<option value='En examen médico'>En examen médico</option>
					<option value='En afiliación'>En afiliación</option>
					<option value='Listo para contratar'>Listo para contratar</option>
					<option value='Contratado'>Contratado</option>
				</select>
			</div>
			<div><label>PDV</label><input type='text' class='form-control f-pdv' placeholder='Código PDV'></div>
			<div><label>Desde</label><input type='date' class='form-control f-desde'></div>
			<div><label>Hasta</label><input type='date' class='form-control f-hasta'></div>
			<div><button class='btn btn-default btn-load'>Buscar</button></div>
		</div>
		<div class='table-wrap'></div>
		<div style='margin-top:12px'>
			<button class='btn btn-primary action-export-xlsx'>Exportar Excel (49 columnas)</button>
		</div>
	`);

	$root.find(".btn-load").on("click", load);

	$root.find(".action-export-xlsx").on("click", function() {
		const $btn = $(this);
		const originalText = $btn.html();
		$btn.prop("disabled", true).html("Generando…");
		frappe.call("hubgh.hubgh.page.seleccion_cruce_contratacion.seleccion_cruce_contratacion.export_cruce_xlsx", {
			filters: getFilters(),
		})
			.then(r => {
				const m = (r && r.message) || {};
				if (!m.content_b64) {
					frappe.msgprint("No fue posible generar el archivo.");
					return;
				}
				const byteChars = atob(m.content_b64);
				const bytes = new Uint8Array(byteChars.length);
				for (let i = 0; i < byteChars.length; i++) bytes[i] = byteChars.charCodeAt(i);
				const blob = new Blob([bytes], {
					type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
				});
				const url = URL.createObjectURL(blob);
				const a = document.createElement("a");
				a.href = url;
				a.download = m.filename || "cruce_seleccion.xlsx";
				document.body.appendChild(a);
				a.click();
				document.body.removeChild(a);
				URL.revokeObjectURL(url);
				frappe.show_alert({ indicator: "green", message: `Exportados ${m.count} candidatos` });
			})
			.catch(err => {
				const msg = (err && (err.message || err.exc || err._server_messages)) || "No fue posible generar el archivo.";
				frappe.msgprint(msg);
			})
			.finally(() => {
				$btn.prop("disabled", false).html(originalText);
			});
	});

	load();
};
