/**
 * Workspace de Novedades — page controller.
 *
 * Sigue el patrón del resto de bandejas (`bandeja_contratacion`,
 * `bandeja_afiliaciones`, …) reusando las clases compartidas de
 * `public/js/bandejas_ui_base.js` para que rime con la plataforma:
 *   - hubgh-board-shell / hubgh-board-hero / hubgh-board-kickers / hubgh-meta-pill
 *   - hubgh-card / hubgh-table-shell / hubgh-empty
 *   - btn-dark para acciones primarias, btn-default para secundarias.
 *
 * Endpoints whitelisted en `hubgh.hubgh.payroll.service`:
 *   list_runs · get_run_summary · list_novedades ·
 *   create_run · attach_file · process_run · export_run ·
 *   update_detected_source · delete_run_file
 */

frappe.pages["payroll_workspace"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Workspace de Novedades",
		single_column: true,
	});

	(window.hubghBandejasUI || { injectBaseStyles() {} }).injectBaseStyles();

	const $body = $(page.body).empty();
	const $shell = $('<div class="hubgh-board-shell"></div>').appendTo($body);

	const SOURCE_LABELS = {
		clonk: "CLONK",
		payflow: "Payflow",
		fincomercio: "Fincomercio",
		fongiga: "FONGIGA",
		libranza_davivienda: "Libranza Davivienda",
		libranza_compensar: "Libranza Compensar",
		libranza_comfenalco: "Libranza Comfenalco",
		manual_internal: "Manual",
		unknown: "Sin detectar",
	};

	const STATUS_LABELS = {
		draft: "Borrador",
		ingesting: "Procesando",
		parsed: "Parseado",
		reviewing: "En revisión",
		exported: "Exportado",
		archived: "Archivado",
		failed: "Error",
	};

	const state = {
		runs: [],
		current: null,
		summary: null,
		consolidated: null,  // { employees: [...], totals: {...} }
		filter: { jornada: "", search: "" },
		loading: false,
	};

	// ────────────────────────────────────────────────────────────────
	// Helpers
	// ────────────────────────────────────────────────────────────────

	const esc = (window.hubghBandejasUI && window.hubghBandejasUI.esc) ||
		((v) => frappe.utils.escape_html(v == null ? "" : String(v)));
	const fmtMoney = (v) =>
		typeof v === "number" && v !== 0
			? v.toLocaleString("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 0 })
			: "—";
	const fmtNum = (v, dec = 2) =>
		typeof v === "number" && v !== 0 ? v.toFixed(dec) : "—";
	const fmtPeriod = (y, m) => (y && m ? `${y}-${String(m).padStart(2, "0")}` : "—");

	const showInfo = (msg) => frappe.show_alert({ message: msg, indicator: "blue" }, 4);
	const showSuccess = (msg) => frappe.show_alert({ message: msg, indicator: "green" }, 4);
	const showError = (msg) => frappe.msgprint({ title: "Error", message: msg, indicator: "red" });

	const apiCall = (method, args) =>
		frappe.call({ method: `hubgh.hubgh.payroll.service.${method}`, args, freeze: false });

	// ────────────────────────────────────────────────────────────────
	// Carga de datos
	// ────────────────────────────────────────────────────────────────

	const loadRuns = () =>
		apiCall("list_runs", { limit: 30 }).then((r) => {
			state.runs = (r && r.message) || [];
		});
	const loadSummary = (run) =>
		apiCall("get_run_summary", { run_name: run }).then((r) => {
			state.summary = (r && r.message) || null;
		});
	const loadConsolidated = (run) =>
		apiCall("get_run_consolidated", {
			run_name: run,
			jornada: state.filter.jornada,
			search: state.filter.search,
		}).then((r) => {
			state.consolidated = (r && r.message) || null;
		});

	const refresh = async () => {
		state.loading = true;
		render();
		try {
			await loadRuns();
			if (state.current) {
				await loadSummary(state.current);
				await loadConsolidated(state.current);
			}
		} finally {
			state.loading = false;
			render();
		}
	};

	// ────────────────────────────────────────────────────────────────
	// Acciones
	// ────────────────────────────────────────────────────────────────

	const onCreateRun = () => {
		const now = new Date();
		const dlg = new frappe.ui.Dialog({
			title: "Nuevo Run de nómina",
			fields: [
				{ fieldtype: "Int", fieldname: "year", label: "Año", default: now.getFullYear(), reqd: 1 },
				{
					fieldtype: "Select",
					fieldname: "month",
					label: "Mes",
					options: ["1","2","3","4","5","6","7","8","9","10","11","12"].join("\n"),
					default: String(now.getMonth() + 1),
					reqd: 1,
				},
			],
			primary_action_label: "Crear",
			primary_action: async (values) => {
				dlg.hide();
				const r = await apiCall("create_run", { period_year: values.year, period_month: values.month });
				const name = r && r.message;
				if (!name) return;
				state.current = name;
				showSuccess(`Run ${name} creado.`);
				await refresh();
			},
		});
		dlg.show();
	};

	const onSelectRun = (name) => {
		state.current = name;
		state.filter = { jornada: "", search: "" };
		refresh();
	};

	const onUploadFiles = async (fileList) => {
		if (!state.current) {
			showError("Primero seleccioná o creá un Run.");
			return;
		}
		const total = fileList.length;
		let done = 0;
		for (const file of fileList) {
			try {
				const fileUrl = await uploadOneFile(file);
				await apiCall("attach_file", {
					run_name: state.current,
					file_url: fileUrl,
					file_name: file.name,
				});
				done += 1;
				showInfo(`Subido ${done}/${total}: ${file.name}`);
			} catch (e) {
				showError(`Falló subida de ${file.name}: ${(e && e.message) || e}`);
			}
		}
		await refresh();
	};

	const uploadOneFile = (file) =>
		new Promise((resolve, reject) => {
			const fd = new FormData();
			fd.append("file", file, file.name);
			fd.append("is_private", "1");
			fd.append("doctype", "Payroll Run");
			fd.append("docname", state.current);
			fd.append("folder", "Home/Attachments");
			$.ajax({
				url: "/api/method/upload_file",
				type: "POST",
				data: fd,
				processData: false,
				contentType: false,
				headers: { "X-Frappe-CSRF-Token": frappe.csrf_token },
				success: (resp) => {
					if (resp && resp.message && resp.message.file_url) resolve(resp.message.file_url);
					else reject(new Error("upload_file sin file_url"));
				},
				error: (xhr) => reject(new Error(xhr.responseText || "upload_file falló")),
			});
		});

	const onDeleteFile = (fileName) =>
		new Promise((res) =>
			frappe.confirm("¿Quitar este archivo del Run?", () => res(true), () => res(false))
		).then(async (ok) => {
			if (!ok) return;
			await apiCall("delete_run_file", { run_file_name: fileName });
			showInfo("Archivo eliminado.");
			await refresh();
		});

	const onChangeSource = (fileName, newSource) =>
		apiCall("update_detected_source", { run_file_name: fileName, detected_source: newSource })
			.then(() => showInfo(`Fuente actualizada a ${SOURCE_LABELS[newSource] || newSource}.`));

	const onProcessRun = async () => {
		if (!state.current) return;
		const r = await apiCall("process_run", { run_name: state.current });
		const totals = (r && r.message && r.message.totals) || {};
		showSuccess(
			`Procesado: ${totals.files || 0} archivo(s) · ${totals.novedades || 0} novedades · ` +
				`${totals.errors || 0} error · ${totals.skipped || 0} skip.`
		);
		await refresh();
	};

	const onExportRun = async () => {
		if (!state.current) return;
		const r = await apiCall("export_run", { run_name: state.current });
		const fileUrl = r && r.message;
		if (fileUrl) window.open(fileUrl, "_blank");
		await refresh();
	};

	// ────────────────────────────────────────────────────────────────
	// Render
	// ────────────────────────────────────────────────────────────────

	const render = () => {
		$shell.empty();
		renderHero();
		renderRunPicker();
		if (state.current && state.summary) {
			renderUploadCard();
			renderProcessCard();
			renderReviewCard();
			renderExportCard();
		} else if (!state.runs.length) {
			$shell.append(`
				<div class="hubgh-empty">
					<span class="hubgh-empty-title">Aún no hay Runs.</span>
					<p class="hubgh-empty-copy">Creá el primero con el botón "+ Nuevo Run" arriba.</p>
				</div>
			`);
		} else {
			$shell.append(`
				<div class="hubgh-empty">
					<span class="hubgh-empty-title">Seleccioná un Run.</span>
					<p class="hubgh-empty-copy">Elegí uno del listado o creá uno nuevo para empezar.</p>
				</div>
			`);
		}
	};

	const renderHero = () => {
		const run = state.summary && state.summary.run;
		const period = run ? fmtPeriod(run.period_year, run.period_month) : "";
		const status = run ? run.status : "";

		const meta = [];
		if (status) {
			meta.push(
				`<span class="pwsp-state-pill ${esc(status)}">${esc(STATUS_LABELS[status] || status)}</span>`
			);
		}
		if (period) meta.push(`<span class="hubgh-meta-pill">Periodo ${esc(period)}</span>`);
		if (run) meta.push(`<span class="hubgh-meta-pill">${esc(run.name)}</span>`);

		$shell.append(`
			<div class="hubgh-board-hero">
				<div class="hubgh-board-hero-head">
					<div>
						<div class="hubgh-board-kickers">
							<span class="hubgh-board-kicker">Nómina</span>
							<span class="hubgh-board-kicker">Run + Adapters</span>
						</div>
						<h3 class="hubgh-board-title">Workspace de Novedades</h3>
						<p class="hubgh-board-copy">
							Subí los archivos del periodo (CLONK, Payflow, Fincomercio, FONGIGA o libranzas).
							El sistema detecta la fuente, parsea, calcula y entrega la prenómina single-sheet.
						</p>
					</div>
					<div class="hubgh-board-meta">${meta.join("") || ""}</div>
				</div>
			</div>
		`);
	};

	const renderRunPicker = () => {
		const $card = $('<div class="hubgh-card"></div>').appendTo($shell);
		$card.append(`
			<div class="hubgh-section-head">
				<div>
					<h4 class="hubgh-section-title">Run de nómina</h4>
					<p class="hubgh-section-copy">Elegí el Run sobre el que estás trabajando o creá uno nuevo.</p>
				</div>
			</div>
		`);
		const $row = $('<div class="hubgh-board-toolbar"></div>').appendTo($card);
		const $sel = $('<select class="form-control filter-search"></select>').appendTo($row);
		$sel.append(`<option value="">— elegí un Run —</option>`);
		state.runs.forEach((r) => {
			const lbl = `${r.name} · ${fmtPeriod(r.period_year, r.period_month)} · ${
				STATUS_LABELS[r.status] || r.status
			}`;
			$sel.append(
				`<option value="${esc(r.name)}" ${
					r.name === state.current ? "selected" : ""
				}>${esc(lbl)}</option>`
			);
		});
		$sel.on("change", (e) => onSelectRun($(e.currentTarget).val()));

		$row.append('<button class="btn btn-sm btn-dark">+ Nuevo Run</button>')
			.find("button:last").on("click", onCreateRun);
		$row.append('<button class="btn btn-sm btn-default">Refrescar</button>')
			.find("button:last").on("click", refresh);
	};

	const renderUploadCard = () => {
		const $card = $('<div class="hubgh-card"></div>').appendTo($shell);
		$card.append(`
			<div class="hubgh-section-head">
				<div>
					<h4 class="hubgh-section-title">Cargar archivos del periodo</h4>
					<p class="hubgh-section-copy">
						Drag-and-drop o click para abrir el selector. Formatos: .xlsx · .xls · .csv. Multi-archivo.
					</p>
				</div>
			</div>
		`);

		const $drop = $(`
			<label class="pwsp-dropzone" tabindex="0">
				<strong>Soltá archivos aquí</strong>
				<span class="muted">o tocá para abrir el selector</span>
				<input type="file" multiple accept=".xlsx,.xls,.csv">
			</label>
		`).appendTo($card);
		const $input = $drop.find("input");
		$input.on("change", (e) => {
			const files = Array.from(e.currentTarget.files || []);
			if (files.length) onUploadFiles(files);
			e.currentTarget.value = "";
		});
		$drop.on("dragover", (e) => { e.preventDefault(); $drop.addClass("is-active"); });
		$drop.on("dragleave drop", () => $drop.removeClass("is-active"));
		$drop.on("drop", (e) => {
			e.preventDefault();
			const files = Array.from(e.originalEvent.dataTransfer.files || []);
			if (files.length) onUploadFiles(files);
		});

		const files = (state.summary && state.summary.files) || [];
		if (!files.length) {
			$card.append(`
				<div class="hubgh-empty">
					<span class="hubgh-empty-title">Sin archivos cargados.</span>
					<p class="hubgh-empty-copy">Arrastrá uno o más archivos del periodo arriba.</p>
				</div>
			`);
			return;
		}
		const $shellTbl = $('<div class="hubgh-table-shell hubgh-table-wrap"></div>').appendTo($card);
		const $table = $(`
			<table class="pwsp-files">
				<thead><tr>
					<th>Archivo</th>
					<th>Fuente detectada</th>
					<th>Periodo</th>
					<th>Parse</th>
					<th></th>
				</tr></thead>
				<tbody></tbody>
			</table>
		`).appendTo($shellTbl);
		const $tbody = $table.find("tbody");
		const validSources = (state.summary && state.summary.valid_sources) || Object.keys(SOURCE_LABELS);
		files.forEach((f) => {
			const sourceOptions = validSources
				.map(
					(s) =>
						`<option value="${esc(s)}" ${s === f.detected_source ? "selected" : ""}>${esc(
							SOURCE_LABELS[s] || s
						)}</option>`
				)
				.join("");
			const period = fmtPeriod(f.detected_period_year, f.detected_period_month);
			const $tr = $(`
				<tr>
					<td>
						<div class="hubgh-cell-stack">
							<a class="hubgh-cell-main" href="${esc(f.file_url)}" target="_blank">${esc(
								f.file_name || f.file_url
							)}</a>
						</div>
					</td>
					<td><select class="form-control input-sm" data-src="${esc(f.name)}">${sourceOptions}</select></td>
					<td>${esc(period)}</td>
					<td><span class="pill ${esc(f.parse_status)}">${esc(f.parse_status)}</span></td>
					<td><button class="btn btn-link btn-xs text-danger" data-del="${esc(f.name)}">Quitar</button></td>
				</tr>
			`).appendTo($tbody);
			$tr.find("select").on("change", (e) => onChangeSource(f.name, $(e.currentTarget).val()));
			$tr.find("button[data-del]").on("click", () => onDeleteFile(f.name));
		});
	};

	const renderProcessCard = () => {
		const run = state.summary.run;
		if (!["draft", "ingesting", "parsed", "reviewing", "failed"].includes(run.status)) return;
		const $card = $('<div class="hubgh-card"></div>').appendTo($shell);
		$card.append(`
			<div class="hubgh-section-head">
				<div>
					<h4 class="hubgh-section-title">Procesar archivos</h4>
					<p class="hubgh-section-copy">
						Detecta la fuente, parsea las novedades, resuelve empleado/contrato/jornada y calcula cada línea.
						Idempotente: podés re-correr después de corregir fuentes.
					</p>
				</div>
			</div>
		`);
		const $row = $('<div class="hubgh-board-toolbar"></div>').appendTo($card);
		$row.append('<button class="btn btn-sm btn-dark">Procesar Run</button>').find("button").on("click", onProcessRun);
	};

	const renderReviewCard = () => {
		const consolidated = state.consolidated;
		if (!consolidated || !consolidated.employees) return;
		const employees = consolidated.employees;
		const totals = consolidated.totals || {};

		const $card = $('<div class="hubgh-card"></div>').appendTo($shell);
		$card.append(`
			<div class="hubgh-section-head">
				<div>
					<h4 class="hubgh-section-title">Revisar consolidado por empleado</h4>
					<p class="hubgh-section-copy">
						Una fila por empleado con el resumen de todas sus novedades del periodo.
						Filtrá por jornada o por nombre / cédula / cargo / sucursal antes de exportar.
					</p>
				</div>
			</div>
		`);

		// KPIs consolidados.
		const $kpis = $('<div class="pwsp-kpis"></div>').appendTo($card);
		$kpis.append(`
			<div class="pwsp-kpi"><div class="label">Empleados</div>
				<div class="value">${esc(totals.empleados || 0)}</div></div>
			<div class="pwsp-kpi is-computed"><div class="label">Devengado</div>
				<div class="value">${esc(fmtMoney(totals.total_devengado))}</div></div>
			<div class="pwsp-kpi is-error"><div class="label">Descuentos</div>
				<div class="value">${esc(fmtMoney(totals.total_descontado))}</div></div>
			<div class="pwsp-kpi"><div class="label">Aux. Transporte</div>
				<div class="value">${esc(fmtMoney(totals.total_aux_transporte))}</div></div>
			<div class="pwsp-kpi"><div class="label">Neto</div>
				<div class="value">${esc(fmtMoney(totals.total_neto))}</div></div>
		`);
		if (totals.empleados_partial) {
			$kpis.append(`
				<div class="pwsp-kpi is-skipped">
					<div class="label">Con datos parciales</div>
					<div class="value">${esc(totals.empleados_partial)}</div>
				</div>
			`);
		}

		const $filters = $(`
			<div class="pwsp-filters">
				<select class="form-control input-sm" id="pwsp-f-jornada">
					<option value="">Todas las jornadas</option>
					<option value="Tiempo Completo">Tiempo Completo</option>
					<option value="Tiempo Parcial">Tiempo Parcial</option>
				</select>
				<input type="text" class="form-control input-sm" id="pwsp-f-search"
					placeholder="Buscar por nombre, cédula, cargo o sucursal">
				<button class="btn btn-sm btn-default" id="pwsp-f-apply">Aplicar</button>
			</div>
		`).appendTo($card);
		$filters.find("#pwsp-f-jornada").val(state.filter.jornada);
		$filters.find("#pwsp-f-search").val(state.filter.search);
		$filters.find("#pwsp-f-apply").on("click", () => {
			state.filter.jornada = $("#pwsp-f-jornada").val() || "";
			state.filter.search = ($("#pwsp-f-search").val() || "").trim();
			loadConsolidated(state.current).then(render);
		});

		if (!employees.length) {
			$card.append(`
				<div class="hubgh-empty">
					<span class="hubgh-empty-title">Sin empleados con esos filtros.</span>
					<p class="hubgh-empty-copy">Probá otros valores o limpiá los filtros.</p>
				</div>
			`);
			return;
		}

		const $shellTbl = $('<div class="hubgh-table-shell hubgh-table-wrap"></div>').appendTo($card);
		const $tbl = $(`
			<table class="pwsp-novedades">
				<thead><tr>
					<th>Empleado</th>
					<th>Cédula</th>
					<th>Jornada</th>
					<th>Cargo</th>
					<th>Sucursal</th>
					<th class="num">Salario</th>
					<th class="num">Devengado</th>
					<th class="num">Descuentos</th>
					<th class="num">Aux.&nbsp;Trans.</th>
					<th class="num">Neto</th>
					<th>Detalle</th>
				</tr></thead>
				<tbody></tbody>
			</table>
		`).appendTo($shellTbl);
		const $tbody = $tbl.find("tbody");
		employees.forEach((e) => {
			const partialBadge = e.has_partial
				? `<span class="pwsp-state-pill partial compact" title="Algunas novedades quedaron sin importe (falta empleado/contrato/cargo en DB)">parcial</span>`
				: "";
			const breakdown = _summarizeEmployee(e);
			$tbody.append(`
				<tr>
					<td>
						<div class="hubgh-cell-stack">
							<span class="hubgh-cell-main">${esc(e.nombre || "—")}</span>
							${partialBadge ? `<span class="hubgh-cell-sub">${partialBadge}</span>` : ""}
						</div>
					</td>
					<td><span class="hubgh-cell-sub">${esc(e.cedula)}</span></td>
					<td>${esc(e.jornada || "—")}</td>
					<td><span class="hubgh-cell-sub">${esc(e.cargo || "—")}</span></td>
					<td><span class="hubgh-cell-sub">${esc(e.sucursal || "—")}</span></td>
					<td class="num">${esc(fmtMoney(e.salario))}</td>
					<td class="num status-computed">${esc(fmtMoney(e.total_devengado))}</td>
					<td class="num status-error">${esc(fmtMoney(e.total_descontado))}</td>
					<td class="num">${esc(fmtMoney(e.auxilio_transporte))}</td>
					<td class="num"><strong>${esc(fmtMoney(e.neto))}</strong></td>
					<td><span class="hubgh-cell-sub">${esc(breakdown)}</span></td>
				</tr>
			`);
		});
	};

	const _summarizeEmployee = (e) => {
		const parts = [];
		const horas = Object.entries(e.horas || {})
			.filter(([_, v]) => v.qty > 0)
			.map(([k, v]) => `${k} ${v.qty.toFixed(1)}h`)
			.join(" · ");
		if (horas) parts.push(horas);
		const dias = Object.entries(e.dias || {})
			.filter(([_, q]) => q > 0)
			.map(([k, q]) => `${k.replaceAll("_", " ").toLowerCase()} ${q}d`)
			.join(" · ");
		if (dias) parts.push(dias);
		const desc = Object.keys(e.descuentos || {}).length;
		if (desc) parts.push(`${desc} descuento(s)`);
		return parts.join(" · ") || "—";
	};

	const renderExportCard = () => {
		const run = state.summary.run;
		if (!["parsed", "reviewing", "exported"].includes(run.status)) return;
		const $card = $('<div class="hubgh-card"></div>').appendTo($shell);
		$card.append(`
			<div class="hubgh-section-head">
				<div>
					<h4 class="hubgh-section-title">Generar prenómina</h4>
					<p class="hubgh-section-copy">
						Excel single-sheet, una fila por empleado, columnas por categoría agregada.
					</p>
				</div>
			</div>
		`);
		const $row = $('<div class="hubgh-board-toolbar"></div>').appendTo($card);
		$row.append('<button class="btn btn-sm btn-dark">Generar prenómina</button>')
			.find("button").on("click", onExportRun);
		if (run.export_file) {
			$row.append(
				`<a class="btn btn-sm btn-default" href="${esc(run.export_file)}" target="_blank">Última prenómina</a>`
			);
		}
	};

	// Boot
	refresh();
};
