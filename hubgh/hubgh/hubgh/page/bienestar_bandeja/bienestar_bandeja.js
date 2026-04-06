let bienestarBandejaState = {
	globalFilter: "",
	tableFilters: {
		seguimientos_pendientes: "",
		seguimientos_hoy: "",
		seguimientos_vencidos: "",
		seguimientos_proximos: "",
		evaluaciones_pendientes: "",
		evaluaciones_vencidas: "",
		evaluaciones_no_aprobadas: "",
		alertas_abiertas: "",
		alertas_en_seguimiento: "",
		alertas_escaladas: "",
		compromisos_activos: "",
		compromisos_sin_mejora: "",
		compromisos_escalados_rrll: "",
	},
	data: null,
};

const TABLES = {
	seguimientos_pendientes: {
		title: "Seguimientos pendientes",
		source: "colas.seguimientos.pendientes",
		tipo: "seguimiento",
		columns: [
			{ key: "empleado_label", label: "Empleado" },
			{ key: "punto_venta_label", label: "PDV" },
			{ key: "responsable_label", label: "Responsable" },
			{ key: "tipo_resumen", label: "Tipo/Resumen" },
			{ key: "fecha_programada", label: "Fecha" },
			{ key: "estado", label: "Estado" },
		],
	},
	seguimientos_hoy: {
		title: "Seguimientos hoy",
		source: "colas.seguimientos.hoy",
		tipo: "seguimiento",
		columns: [
			{ key: "empleado_label", label: "Empleado" },
			{ key: "punto_venta_label", label: "PDV" },
			{ key: "responsable_label", label: "Responsable" },
			{ key: "tipo_resumen", label: "Tipo/Resumen" },
			{ key: "fecha_programada", label: "Fecha" },
			{ key: "estado", label: "Estado" },
		],
	},
	seguimientos_vencidos: {
		title: "Seguimientos vencidos",
		source: "colas.seguimientos.vencidos",
		tipo: "seguimiento",
		columns: [
			{ key: "empleado_label", label: "Empleado" },
			{ key: "punto_venta_label", label: "PDV" },
			{ key: "responsable_label", label: "Responsable" },
			{ key: "tipo_resumen", label: "Tipo/Resumen" },
			{ key: "fecha_programada", label: "Fecha" },
			{ key: "estado", label: "Estado" },
		],
	},
	seguimientos_proximos: {
		title: "Seguimientos próximos",
		source: "colas.seguimientos.proximos",
		tipo: "seguimiento",
		columns: [
			{ key: "empleado_label", label: "Empleado" },
			{ key: "punto_venta_label", label: "PDV" },
			{ key: "responsable_label", label: "Responsable" },
			{ key: "tipo_resumen", label: "Tipo/Resumen" },
			{ key: "fecha_programada", label: "Fecha" },
			{ key: "estado", label: "Estado" },
		],
	},
	evaluaciones_pendientes: {
		title: "Evaluaciones pendientes",
		source: "colas.evaluaciones.pendientes",
		tipo: "evaluacion",
		columns: [
			{ key: "empleado_label", label: "Empleado" },
			{ key: "punto_venta_label", label: "PDV" },
			{ key: "responsable_label", label: "Responsable" },
			{ key: "tipo_resumen", label: "Tipo/Resumen" },
			{ key: "fecha_evaluacion", label: "Fecha" },
			{ key: "estado", label: "Estado" },
		],
	},
	evaluaciones_vencidas: {
		title: "Evaluaciones vencidas",
		source: "colas.evaluaciones.vencidas",
		tipo: "evaluacion",
		columns: [
			{ key: "empleado_label", label: "Empleado" },
			{ key: "punto_venta_label", label: "PDV" },
			{ key: "responsable_label", label: "Responsable" },
			{ key: "tipo_resumen", label: "Tipo/Resumen" },
			{ key: "fecha_evaluacion", label: "Fecha" },
			{ key: "estado", label: "Estado" },
		],
	},
	evaluaciones_no_aprobadas: {
		title: "Evaluaciones no aprobadas",
		source: "colas.evaluaciones.no_aprobadas",
		tipo: "evaluacion",
		columns: [
			{ key: "empleado_label", label: "Empleado" },
			{ key: "punto_venta_label", label: "PDV" },
			{ key: "responsable_label", label: "Responsable" },
			{ key: "tipo_resumen", label: "Tipo/Resumen" },
			{ key: "fecha_evaluacion", label: "Fecha" },
			{ key: "rrll_handoff_label", label: "Handoff RRLL" },
		],
	},
	alertas_abiertas: {
		title: "Alertas abiertas",
		source: "colas.alertas.abiertas",
		tipo: "alerta",
		columns: [
			{ key: "empleado_label", label: "Empleado" },
			{ key: "punto_venta_label", label: "PDV" },
			{ key: "responsable_label", label: "Responsable" },
			{ key: "tipo_resumen", label: "Tipo/Resumen" },
			{ key: "prioridad", label: "Prioridad" },
			{ key: "estado", label: "Estado" },
		],
	},
	alertas_en_seguimiento: {
		title: "Alertas en seguimiento",
		source: "colas.alertas.en_seguimiento",
		tipo: "alerta",
		columns: [
			{ key: "empleado_label", label: "Empleado" },
			{ key: "punto_venta_label", label: "PDV" },
			{ key: "responsable_label", label: "Responsable" },
			{ key: "tipo_resumen", label: "Tipo/Resumen" },
			{ key: "prioridad", label: "Prioridad" },
			{ key: "estado", label: "Estado" },
		],
	},
	alertas_escaladas: {
		title: "Alertas escaladas",
		source: "colas.alertas.escaladas",
		tipo: "alerta",
		columns: [
			{ key: "empleado_label", label: "Empleado" },
			{ key: "punto_venta_label", label: "PDV" },
			{ key: "responsable_label", label: "Responsable" },
			{ key: "tipo_resumen", label: "Tipo/Resumen" },
			{ key: "origen_contexto_display", label: "Origen" },
			{ key: "rrll_handoff_label", label: "Handoff RRLL" },
		],
	},
	compromisos_activos: {
		title: "Compromisos activos",
		source: "colas.compromisos.activos",
		tipo: "compromiso",
		columns: [
			{ key: "empleado_label", label: "Empleado" },
			{ key: "punto_venta_label", label: "PDV" },
			{ key: "responsable_label", label: "Responsable" },
			{ key: "tipo_resumen", label: "Tipo/Resumen" },
			{ key: "fecha_limite", label: "Límite" },
			{ key: "estado", label: "Estado" },
		],
	},
	compromisos_sin_mejora: {
		title: "Compromisos sin mejora",
		source: "colas.compromisos.sin_mejora",
		tipo: "compromiso",
		columns: [
			{ key: "empleado_label", label: "Empleado" },
			{ key: "punto_venta_label", label: "PDV" },
			{ key: "responsable_label", label: "Responsable" },
			{ key: "tipo_resumen", label: "Tipo/Resumen" },
			{ key: "origen_contexto_display", label: "Origen" },
			{ key: "rrll_handoff_label", label: "Handoff RRLL" },
		],
	},
	compromisos_escalados_rrll: {
		title: "Compromisos escalados RRLL",
		source: "colas.compromisos.escalados_rrll",
		tipo: "compromiso",
		columns: [
			{ key: "empleado_label", label: "Empleado" },
			{ key: "punto_venta_label", label: "PDV" },
			{ key: "responsable_label", label: "Responsable" },
			{ key: "tipo_resumen", label: "Tipo/Resumen" },
			{ key: "origen_contexto_display", label: "Origen" },
			{ key: "rrll_handoff_label", label: "Handoff RRLL" },
		],
	},
};

