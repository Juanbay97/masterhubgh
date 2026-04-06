let sstBandejaState = {
	globalFilter: "",
	tableFilters: {
		cola_alertas: "",
		cola_accidentes: "",
		cola_incapacidades: "",
		cola_radar: "",
		cola_novedades: "",
	},
	data: null,
};

const TABLE_CONFIG = {
	cola_alertas: {
		title: "Alertas SST por prioridad",
		columns: [
			{ key: "empleado_label", label: "Empleado" },
			{ key: "punto_venta_label", label: "PDV" },
			{ key: "responsable_label", label: "Responsable" },
			{ key: "alerta_label", label: "Alerta" },
			{ key: "tipo_resumen", label: "Tipo/Resumen" },
			{ key: "fecha_programada", label: "Fecha" },
		],
		actions: ["abrir_alerta", "abrir_novedad", "reprogramar", "atender"],
	},
	cola_accidentes: {
		title: "Accidentes abiertos",
		columns: [
			{ key: "empleado_label", label: "Empleado" },
			{ key: "punto_venta_label", label: "PDV" },
			{ key: "responsable_label", label: "Responsable" },
			{ key: "tipo_resumen", label: "Tipo/Resumen" },
			{ key: "estado", label: "Estado" },
			{ key: "prioridad", label: "Prioridad" },
			{ key: "rrll_handoff_label", label: "Handoff RRLL" },
			{ key: "proxima_alerta_fecha", label: "Próxima gestión" },
		],
		actions: ["abrir_novedad", "escalar_rrll"],
	},
	cola_incapacidades: {
		title: "Incapacidades activas",
		columns: [
			{ key: "empleado_label", label: "Empleado" },
			{ key: "punto_venta_label", label: "PDV" },
			{ key: "responsable_label", label: "Responsable" },
			{ key: "tipo_resumen", label: "Tipo/Resumen" },
			{ key: "estado", label: "Estado" },
			{ key: "rrll_handoff_label", label: "Handoff RRLL" },
			{ key: "proxima_alerta_fecha", label: "Control" },
		],
		actions: ["abrir_novedad", "escalar_rrll"],
	},
	cola_radar: {
		title: "Radar y seguimientos",
		columns: [
			{ key: "empleado_label", label: "Empleado" },
			{ key: "punto_venta_label", label: "PDV" },
			{ key: "responsable_label", label: "Responsable" },
			{ key: "tipo_resumen", label: "Tipo/Resumen" },
			{ key: "categoria_seguimiento", label: "Categoría" },
			{ key: "estado", label: "Estado" },
			{ key: "rrll_handoff_label", label: "Handoff RRLL" },
		],
		actions: ["abrir_novedad", "escalar_rrll"],
	},
	cola_novedades: {
		title: "Novedades SST abiertas",
		columns: [
			{ key: "empleado_label", label: "Empleado" },
			{ key: "punto_venta_label", label: "PDV" },
			{ key: "responsable_label", label: "Responsable" },
			{ key: "tipo_resumen", label: "Tipo/Resumen" },
			{ key: "estado", label: "Estado" },
			{ key: "prioridad", label: "Prioridad" },
			{ key: "rrll_handoff_label", label: "Handoff RRLL" },
		],
		actions: ["abrir_novedad", "escalar_rrll"],
	},
};

frappe.pages["sst_bandeja"].on_page_load = function(wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Bandeja SST Central",
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
		fieldname: "categoria",
		label: "Categoría Radar",
		fieldtype: "Select",
		options: "\nGestante\nLactante\nCondición médica\nAT abierto\nIncapacidad larga\nPadre gestante\nOtro",
		change: () => fetchAndRender(page),
	});

	page.add_field({
		fieldname: "responsable",
		label: "Responsable",
		fieldtype: "Link",
		options: "User",
		change: () => fetchAndRender(page),
	});

	fetchAndRender(page);
};

