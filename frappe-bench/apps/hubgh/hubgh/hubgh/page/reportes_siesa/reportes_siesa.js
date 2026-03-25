frappe.pages["reportes_siesa"].on_page_load = function(wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "RRLL - Reportes SIESA",
		single_column: true,
	});

	(window.hubghBandejasUI || { injectBaseStyles() {} }).injectBaseStyles();
	const $root = $("<div class='reportes-siesa hubgh-board-shell'></div>").appendTo(page.body);

	const renderRows = (rows) => {
		const htmlRows = (rows || []).map(r => {
			const status = r.ready_siesa ? "✅ Listo" : "⚠️ Incompleto";
			const errors = (r.errores || []).join(" | ");
			return `
				<tr>
					<td><input type='checkbox' class='row-check' data-c='${r.name}' ${r.ready_siesa ? "checked" : ""} ${r.ready_siesa ? "" : "disabled"}></td>
					<td><a href='#' class='text-bold clickable-name' data-candidate='${r.name}' title='Click para editar datos de contratación'>${frappe.utils.escape_html(r.full_name || "")}</a></td>
					<td>${frappe.utils.escape_html(r.numero_documento || "")}</td>
					<td>${frappe.utils.escape_html(r.fecha_tentativa_ingreso || "")}</td>
					<td>${status}</td>
					<td style='font-size:12px;color:#6b7280'>${frappe.utils.escape_html(errors)}</td>
				</tr>
			`;
		}).join("");

		$root.find(".table-wrap").html(`
			<div class='hubgh-table-shell'>
			<table class='table table-bordered hubgh-table'>
				<thead><tr><th></th><th>Candidato</th><th>Documento</th><th>Ingreso</th><th>Estado</th><th>Observaciones</th></tr></thead>
				<tbody>${htmlRows || "<tr><td colspan='6'>Sin resultados</td></tr>"}</tbody>
			</table>
			</div>
		`);
		$root.find('.result-pill').text(`${(rows || []).length} registros`);
	};

	const load = () => {
		frappe.call("hubgh.hubgh.page.reportes_siesa.reportes_siesa.siesa_candidates", {
			fecha_desde: $root.find(".f-desde").val() || null,
			fecha_hasta: $root.find(".f-hasta").val() || null,
			only_ready: $root.find(".only-ready").is(":checked") ? 1 : 0,
		}).then(r => renderRows(r.message || []));
	};

	const selectedCandidates = () => {
		return $root.find(".row-check:checked").map(function() { return $(this).data("c"); }).get();
	};

	$root.html(`
		<div class='hubgh-board-hero'>
			<div class='hubgh-board-hero-head'>
				<div>
					<div class='hubgh-board-kickers'><span class='hubgh-board-kicker'>RRLL</span><span class='hubgh-board-kicker'>Conectores SIESA</span></div>
					<h3 class='hubgh-board-title'>Exportación lista para conector</h3>
					<p class='hubgh-board-copy'>Mantené visible qué registros están listos y cuáles siguen incompletos antes de descargar archivos para SIESA.</p>
				</div>
				<div class='hubgh-board-meta'><span class='hubgh-meta-pill result-pill'>0 registros</span></div>
			</div>
			<div class='hubgh-board-shortcuts'>
				<button class='btn btn-sm btn-default go-contracts'>Formalización</button>
				<button class='btn btn-sm btn-default go-folder'>Carpeta documental</button>
			</div>
		</div>
		<div class='filters hubgh-board-toolbar' style='align-items:end'>
			<div><label>Desde</label><input type='date' class='form-control f-desde'></div>
			<div><label>Hasta</label><input type='date' class='form-control f-hasta'></div>
			<div><label><input type='checkbox' class='only-ready' checked> Solo listos SIESA</label></div>
			<div><button class='btn btn-default btn-load'>Buscar</button></div>
		</div>
		<div class='table-wrap'></div>
		<div style='display:flex;gap:8px;margin-top:12px'>
			<button class='btn btn-primary btn-emp'>Descargar Conector Empleados</button>
			<button class='btn btn-default btn-cont'>Descargar Conector Contratos</button>
		</div>
	`);

	$root.find('.go-contracts').on('click', () => frappe.set_route('app', 'bandeja_contratacion'));
	$root.find('.go-folder').on('click', () => frappe.set_route('app', 'carpeta_documental_empleado'));

	// Click on candidate name to open Datos Contratacion
	$root.on('click', '.clickable-name', function(e) {
		e.preventDefault();
		const candidateName = $(this).data('candidate');
		if (candidateName) {
			frappe.call("hubgh.hubgh.page.reportes_siesa.reportes_siesa.get_datos_contratacion_for_candidate", {
				candidate: candidateName
			}).then(r => {
				const datosName = r.message;
				if (datosName) {
					frappe.set_route('app', 'form', 'Datos Contratacion', datosName);
				} else {
					frappe.msgprint("No existe Datos Contratacion para este candidato");
				}
			});
		}
	});

	$root.find(".btn-load").on("click", load);

	$root.find(".btn-emp").on("click", () => {
		const selected = selectedCandidates();
		if (!selected.length) {
			frappe.msgprint("Selecciona al menos un candidato listo para SIESA.");
			return;
		}
		window.open(`/api/method/hubgh.hubgh.siesa_export.exportar_conector_empleados?candidatos=${encodeURIComponent(JSON.stringify(selected))}`);
	});

	$root.find(".btn-cont").on("click", () => {
		const selected = selectedCandidates();
		if (!selected.length) {
			frappe.msgprint("Selecciona al menos un candidato listo para SIESA.");
			return;
		}
		window.open(`/api/method/hubgh.hubgh.siesa_export.exportar_conector_contratos?candidatos=${encodeURIComponent(JSON.stringify(selected))}`);
	});

	load();
};
