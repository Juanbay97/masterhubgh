frappe.pages["candidatos_rechazados"].on_page_load = function(wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Selección - Candidatos rechazados",
		single_column: true,
	});

	(window.hubghBandejasUI || { injectBaseStyles() {} }).injectBaseStyles();
	const $root = $("<div class='hubgh-board-shell'></div>").appendTo(page.body);
	const esc = value => frappe.utils.escape_html(value == null ? "" : String(value));
	let state = { rows: [], search: "" };

	const getFilteredRows = () => {
		const q = (state.search || "").trim().toLowerCase();
		return (state.rows || []).filter(row => {
			if (!q) return true;
			const blob = [row.full_name, row.numero_documento, row.motivo_rechazo].filter(Boolean).join(" ").toLowerCase();
			return blob.includes(q);
		});
	};

	const reactivate = candidate => {
		frappe.call("hubgh.hubgh.page.candidatos_rechazados.candidatos_rechazados.reactivate_candidate", { candidate })
			.then(() => {
				frappe.show_alert({ indicator: "green", message: "Candidato reactivado" });
				load();
			});
	};

	const renderCards = rows => {
		const lastRejected = rows[0]?.fecha_rechazo ? frappe.datetime.str_to_user(rows[0].fecha_rechazo) : "Sin registro reciente";
		const cards = (rows || []).map(row => `
			<div class='hubgh-card'>
				<div class='hubgh-card-head'>
					<div class='hubgh-main'>
						<div class='hubgh-title-row'>
							<div class='hubgh-name'>${esc(row.full_name || row.name)}</div>
							<span class='indicator-pill red'>Rechazado</span>
						</div>
						<div class='hubgh-meta'>CC ${esc(row.numero_documento || "-")}</div>
						<div class='hubgh-submeta'>
							<span>Fecha: ${esc(frappe.datetime.str_to_user(row.fecha_rechazo || "") || "-")}</span>
						</div>
						<div class='hubgh-submeta'><span>Motivo: ${esc(row.motivo_rechazo || "-")}</span></div>
					</div>
				</div>
				<div class='hubgh-actions'>
					<button class='btn btn-xs btn-success action-reactivate' data-c='${esc(row.name)}'>Reactivar</button>
				</div>
			</div>
		`).join("");

		$root.find(".hubgh-cards-wrap").html(cards || "<div class='hubgh-empty'><span class='hubgh-empty-title'>Sin rechazos para mostrar</span><p class='hubgh-empty-copy'>Cuando Selección descarte candidatos con motivo registrado, aparecen acá para reactivación o auditoría rápida.</p></div>");
		$root.find(".hubgh-board-toolbar-copy").text(`${rows.length} visibles de ${state.rows.length}`);
		$root.find(".hubgh-meta-pill.last-rejected").text(`Último rechazo: ${lastRejected}`);
	};

	const bindEvents = () => {
		$root.find(".filter-search").off("input").on("input", function() {
			state.search = $(this).val() || "";
			renderCards(getFilteredRows());
			bindEvents();
		});

		$root.find(".action-reactivate").off("click").on("click", function() {
			reactivate($(this).data("c"));
		});
	};

	const load = () => {
		frappe.call("hubgh.hubgh.page.candidatos_rechazados.candidatos_rechazados.list_rejected_candidates")
			.then(r => {
				state.rows = r.message || [];
				renderCards(getFilteredRows());
				bindEvents();
			});
	};

	$root.html(`
		<div class='hubgh-board-hero'>
			<div class='hubgh-board-hero-head'>
				<div>
					<div class='hubgh-board-kickers'><span class='hubgh-board-kicker'>Selección</span><span class='hubgh-board-kicker'>Auditoría rápida</span></div>
					<h3 class='hubgh-board-title'>Rechazos con trazabilidad</h3>
					<p class='hubgh-board-copy'>Dejá a mano el motivo de descarte y una acción clara de reactivación para no convertir esta vista en un fondo muerto.</p>
				</div>
				<div class='hubgh-board-meta'>
					<span class='hubgh-meta-pill'>${state.rows.length} rechazados</span>
					<span class='hubgh-meta-pill last-rejected'>Último rechazo: Sin registro reciente</span>
				</div>
			</div>
			<div class='hubgh-board-shortcuts'>
				<button class='btn btn-sm btn-default go-selection-board'>Volver a control documental</button>
				<button class='btn btn-sm btn-default go-medical-board'>Ir a exámenes médicos</button>
			</div>
		</div>
		<div class='hubgh-board-toolbar'>
			<input type='text' class='form-control filter-search' placeholder='Buscar por nombre, documento o motivo' />
			<div class='hubgh-board-toolbar-copy'>0 visibles</div>
		</div>
		<div class='sel-docs-subtitle'>Listado de candidatos rechazados con trazabilidad de motivo y acción de reactivación.</div>
		<div class='hubgh-cards-wrap'></div>
	`);

	$root.find(".go-selection-board").on("click", () => frappe.set_route("app", "seleccion_documentos"));
	$root.find(".go-medical-board").on("click", () => frappe.set_route("app", "sst_examenes_medicos"));

	load();
};