function fetchAndRender(page) {
	frappe.call({
		method: "hubgh.hubgh.page.sst_bandeja.sst_bandeja.get_sst_bandeja",
		args: {
			punto_venta: page.fields_dict.punto_venta.get_value(),
			categoria: page.fields_dict.categoria.get_value(),
			responsable: page.fields_dict.responsable.get_value(),
		},
		callback: r => {
			sstBandejaState.data = r.message || {};
			render(page);
		},
	});
}

function render(page) {
	const data = sstBandejaState.data || {};
	const kpi = data.kpis || {};
	const ex = data.resumen_examenes || {};
	const $container = $(page.main || page.body);
	$container.empty();

	$container.append(`
		<div class="sst-shell">
			<div class="sst-toolbar card-shadow">
				<div class="sst-toolbar-head">
					<div>
						<div class="sst-toolbar-kickers"><span>Operación SST</span><span>Alertas y casos</span></div>
						<div class="sst-toolbar-title">Centro de gestión SST</div>
						<div class="sst-toolbar-subtitle">Priorizá vencimientos, resolvé acciones rápidas y navegá a exámenes médicos sin abrir otra lista de la lista.</div>
					</div>
					<div class="sst-toolbar-links">
						<a class="btn btn-sm btn-default" href="/app/sst_examenes_medicos">Exámenes médicos</a>
						<a class="btn btn-sm btn-default" href="/app/punto_360">Punto 360</a>
					</div>
				</div>
			<div class="sst-global-filter-wrap">
				<input id="sst-global-filter" class="form-control" placeholder="Buscar en toda la bandeja..." value="${escapeHtml(sstBandejaState.globalFilter || "")}" />
			</div>
			<div class="sst-toolbar-links">
				<button class="btn btn-sm btn-default action-clear-filters">Limpiar filtros</button>
			</div>
		</div>

			<div class="row sst-kpi-row">
				${kpiCardHtml("Alertas activas", kpi.total_alertas || 0, "neutral")}
				${kpiCardHtml("Vencidas", kpi.alertas_vencidas || 0, "danger")}
				${kpiCardHtml("Hoy", kpi.alertas_hoy || 0, "warning")}
				${kpiCardHtml("Novedades abiertas", kpi.novedades_abiertas || 0, "info")}
				${kpiCardHtml("Accidentes", kpi.accidentes_abiertos || 0, "danger")}
				${kpiCardHtml("Incapacidades", kpi.incapacidades_activas || 0, "warning")}
				${kpiCardHtml("Casos radar", kpi.casos_radar || 0, "success")}
				${kpiCardHtml("Exámenes pendientes", kpi.examenes_pendientes || 0, "info")}
			</div>

			<div class="sst-exam-summary card-shadow">
				<div>
					<div class="sst-card-title">Resumen Exámenes Médicos</div>
					<div class="sst-toolbar-subtitle">Pendientes: <strong>${escapeHtml(ex.pendientes || 0)}</strong> · Histórico: <strong>${escapeHtml(ex.historico || 0)}</strong></div>
				</div>
				<div>
					<a class="btn btn-sm btn-primary" href="${escapeHtml(ex.ruta || "/app/sst_examenes_medicos")}">Ir a Exámenes Médicos</a>
				</div>
			</div>

			<div class="row sst-grid-row">
				<div class="col-md-12">${tableCardHtml("cola_alertas", applyFilters(data.cola_alertas || [], "cola_alertas"))}</div>
			</div>
			<div class="row sst-grid-row">
				<div class="col-md-6">${tableCardHtml("cola_accidentes", applyFilters(data.cola_accidentes || [], "cola_accidentes"))}</div>
				<div class="col-md-6">${tableCardHtml("cola_incapacidades", applyFilters(data.cola_incapacidades || [], "cola_incapacidades"))}</div>
			</div>
			<div class="row sst-grid-row">
				<div class="col-md-6">${tableCardHtml("cola_radar", applyFilters(data.cola_radar || [], "cola_radar"))}</div>
				<div class="col-md-6">${tableCardHtml("cola_novedades", applyFilters(data.cola_novedades || [], "cola_novedades"))}</div>
			</div>
		</div>
	`);

	bindEvents(page);
}