const MANUAL_STATE_OPTIONS = {
	seguimiento: ["Pendiente", "En gestión", "Realizado", "Cancelado", "Vencido"],
	evaluacion: ["Pendiente", "En gestión", "Realizada", "No aprobada", "Cerrada"],
	alerta: ["Abierta", "En seguimiento", "Escalada", "Cerrada"],
	compromiso: ["Activo", "En seguimiento", "Cerrado", "Escalado RRLL"],
};

Object.values(TABLES).forEach(cfg => {
	if (!cfg || !Array.isArray(cfg.columns)) return;
	if (cfg.columns.some(col => col.key === "semaforo_label")) return;
	const estadoIndex = cfg.columns.findIndex(col => col.key === "estado");
	const insertAt = estadoIndex >= 0 ? estadoIndex : cfg.columns.length;
	cfg.columns.splice(insertAt, 0, { key: "semaforo_label", label: "Semáforo" });
});

frappe.pages["bienestar_bandeja"].on_page_load = function(wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Bandeja Central de Bienestar",
		single_column: true,
	});

	injectStylesOnce();

	page.add_field({
		fieldname: "punto_venta",
		label: "Punto de Venta",
		fieldtype: "Link",
		options: "Punto de Venta",
		change: () => fetchAndRender(page),
	});

	page.add_field({
		fieldname: "responsable",
		label: "Responsable",
		fieldtype: "Link",
		options: "User",
		change: () => fetchAndRender(page),
	});

	page.add_field({
		fieldname: "estado",
		label: "Estado",
		fieldtype: "Data",
		change: () => fetchAndRender(page),
	});

	page.add_field({
		fieldname: "tipo",
		label: "Tipo",
		fieldtype: "Select",
		options: "\nseguimiento\nevaluacion\nalerta\ncompromiso",
		change: () => fetchAndRender(page),
	});

	fetchAndRender(page);
};

