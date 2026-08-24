frappe.pages["bandeja_disponibilidad"].on_page_load = function(wrapper) {
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
		title: "Disponibilidad de personal",
		single_column: true,
	});

	const ui = window.hubghBandejasUI || { injectBaseStyles() {} };
	ui.injectBaseStyles();
	const esc = value => frappe.utils.escape_html(value == null ? "" : String(value));

	const $root = $("<div class='bandeja-disponibilidad hubgh-board-shell'></div>").appendTo(page.body);

	const getFilters = () => ({
		search: $root.find(".f-search").val() || null,
		poblacion: $root.find(".f-poblacion").val() || null,
		pdv: $root.find(".f-pdv").val() || null,
		fecha_desde: $root.find(".f-desde").val() || null,
		fecha_hasta: $root.find(".f-hasta").val() || null,
	});

	const renderRows = (rows) => {
		const htmlRows = (rows || []).map(r => `
			<tr>
				<td>${esc(r.nombre)}</td>
				<td>${esc(r.cedula)}</td>
				<td>${esc(r.punto_de_venta)}</td>
				<td>${esc(r.vinculacion)}</td>
				<td>${esc(r.estado)}</td>
				<td>${esc(r.fecha_ingreso)}</td>
				<td>${esc(r.dias_resumen)}</td>
			</tr>
		`).join("");

		$root.find(".table-wrap").html(`
			<div class='hubgh-table-shell'>
				<table class='table table-bordered hubgh-table'>
					<thead>
						<tr>
							<th>Nombre</th><th>Cédula</th><th>Punto de venta</th><th>Vinculación</th><th>Estado</th><th>Fecha de ingreso</th><th>Días</th>
						</tr>
					</thead>
					<tbody>${htmlRows || "<tr><td colspan='7'>Sin resultados</td></tr>"}</tbody>
				</table>
			</div>
		`);
		$root.find(".result-pill").text(`${(rows || []).length} de ${(rows || []).length} registros`);
	};

	const load = () => {
		frappe.call("hubgh.hubgh.page.bandeja_disponibilidad.bandeja_disponibilidad.list_disponibilidad", getFilters())
			.then(r => renderRows(r.message || []));
	};

	$root.html(`
		<div class='hubgh-board-hero'>
			<div class='hubgh-board-hero-head'>
				<div>
					<div class='hubgh-board-kickers'><span class='hubgh-board-kicker'>RRLL</span><span class='hubgh-board-kicker'>Disponibilidad</span></div>
					<h3 class='hubgh-board-title'>Disponibilidad de personal</h3>
					<p class='hubgh-board-copy'>Consulta la disponibilidad horaria de contratados y candidatos en proceso, y exporta el Excel con el detalle completo por día.</p>
				</div>
				<div class='hubgh-board-meta'><span class='hubgh-meta-pill result-pill'>0 de 0 registros</span></div>
			</div>
		</div>
		<div class='filters hubgh-board-toolbar' style='align-items:end'>
			<div><label>Buscar</label><input type='text' class='form-control f-search' placeholder='Cédula o documento'></div>
			<div><label>Población</label>
				<select class='form-control f-poblacion'>
					<option value=''>Todos</option>
					<option value='contratados'>Contratados</option>
					<option value='en_proceso'>En proceso</option>
				</select>
			</div>
			<div><label>PDV</label><input type='text' class='form-control f-pdv' placeholder='Código PDV'></div>
			<div><label>Desde</label><input type='date' class='form-control f-desde'></div>
			<div><label>Hasta</label><input type='date' class='form-control f-hasta'></div>
			<div><button class='btn btn-default btn-load'>Buscar</button></div>
		</div>
		<div class='table-wrap'></div>
		<div style='margin-top:12px'>
			<button class='btn btn-primary action-export-xlsx'>Exportar Excel</button>
		</div>
	`);

	$root.find(".btn-load").on("click", load);

	$root.find(".action-export-xlsx").on("click", function() {
		const $btn = $(this);
		const originalText = $btn.html();
		$btn.prop("disabled", true).html("Generando…");
		frappe.call("hubgh.hubgh.page.bandeja_disponibilidad.bandeja_disponibilidad.export_disponibilidad_xlsx", {
			filters: getFilters(),
		})
			.then(r => {
				const m = (r && r.message) || {};
				if (!m.content_b64) {
					frappe.msgprint("No fue posible generar el archivo.");
					return;
				}
				if (m.count === 0) {
					frappe.show_alert({ indicator: "orange", message: "No hay registros para exportar con los filtros actuales." });
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
				a.download = m.filename || "disponibilidad_personal.xlsx";
				document.body.appendChild(a);
				a.click();
				document.body.removeChild(a);
				URL.revokeObjectURL(url);
				if (m.count > 0) {
					frappe.show_alert({ indicator: "green", message: `Exportados ${m.count} registros` });
				}
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