function bindEvents(page) {
	const $root = $(page.main || page.body);

	$root.find("#sst-global-filter").off("input").on("input", function() {
		sstBandejaState.globalFilter = ($(this).val() || "").toString();
		render(page);
	});

	$root.find(".sst-table-filter").off("input").on("input", function() {
		const key = $(this).data("tableKey");
		sstBandejaState.tableFilters[key] = ($(this).val() || "").toString();
		render(page);
	});

	$root.find(".action-open-doc").off("click").on("click", function() {
		const doctype = $(this).data("doctype");
		const name = $(this).data("name");
		if (doctype && name) frappe.set_route("Form", doctype, name);
	});

	$root.find(".action-reprogram").off("click").on("click", function() {
		const alerta = $(this).data("name");
		openReprogramDialog(alerta, page);
	});

	$root.find(".action-attend").off("click").on("click", function() {
		const alerta = $(this).data("name");
		frappe.call({
			method: "hubgh.hubgh.page.sst_bandeja.sst_bandeja.atender_alerta",
			args: { alerta_name: alerta, cerrar: 1 },
			callback: () => fetchAndRender(page),
		});
	});

	$root.find(".action-handoff-rrll").off("click").on("click", function() {
		const novedad = $(this).data("name");
		frappe.call({
			method: "hubgh.hubgh.doctype.novedad_sst.novedad_sst.create_rrll_handoff",
			args: { novedad_name: novedad },
			callback: r => {
				const ghNovedad = r.message && r.message.gh_novedad;
				if (ghNovedad) {
					frappe.show_alert({ message: `Traslado RRLL listo: ${ghNovedad}`, indicator: "green" });
				}
				fetchAndRender(page);
			},
		});
	});

	$root.find(".action-clear-filters").off("click").on("click", function() {
		sstBandejaState.globalFilter = "";
		sstBandejaState.tableFilters = Object.keys(sstBandejaState.tableFilters || {}).reduce((acc, key) => {
			acc[key] = "";
			return acc;
		}, {});
		render(page);
	});
}