function fetchAndRender(page) {
	frappe.call({
		method: "hubgh.hubgh.page.bienestar_bandeja.bienestar_bandeja.get_bienestar_bandeja",
		args: {
			punto_venta: page.fields_dict.punto_venta.get_value(),
			responsable: page.fields_dict.responsable.get_value(),
			estado: page.fields_dict.estado.get_value(),
			tipo: page.fields_dict.tipo.get_value(),
		},
		callback: r => {
			bienestarBandejaState.data = r.message || {};
			render(page);
		},
	});
}

function render(page) {
	const data = bienestarBandejaState.data || {};
	const kpi = data.kpis || {};
	const $container = $(page.main || page.body);
	$container.empty();

	$container.append(`
		<div class="bien-shell">
			<div class="bien-toolbar card-shadow">
				<div class="bien-toolbar-head">
					<div>
						<div class="bien-toolbar-kickers"><span>Bienestar</span><span>Seguimiento 5/15/30</span></div>
						<div class="bien-toolbar-title">Centro operativo de bienestar</div>
						<div class="bien-toolbar-subtitle">Agrupá seguimientos, alertas y compromisos con la misma lógica visual y dejá las escaladas a RRLL a un clic.</div>
					</div>
					<div class="bien-toolbar-links">
						<a class="btn btn-sm btn-default" href="/app/persona_360">Persona 360</a>
						<a class="btn btn-sm btn-default" href="/app/punto_360">Punto 360</a>
					</div>
				</div>
			<div class="bien-global-filter-wrap">
				<input id="bien-global-filter" class="form-control" placeholder="Buscar en toda la bandeja..." value="${escapeHtml(bienestarBandejaState.globalFilter || "")}" />
			</div>
			<div class="bien-toolbar-links">
				<button class="btn btn-sm btn-default action-clear-filters">Limpiar filtros</button>
			</div>
		</div>

			<div class="row bien-kpi-row">
				${kpiCardHtml("Total operativo", kpi.total_operativo || 0, "neutral")}
				${kpiCardHtml("Total vencimientos", kpi.total_vencimientos || 0, "danger")}
				${kpiCardHtml("Seg. vencidos", kpi.seguimientos_vencidos || 0, "danger")}
				${kpiCardHtml("Eval. vencidas", kpi.evaluaciones_vencidas || 0, "warning")}
			</div>

			<div class="row bien-grid-row">
				<div class="col-md-6">${tableHtml("seguimientos_pendientes")}</div>
				<div class="col-md-6">${tableHtml("seguimientos_hoy")}</div>
			</div>
			<div class="row bien-grid-row">
				<div class="col-md-6">${tableHtml("seguimientos_vencidos")}</div>
				<div class="col-md-6">${tableHtml("seguimientos_proximos")}</div>
			</div>

			<div class="row bien-grid-row">
				<div class="col-md-4">${tableHtml("evaluaciones_pendientes")}</div>
				<div class="col-md-4">${tableHtml("evaluaciones_vencidas")}</div>
				<div class="col-md-4">${tableHtml("evaluaciones_no_aprobadas")}</div>
			</div>

			<div class="row bien-grid-row">
				<div class="col-md-4">${tableHtml("alertas_abiertas")}</div>
				<div class="col-md-4">${tableHtml("alertas_en_seguimiento")}</div>
				<div class="col-md-4">${tableHtml("alertas_escaladas")}</div>
			</div>

			<div class="row bien-grid-row">
				<div class="col-md-4">${tableHtml("compromisos_activos")}</div>
				<div class="col-md-4">${tableHtml("compromisos_sin_mejora")}</div>
				<div class="col-md-4">${tableHtml("compromisos_escalados_rrll")}</div>
			</div>
		</div>
	`);

	bindEvents(page);
}

function tableHtml(tableKey) {
	const cfg = TABLES[tableKey];
	if (!cfg) return "";
	const rows = applyFilters(resolvePath(bienestarBandejaState.data || {}, cfg.source) || [], tableKey);
	const cols = cfg.columns || [];

	return `
		<div class="bien-card card-shadow">
			<div class="bien-card-header">
				<div>
					<div class="bien-card-title">${escapeHtml(cfg.title)}</div>
					<div class="bien-card-copy">Filtro local visible y gestión rápida sin cambiar de vista.</div>
				</div>
				<div class="bien-card-count">${rows.length}</div>
			</div>
			<div class="bien-filter-row">
				<input data-table-key="${tableKey}" class="form-control bien-table-filter" placeholder="Filtrar bloque..." value="${escapeHtml((bienestarBandejaState.tableFilters || {})[tableKey] || "")}" />
			</div>
			<div class="bien-table-wrap">
				<table class="table table-sm bien-table">
					<thead>
						<tr>
							${cols.map(c => `<th>${escapeHtml(c.label)}</th>`).join("")}
							<th>Acciones</th>
						</tr>
					</thead>
					<tbody>
						${rows.length ? rows.map(r => rowHtml(r, cols, cfg.tipo)).join("") : `<tr><td colspan="${cols.length + 1}" class="bien-empty"><div class="bien-empty-state"><strong>Sin datos para este bloque</strong><span>Probá limpiar filtros o navegar a Persona 360 para revisar el contexto.</span><button class="btn btn-xs btn-default action-clear-filters">Limpiar filtros</button></div></td></tr>`}
					</tbody>
				</table>
			</div>
		</div>
	`;
}

function rowHtml(row, cols, tipo) {
	const cells = cols.map(c => `<td>${formatCell(c.key, row[c.key], tipo, row)}</td>`).join("");
	return `<tr>
		${cells}
		<td class="bien-actions">
			<button class="btn btn-xs btn-primary action-manage" data-tipo="${escapeHtml(tipo)}" data-name="${escapeHtml(row.name || "")}">Gestionar</button>
			<button class="btn btn-xs btn-link action-open-doc" data-tipo="${escapeHtml(tipo)}" data-name="${escapeHtml(row.name || "")}">Abrir</button>
		</td>
	</tr>`;
}

function bindEvents(page) {
	const $root = $(page.main || page.body);

	$root.find("#bien-global-filter").off("input").on("input", function() {
		bienestarBandejaState.globalFilter = ($(this).val() || "").toString();
		render(page);
	});

	$root.find(".bien-table-filter").off("input").on("input", function() {
		const key = $(this).data("tableKey");
		bienestarBandejaState.tableFilters[key] = ($(this).val() || "").toString();
		render(page);
	});

	$root.find(".action-open-doc").off("click").on("click", function() {
		const tipo = ($(this).data("tipo") || "").toString();
		const name = ($(this).data("name") || "").toString();
		if (!tipo || !name) return;
		const map = {
			seguimiento: "Bienestar Seguimiento Ingreso",
			evaluacion: "Bienestar Evaluacion Periodo Prueba",
			alerta: "Bienestar Alerta",
			compromiso: "Bienestar Compromiso",
		};
		frappe.set_route("Form", map[tipo], name);
	});

	$root.find(".action-manage").off("click").on("click", function() {
		const tipo = ($(this).data("tipo") || "").toString();
		const name = ($(this).data("name") || "").toString();
		openManageDialog(tipo, name, page);
	});

	$root.find(".action-clear-filters").off("click").on("click", function() {
		bienestarBandejaState.globalFilter = "";
		bienestarBandejaState.tableFilters = Object.keys(bienestarBandejaState.tableFilters || {}).reduce((acc, key) => {
			acc[key] = "";
			return acc;
		}, {});
		render(page);
	});
}