function openReprogramDialog(alertaName, page) {
	const d = new frappe.ui.Dialog({
		title: "Reprogramar alerta SST",
		fields: [
			{ fieldname: "reprogramar_fecha", fieldtype: "Date", label: "Nueva fecha", reqd: 1 },
			{ fieldname: "comentario", fieldtype: "Small Text", label: "Comentario" },
		],
		primary_action_label: "Guardar",
		primary_action(values) {
			frappe.call({
				method: "hubgh.hubgh.page.sst_bandeja.sst_bandeja.atender_alerta",
				args: {
					alerta_name: alertaName,
					reprogramar_fecha: values.reprogramar_fecha,
					comentario: values.comentario,
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
	const global = normalizeText(sstBandejaState.globalFilter);
	const local = normalizeText((sstBandejaState.tableFilters || {})[tableKey] || "");

	return rows.filter(row => {
		const blob = normalizeText(JSON.stringify(row || {}));
		return (!global || blob.includes(global)) && (!local || blob.includes(local));
	});
}

function tableCardHtml(tableKey, rows) {
	const cfg = TABLE_CONFIG[tableKey];
	if (!cfg) return "";
	const cols = cfg.columns || [];

	return `
		<div class="sst-card card-shadow">
			<div class="sst-card-header">
				<div>
					<div class="sst-card-title">${escapeHtml(cfg.title)}</div>
					<div class="sst-card-copy">Filtros visibles y acciones operativas en una sola capa.</div>
				</div>
				<div class="sst-card-count">${rows.length}</div>
			</div>
			<div class="sst-filter-row">
				<input data-table-key="${tableKey}" class="form-control sst-table-filter" placeholder="Filtrar bloque..." value="${escapeHtml((sstBandejaState.tableFilters || {})[tableKey] || "")}" />
			</div>
			<div class="sst-table-wrap">
				<table class="table table-sm sst-table">
					<thead>
						<tr>
							${cols.map(c => `<th>${escapeHtml(c.label)}</th>`).join("")}
							<th>Acciones</th>
						</tr>
					</thead>
					<tbody>
						${rows.length ? rows.map(r => rowHtml(r, cols, cfg.actions || [])).join("") : `<tr><td colspan="${cols.length + 1}" class="sst-empty"><div class="sst-empty-state"><strong>Sin datos para este bloque</strong><span>Probá limpiar filtros o revisar otra cola operativa.</span><button class="btn btn-xs btn-default action-clear-filters">Limpiar filtros</button></div></td></tr>`}
					</tbody>
				</table>
			</div>
		</div>
	`;
}

function getPrimaryAction(actions, row) {
	const actionList = actions || [];
	if (actionList.includes("atender")) return { type: "attend", label: "Cerrar", tone: "btn-success" };
	if (actionList.includes("escalar_rrll") && row.name && String(row.name).startsWith("NOV-") && !row.rrll_handoff_name) {
		return { type: "handoff", label: "Escalar RRLL", tone: "btn-warning" };
	}
	if (actionList.includes("reprogramar")) return { type: "reprogram", label: "Reprogramar", tone: "btn-primary" };
	if (actionList.includes("abrir_novedad") && (row.novedad || (row.name && String(row.name).startsWith("NOV-")))) {
		return { type: "open_novedad", label: "Gestionar", tone: "btn-primary" };
	}
	if (actionList.includes("abrir_alerta")) return { type: "open_alerta", label: "Ver alerta", tone: "btn-primary" };
	return null;
}

function rowHtml(row, cols, actions) {
	const cells = cols.map(c => `<td>${formatCell(c.key, row[c.key], row)}</td>`).join("");
	const primary = getPrimaryAction(actions, row);
	const secondary = [];

	if (actions.includes("abrir_alerta") && (!primary || primary.type !== "open_alerta")) {
		secondary.push(`<button class="btn btn-xs btn-link action-open-doc" data-doctype="SST Alerta" data-name="${escapeHtml(row.name || "")}">Ver alerta</button>`);
	}
	if (actions.includes("abrir_novedad") && row.novedad && (!primary || primary.type !== "open_novedad")) {
		secondary.push(`<button class="btn btn-xs btn-link action-open-doc" data-doctype="Novedad SST" data-name="${escapeHtml(row.novedad || "")}">Ver novedad</button>`);
	} else if (actions.includes("abrir_novedad") && row.name && String(row.name).startsWith("NOV-") && (!primary || primary.type !== "open_novedad")) {
		secondary.push(`<button class="btn btn-xs btn-link action-open-doc" data-doctype="Novedad SST" data-name="${escapeHtml(row.name || "")}">Abrir</button>`);
	}
	if (actions.includes("escalar_rrll") && row.name && String(row.name).startsWith("NOV-") && !row.rrll_handoff_name && (!primary || primary.type !== "handoff")) {
		secondary.push(`<button class="btn btn-xs btn-link action-handoff-rrll" data-name="${escapeHtml(row.name || "")}">Escalar RRLL</button>`);
	}
	if (actions.includes("escalar_rrll") && row.rrll_handoff_name) {
		secondary.push(`<button class="btn btn-xs btn-link action-open-doc" data-doctype="GH Novedad" data-name="${escapeHtml(row.rrll_handoff_name || "")}">Ver RRLL</button>`);
	}
	if (actions.includes("reprogramar") && (!primary || primary.type !== "reprogram")) {
		secondary.push(`<button class="btn btn-xs btn-link action-reprogram" data-name="${escapeHtml(row.name || "")}">Reprogramar</button>`);
	}
	if (actions.includes("atender") && (!primary || primary.type !== "attend")) {
		secondary.push(`<button class="btn btn-xs btn-link action-attend" data-name="${escapeHtml(row.name || "")}">Cerrar</button>`);
	}

	const primaryButton = primary
		? {
			attend: `<button class="btn btn-xs ${primary.tone} action-attend" data-name="${escapeHtml(row.name || "")}">${primary.label}</button>`,
			handoff: `<button class="btn btn-xs ${primary.tone} action-handoff-rrll" data-name="${escapeHtml(row.name || "")}">${primary.label}</button>`,
			reprogram: `<button class="btn btn-xs ${primary.tone} action-reprogram" data-name="${escapeHtml(row.name || "")}">${primary.label}</button>`,
			open_novedad: `<button class="btn btn-xs ${primary.tone} action-open-doc" data-doctype="Novedad SST" data-name="${escapeHtml(row.novedad || row.name || "")}">${primary.label}</button>`,
			open_alerta: `<button class="btn btn-xs ${primary.tone} action-open-doc" data-doctype="SST Alerta" data-name="${escapeHtml(row.name || "")}">${primary.label}</button>`,
		}[primary.type]
		: "-";

	return `<tr>${cells}<td class="sst-actions"><div class="sst-actions-primary">${primaryButton || "-"}</div><div class="sst-actions-secondary">${secondary.join(" ")}</div></td></tr>`;
}

function kpiCardHtml(label, value, tone) {
	return `
		<div class="col-md-3 col-lg-3">
			<div class="sst-kpi sst-kpi-${tone} card-shadow">
				<div class="sst-kpi-label">${escapeHtml(label)}</div>
				<div class="sst-kpi-value">${escapeHtml(value)}</div>
			</div>
		</div>
	`;
}

function formatCell(col, value, row) {
	if (value === null || value === undefined || value === "") return "-";
	if (col === "name") {
		const v = String(value);
		if (v.startsWith("SSTA-")) return `<a href="/app/sst-alerta/${encodeURIComponent(v)}">${escapeHtml(v)}</a>`;
		if (v.startsWith("NOV-")) return `<a href="/app/novedad-sst/${encodeURIComponent(v)}">${escapeHtml(v)}</a>`;
		return escapeHtml(v);
	}
	if (["alerta_label", "tipo_resumen"].includes(col)) {
		const secondary = rowSecondary(col, value, row);
		return `<div>${escapeHtml(String(value))}</div>${secondary}`;
	}
	if (["empleado_label", "punto_venta_label", "responsable_label", "rrll_handoff_label"].includes(col)) {
		const secondary = rowSecondary(col, value, row);
		return `<div>${escapeHtml(String(value))}</div>${secondary}`;
	}
	return escapeHtml(String(value));
}

function rowSecondary(col, value, row) {
	if (!row) return "";
	if (col === "alerta_label" && row.name) {
		const linkedNovedad = row.novedad ? ` · ${escapeHtml(String(row.novedad))}` : "";
		return `<div class="small text-muted">${escapeHtml(String(row.name))}${linkedNovedad}</div>`;
	}
	if (col === "tipo_resumen" && row.tipo_novedad) {
		const technicalId = row.name ? ` · ${escapeHtml(String(row.name))}` : "";
		return `<div class="small text-muted">${escapeHtml(String(row.tipo_novedad))}${technicalId}</div>`;
	}
	if (col === "empleado_label" && row.empleado) {
		return `<div class="small text-muted">${escapeHtml(String(row.empleado))}</div>`;
	}
	if (col === "punto_venta_label" && row.punto_venta) {
		return `<div class="small text-muted">${escapeHtml(String(row.punto_venta))}</div>`;
	}
	if (col === "responsable_label") {
		const technicalUser = row.asignado_a || row.owner;
		if (technicalUser) {
			return `<div class="small text-muted">${escapeHtml(String(technicalUser))}</div>`;
		}
	}
	if (col === "rrll_handoff_label" && row.rrll_handoff_name) {
		return `<div class="small text-muted">${escapeHtml(String(row.rrll_handoff_name))}</div>`;
	}
	return "";
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
	if (document.getElementById("sst-bandeja-styles")) return;
	const style = document.createElement("style");
	style.id = "sst-bandeja-styles";
	style.innerHTML = `
		.sst-shell { padding: 12px 8px 24px; }
		.card-shadow { box-shadow: 0 6px 16px rgba(16, 24, 40, 0.06); }
		.sst-toolbar {
			background: linear-gradient(135deg, #f8fbff 0%, #f5f8ff 100%);
			border: 1px solid #e3eaf7;
			border-radius: 12px;
			padding: 14px;
			margin-bottom: 14px;
		}
		.sst-toolbar-head { display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; flex-wrap: wrap; }
		.sst-toolbar-kickers { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 8px; }
		.sst-toolbar-kickers span { border-radius: 999px; padding: 4px 10px; background: #dbeafe; color: #1d4ed8; font-size: 11px; font-weight: 700; }
		.sst-toolbar-links { display: flex; gap: 8px; flex-wrap: wrap; }
		.sst-toolbar-title { font-size: 16px; font-weight: 700; color: #1f2a44; }
		.sst-toolbar-subtitle { font-size: 12px; color: #6b7280; margin: 2px 0 10px; }
		.sst-global-filter-wrap { max-width: 520px; }
		.sst-kpi-row { margin-bottom: 8px; }
		.sst-kpi {
			border-radius: 12px;
			padding: 12px 14px;
			border: 1px solid #e8edf6;
			background: #fff;
			margin-bottom: 10px;
		}
		.sst-kpi-label { color: #5b6475; font-size: 12px; }
		.sst-kpi-value { color: #1f2a44; font-size: 24px; font-weight: 700; line-height: 1.1; }
		.sst-kpi-danger .sst-kpi-value { color: #dc2626; }
		.sst-kpi-info .sst-kpi-value { color: #2563eb; }
		.sst-kpi-success .sst-kpi-value { color: #059669; }
		.sst-kpi-warning .sst-kpi-value { color: #d97706; }
		.sst-exam-summary {
			display: flex;
			justify-content: space-between;
			align-items: center;
			gap: 10px;
			padding: 12px;
			border: 1px solid #e8edf6;
			border-radius: 12px;
			margin-bottom: 12px;
			background: #fff;
		}
		.sst-grid-row { margin-bottom: 8px; }
		.sst-card {
			background: #fff;
			border: 1px solid #e8edf6;
			border-radius: 12px;
			padding: 10px;
			margin-bottom: 12px;
		}
		.sst-card-header {
			display: flex;
			justify-content: space-between;
			align-items: center;
			margin-bottom: 8px;
		}
		.sst-card-title { font-weight: 700; color: #1f2a44; }
		.sst-card-copy { color: #64748b; font-size: 11px; margin-top: 2px; }
		.sst-card-count {
			min-width: 28px;
			text-align: center;
			border-radius: 999px;
			padding: 2px 8px;
			background: #eef4ff;
			color: #3359a8;
			font-size: 12px;
			font-weight: 700;
		}
		.sst-filter-row { margin-bottom: 8px; }
		.sst-table-wrap {
			overflow-x: auto;
			overflow-y: auto;
			max-height: 420px;
		}
		.sst-table thead th {
			background: #f8fafc;
			border-bottom: 1px solid #e5e7eb;
			color: #334155;
			font-weight: 700;
			white-space: nowrap;
		}
		.sst-table tbody td { vertical-align: middle; }
		.sst-empty { text-align: center; color: #6b7280; }
		.sst-actions { min-width: 160px; }
		.sst-actions-primary { margin-bottom: 4px; }
		.sst-actions-secondary { display: flex; gap: 6px; flex-wrap: wrap; }
		.sst-actions-secondary .btn-link { padding: 0 2px; }
		.sst-empty-state { display: grid; gap: 6px; justify-items: center; padding: 8px 0; }
		@media (max-width: 768px) {
			.sst-shell { padding: 8px 0 18px; }
			.sst-exam-summary { align-items: flex-start; }
			.sst-table-wrap { max-height: none; }
		}
	`;
	document.head.appendChild(style);
}