function openManageDialog(tipo, name, page) {
	const options = MANUAL_STATE_OPTIONS[tipo] || [];
	const selectOptions = [""].concat(options).join("\n");
	const d = new frappe.ui.Dialog({
		title: `Gestionar ${tipo} ${name}`,
		fields: [
			{ fieldname: "nuevo_estado", fieldtype: "Select", label: "Nuevo estado", options: selectOptions },
			{ fieldname: "gestion_breve", fieldtype: "Small Text", label: "Gestión breve", reqd: 1 },
			{ fieldname: "reprogramar_fecha", fieldtype: "Date", label: "Reprogramar fecha" },
		],
		primary_action_label: "Guardar",
		primary_action(values) {
			frappe.call({
				method: "hubgh.hubgh.page.bienestar_bandeja.bienestar_bandeja.gestionar_bienestar_item",
				args: {
					tipo,
					item_name: name,
					nuevo_estado: values.nuevo_estado,
					gestion_breve: values.gestion_breve,
					reprogramar_fecha: values.reprogramar_fecha,
				},
				callback: () => {
					d.hide();
					fetchAndRender(page);
				},
			});
		},
	});
	d.show();
}

function applyFilters(rows, tableKey) {
	const global = normalizeText(bienestarBandejaState.globalFilter);
	const local = normalizeText((bienestarBandejaState.tableFilters || {})[tableKey] || "");
	return rows.filter(row => {
		const blob = normalizeText(JSON.stringify(row || {}));
		return (!global || blob.includes(global)) && (!local || blob.includes(local));
	});
}

function resolvePath(obj, path) {
	return path.split(".").reduce((acc, key) => (acc ? acc[key] : undefined), obj);
}

function kpiCardHtml(label, value, tone) {
	return `
		<div class="col-md-3">
			<div class="bien-kpi bien-kpi-${tone} card-shadow">
				<div class="bien-kpi-label">${escapeHtml(label)}</div>
				<div class="bien-kpi-value">${escapeHtml(value)}</div>
			</div>
		</div>
	`;
}

function formatCell(key, value, tipo, row) {
	if (value === null || value === undefined || value === "") return "-";
	if (key === "name") {
		const routeMap = {
			seguimiento: "bienestar-seguimiento-ingreso",
			evaluacion: "bienestar-evaluacion-periodo-prueba",
			alerta: "bienestar-alerta",
			compromiso: "bienestar-compromiso",
		};
		const route = routeMap[tipo] || "";
		return route ? `<a href="/app/${route}/${encodeURIComponent(value)}">${escapeHtml(value)}</a>` : escapeHtml(value);
	}
	if (["empleado_label", "punto_venta_label", "responsable_label"].includes(key)) {
		const secondaryKeyByField = {
			empleado_label: "ficha_empleado",
			punto_venta_label: "punto_venta",
			responsable_label: "responsable_bienestar",
		};
		const secondaryKey = secondaryKeyByField[key];
		const secondary = row && row[secondaryKey] ? `<div class="small text-muted">${escapeHtml(String(row[secondaryKey]))}</div>` : "";
		return `<div>${escapeHtml(String(value))}</div>${secondary}`;
	}
	if (key === "tipo_resumen") {
		const secondary = row && row.name ? `<div class="small text-muted">${escapeHtml(String(row.name))}</div>` : "";
		return `<div>${escapeHtml(String(value))}</div>${secondary}`;
	}
	if (key === "semaforo_label") {
		const tone = (row && row.semaforo_tone) || "neutral";
		const score = row && row.semaforo_score !== null && row.semaforo_score !== undefined ? `${row.semaforo_score}%` : "Sin score";
		const toneClass = `bien-semaforo bien-semaforo-${tone}`;
		return `<div><span class="${toneClass}">${escapeHtml(String(value || "Sin score"))}</span><div class="small text-muted">${escapeHtml(score)}</div></div>`;
	}
	if (["origen_contexto_display", "rrll_handoff_label"].includes(key)) {
		const secondaryKeyByField = {
			origen_contexto_display: "origen_contexto_secondary",
			rrll_handoff_label: "rrll_handoff_name",
		};
		const secondaryKey = secondaryKeyByField[key];
		const secondary = row && row[secondaryKey] ? `<div class="small text-muted">${escapeHtml(String(row[secondaryKey]))}</div>` : "";
		return `<div class="small">${escapeHtml(String(value))}</div>${secondary}`;
	}
	if (typeof value === "number") return escapeHtml(String(value));
	if (String(key) === "sin_mejora") return Number(value) ? "Sí" : "No";
	return escapeHtml(String(value));
}

function normalizeText(value) {
	return (value || "").toString().toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
}

function escapeHtml(value) {
	return (value || "")
		.toString()
		.replace(/&/g, "&amp;")
		.replace(/</g, "&lt;")
		.replace(/>/g, "&gt;")
		.replace(/"/g, "&quot;")
		.replace(/'/g, "&#39;");
}

function injectStylesOnce() {
	if (document.getElementById("bienestar-bandeja-styles")) return;
	const style = document.createElement("style");
	style.id = "bienestar-bandeja-styles";
	style.innerHTML = `
		.bien-shell { padding: 12px 8px 24px; }
		.card-shadow { box-shadow: 0 6px 16px rgba(16, 24, 40, 0.06); }
		.bien-toolbar { background: #f8fbff; border: 1px solid #e3eaf7; border-radius: 12px; padding: 14px; margin-bottom: 14px; }
		.bien-toolbar-head { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; flex-wrap: wrap; }
		.bien-toolbar-kickers { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 8px; }
		.bien-toolbar-kickers span { border-radius: 999px; padding: 4px 10px; background: #dbeafe; color: #1d4ed8; font-size: 11px; font-weight: 700; }
		.bien-toolbar-links { display: flex; gap: 8px; flex-wrap: wrap; }
		.bien-toolbar-title { font-size: 16px; font-weight: 700; color: #1f2a44; }
		.bien-toolbar-subtitle { font-size: 12px; color: #6b7280; margin: 2px 0 10px; }
		.bien-global-filter-wrap { max-width: 520px; }
		.bien-kpi-row { margin-bottom: 8px; }
		.bien-kpi { border-radius: 12px; padding: 12px 14px; border: 1px solid #e8edf6; background: #fff; margin-bottom: 10px; }
		.bien-kpi-label { color: #5b6475; font-size: 12px; }
		.bien-kpi-value { color: #1f2a44; font-size: 24px; font-weight: 700; line-height: 1.1; }
		.bien-kpi-danger .bien-kpi-value { color: #dc2626; }
		.bien-kpi-warning .bien-kpi-value { color: #d97706; }
		.bien-grid-row { margin-bottom: 8px; }
		.bien-card { background: #fff; border: 1px solid #e8edf6; border-radius: 12px; padding: 10px; margin-bottom: 12px; }
		.bien-card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
		.bien-card-title { font-weight: 700; color: #1f2a44; }
		.bien-card-copy { color: #64748b; font-size: 11px; margin-top: 2px; }
		.bien-card-count { min-width: 28px; text-align: center; border-radius: 999px; padding: 2px 8px; background: #eef4ff; color: #3359a8; font-size: 12px; font-weight: 700; }
		.bien-filter-row { margin-bottom: 8px; }
		.bien-table-wrap { overflow-x: auto; }
		.bien-table thead th { background: #f8fafc; border-bottom: 1px solid #e5e7eb; color: #334155; font-weight: 700; white-space: nowrap; }
		.bien-empty { text-align: center; color: #6b7280; }
		.bien-actions { white-space: nowrap; }
		.bien-actions .btn-link { padding: 0 2px; }
		.bien-empty-state { display: grid; gap: 6px; justify-items: center; padding: 8px 0; }
		.bien-semaforo { display: inline-block; padding: 2px 8px; border-radius: 999px; font-size: 11px; font-weight: 700; }
		.bien-semaforo-success { background: #dcfce7; color: #166534; }
		.bien-semaforo-warning { background: #fef3c7; color: #92400e; }
		.bien-semaforo-danger { background: #fee2e2; color: #991b1b; }
		.bien-semaforo-neutral { background: #e5e7eb; color: #374151; }
		@media (max-width: 768px) {
			.bien-shell { padding: 8px 0 18px; }
			.bien-table-wrap { max-height: none; }
		}
	`;
	document.head.appendChild(style);
}
