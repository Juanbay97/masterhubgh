/**
 * Workspace de Novedades — page controller.
 *
 * Pantalla única guiada para el operador de nómina:
 *   1. Selector / creador de Payroll Run.
 *   2. Drop zone multi-archivo (con botón fallback) y lista de Run Files.
 *   3. Tabla de revisión filtrable por jornada y tipo.
 *   4. Botón "Generar prenómina" → descarga el Excel single-sheet.
 *
 * Llama a los endpoints whitelisted de
 *   `hubgh.hubgh.payroll.service`.
 */

frappe.pages["payroll_workspace"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Workspace de Novedades",
		single_column: true,
	});

	const $body = $(page.body);
	$body.empty();
	const $shell = $('<div class="pwsp-shell"></div>').appendTo($body);

	const SOURCE_LABELS = {
		clonk: "CLONK",
		payflow: "Payflow",
		fincomercio: "Fincomercio",
		fongiga: "FONGIGA",
		libranza_davivienda: "Libranza Davivienda",
		libranza_compensar: "Libranza Compensar",
		libranza_comfenalco: "Libranza Comfenalco",
		manual_internal: "Manual",
		unknown: "(sin detectar)",
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
		current: null,        // run name
		summary: null,         // payload de get_run_summary
		novedades: [],
		filter: { jornada: "", tipo: "" },
		loading: false,
	};

	// ────────────────────────────────────────────────────────────────
	// Util
	// ────────────────────────────────────────────────────────────────

	const esc = (v) => frappe.utils.escape_html(v == null ? "" : String(v));
	const fmtMoney = (v) =>
		typeof v === "number"
			? v.toLocaleString("es-CO", { style: "currency", currency: "COP", maximumFractionDigits: 2 })
			: "-";
	const fmtNum = (v, dec = 2) => (typeof v === "number" ? v.toFixed(dec) : "-");

	const showError = (msg) => frappe.msgprint({ title: "Error", message: msg, indicator: "red" });
	const showInfo = (msg) => frappe.show_alert({ message: msg, indicator: "blue" }, 4);

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

	const loadNovedades = (run) =>
		apiCall("list_novedades", {
			run_name: run,
			limit: 500,
			jornada: state.filter.jornada,
			tipo: state.filter.tipo,
		}).then((r) => {
			state.novedades = (r && r.message) || [];
		});

	const refresh = async () => {
		state.loading = true;
		render();
		try {
			await loadRuns();
			if (state.current) {
				await loadSummary(state.current);
				await loadNovedades(state.current);
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
		const defYear = now.getFullYear();
		const defMonth = now.getMonth() + 1;
		const dlg = new frappe.ui.Dialog({
			title: "Nuevo Payroll Run",
			fields: [
				{ fieldtype: "Int", fieldname: "year", label: "Año", default: defYear, reqd: 1 },
				{
					fieldtype: "Select",
					fieldname: "month",
					label: "Mes",
					options: ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12"].join("\n"),
					default: String(defMonth),
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
				showInfo(`Run ${name} creado.`);
				await refresh();
			},
		});
		dlg.show();
	};

	const onSelectRun = (name) => {
		state.current = name;
		state.filter = { jornada: "", tipo: "" };
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
				console.error(e);
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
					if (resp && resp.message && resp.message.file_url) {
						resolve(resp.message.file_url);
					} else {
						reject(new Error("upload_file no devolvió file_url"));
					}
				},
				error: (xhr) => reject(new Error(xhr.responseText || "upload_file falló")),
			});
		});

	const onDeleteFile = async (fileName) => {
		const ok = await new Promise((res) =>
			frappe.confirm("¿Quitar este archivo del Run?", () => res(true), () => res(false))
		);
		if (!ok) return;
		await apiCall("delete_run_file", { run_file_name: fileName });
		await refresh();
	};

	const onChangeSource = async (fileName, newSource) => {
		await apiCall("update_detected_source", {
			run_file_name: fileName,
			detected_source: newSource,
		});
		showInfo(`Fuente actualizada a ${SOURCE_LABELS[newSource] || newSource}.`);
	};

	const onProcessRun = async () => {
		if (!state.current) return;
		const r = await apiCall("process_run", { run_name: state.current });
		const totals = (r && r.message && r.message.totals) || {};
		showInfo(
			`Procesado: ${totals.files || 0} archivos · ${totals.novedades || 0} novedades · ` +
				`${totals.errors || 0} errores · ${totals.skipped || 0} skipped.`
		);
		await refresh();
	};

	const onExportRun = async () => {
		if (!state.current) return;
		const r = await apiCall("export_run", { run_name: state.current });
		const fileUrl = r && r.message;
		if (fileUrl) {
			window.open(fileUrl, "_blank");
		}
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
			$shell.append(`<div class="pwsp-card pwsp-empty">Aún no hay Runs. Creá el primero arriba.</div>`);
		} else {
			$shell.append(`<div class="pwsp-card pwsp-empty">Seleccioná un Run para empezar.</div>`);
		}
	};

	const renderHero = () => {
		const run = state.summary && state.summary.run;
		const period = run ? `${run.period_year}-${String(run.period_month).padStart(2, "0")}` : "—";
		const status = run ? run.status : "—";
		$shell.append(`
			<div class="pwsp-hero">
				<div class="pwsp-hero-row">
					<div>
						<h2>Workspace de Novedades</h2>
						<p>Subí archivos del periodo y descargá la prenómina single-sheet.</p>
					</div>
					<div class="pwsp-hero-meta">
						<span class="pwsp-badge ${esc(status)}">${esc(STATUS_LABELS[status] || status)}</span>
						<span class="pwsp-badge">Periodo: ${esc(period)}</span>
						${run ? `<span class="pwsp-badge">${esc(run.name)}</span>` : ""}
					</div>
				</div>
			</div>
		`);
	};

	const renderRunPicker = () => {
		const $card = $('<div class="pwsp-card"></div>').appendTo($shell);
		$card.append(`<h3>Run de nómina</h3>`);
		const $row = $(`<div class="pwsp-actions"></div>`).appendTo($card);
		const $sel = $(`<select class="form-control" style="max-width: 360px"></select>`).appendTo($row);
		$sel.append(`<option value="">— elegí un Run —</option>`);
		state.runs.forEach((r) => {
			$sel.append(
				`<option value="${esc(r.name)}" ${
					r.name === state.current ? "selected" : ""
				}>${esc(r.name)} · ${esc(r.period_year)}-${String(r.period_month).padStart(2, "0")} · ${esc(
					STATUS_LABELS[r.status] || r.status
				)}</option>`
			);
		});
		$sel.on("change", (e) => onSelectRun($(e.currentTarget).val()));

		$row.append('<button class="btn btn-primary btn-sm">+ Nuevo Run</button>')
			.find("button:last")
			.on("click", onCreateRun);
		$row.append('<button class="btn btn-default btn-sm">Refrescar</button>')
			.find("button:last")
			.on("click", refresh);
	};

	const renderUploadCard = () => {
		const $card = $('<div class="pwsp-card"></div>').appendTo($shell);
		$card.append(`<h3>1. Cargar archivos del periodo</h3>`);
		$card.append(
			`<p class="muted">Arrastrá archivos CLONK, Payflow, Fincomercio, FONGIGA o libranzas. ` +
				`También podés tocar el botón para elegirlos del disco.</p>`
		);

		const $drop = $(`
			<label class="pwsp-dropzone" tabindex="0">
				<div><strong>Soltá archivos aquí</strong></div>
				<div class="muted">o tocá para abrir el selector — multi-archivo soportado</div>
				<input type="file" multiple accept=".xlsx,.xls,.csv">
			</label>
		`).appendTo($card);

		const $input = $drop.find("input");
		$input.on("change", (e) => {
			const files = Array.from(e.currentTarget.files || []);
			if (files.length) onUploadFiles(files);
			e.currentTarget.value = "";
		});
		$drop.on("dragover", (e) => {
			e.preventDefault();
			$drop.addClass("is-active");
		});
		$drop.on("dragleave drop", () => $drop.removeClass("is-active"));
		$drop.on("drop", (e) => {
			e.preventDefault();
			const files = Array.from(e.originalEvent.dataTransfer.files || []);
			if (files.length) onUploadFiles(files);
		});

		// Tabla de archivos del Run
		const files = (state.summary && state.summary.files) || [];
		if (!files.length) {
			$card.append(`<div class="pwsp-empty">Sin archivos cargados todavía.</div>`);
			return;
		}
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
		`).appendTo($card);
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
			const period =
				f.detected_period_year && f.detected_period_month
					? `${f.detected_period_year}-${String(f.detected_period_month).padStart(2, "0")}`
					: "—";
			const $tr = $(`
				<tr>
					<td><a href="${esc(f.file_url)}" target="_blank">${esc(f.file_name || f.file_url)}</a></td>
					<td><select class="form-control input-sm" data-src="${esc(f.name)}">${sourceOptions}</select></td>
					<td>${esc(period)}</td>
					<td><span class="pill ${esc(f.parse_status)}">${esc(f.parse_status)}</span></td>
					<td><button class="btn btn-link text-danger" data-del="${esc(f.name)}">Quitar</button></td>
				</tr>
			`).appendTo($tbody);
			$tr.find("select").on("change", (e) =>
				onChangeSource(f.name, $(e.currentTarget).val())
			);
			$tr.find("button[data-del]").on("click", () => onDeleteFile(f.name));
		});
	};

	const renderProcessCard = () => {
		const run = state.summary.run;
		if (!["draft", "ingesting", "parsed", "reviewing", "failed"].includes(run.status)) return;
		const $card = $('<div class="pwsp-card"></div>').appendTo($shell);
		$card.append(`<h3>2. Procesar archivos</h3>`);
		$card.append(
			`<p class="muted">Corre la detección de fuente, parseo, enrichment de empleados y ` +
				`cálculo de cada novedad. Es idempotente: podés re-correrlo después de corregir fuentes.</p>`
		);
		const $btn = $(`<button class="btn btn-primary">Procesar Run</button>`).appendTo($card);
		$btn.on("click", onProcessRun);
	};

	const renderReviewCard = () => {
		const counts = state.summary.counts || {};
		if (!counts.novedades) return;
		const $card = $('<div class="pwsp-card"></div>').appendTo($shell);
		$card.append(`<h3>3. Revisar novedades</h3>`);

		// KPIs
		const byStatus = counts.by_status || {};
		const $kpis = $(`<div class="pwsp-totals"></div>`).appendTo($card);
		$kpis.append(`<div class="pwsp-kpi"><div class="label">Total</div><div class="value">${counts.novedades}</div></div>`);
		Object.entries(byStatus).forEach(([k, v]) => {
			$kpis.append(
				`<div class="pwsp-kpi"><div class="label">${esc(k)}</div><div class="value">${esc(v)}</div></div>`
			);
		});

		// Filtros
		const $filters = $(`
			<div class="pwsp-actions" style="margin: 8px 0">
				<select class="form-control input-sm" id="pwsp-f-jornada" style="max-width: 200px">
					<option value="">Todas las jornadas</option>
					<option value="Tiempo Completo">Tiempo Completo</option>
					<option value="Tiempo Parcial">Tiempo Parcial</option>
				</select>
				<input type="text" class="form-control input-sm" id="pwsp-f-tipo" placeholder="Filtrar por tipo (ej. HD, INCAPACIDAD_*)" style="max-width: 320px">
				<button class="btn btn-sm btn-default" id="pwsp-f-apply">Aplicar</button>
			</div>
		`).appendTo($card);
		$filters.find("#pwsp-f-jornada").val(state.filter.jornada);
		$filters.find("#pwsp-f-tipo").val(state.filter.tipo);
		$filters.find("#pwsp-f-apply").on("click", () => {
			state.filter.jornada = $("#pwsp-f-jornada").val() || "";
			state.filter.tipo = ($("#pwsp-f-tipo").val() || "").trim();
			loadNovedades(state.current).then(render);
		});

		// Tabla
		if (!state.novedades.length) {
			$card.append(`<div class="pwsp-empty">No hay novedades con esos filtros.</div>`);
			return;
		}
		const $tbl = $(`
			<table class="pwsp-novedades">
				<thead><tr>
					<th>Empleado</th>
					<th>Doc</th>
					<th>Jornada</th>
					<th>Tipo</th>
					<th class="num">Cant.</th>
					<th class="num">Importe</th>
					<th>Estado</th>
					<th>Notas</th>
				</tr></thead>
				<tbody></tbody>
			</table>
		`).appendTo($card);
		const $tbody = $tbl.find("tbody");
		state.novedades.forEach((n) => {
			$tbody.append(`
				<tr>
					<td>${esc(n.empleado_label || n.empleado || "—")}</td>
					<td>${esc(n.documento_identidad)}</td>
					<td>${esc(n.tipo_jornada_snapshot || "—")}</td>
					<td>${esc(n.tipo_novedad)}</td>
					<td class="num">${esc(fmtNum(n.computed_quantity || n.cantidad, 2))}</td>
					<td class="num">${esc(fmtMoney(n.computed_amount))}</td>
					<td class="status-${esc(n.calc_status)}">${esc(n.calc_status)}</td>
					<td>${esc(n.calc_notes)}</td>
				</tr>
			`);
		});
		if (state.novedades.length === 500) {
			$card.append(`<div class="muted">Mostrando primeras 500 filas. Filtrá para acotar.</div>`);
		}
	};

	const renderExportCard = () => {
		const run = state.summary.run;
		if (!["parsed", "reviewing", "exported"].includes(run.status)) return;
		const $card = $('<div class="pwsp-card"></div>').appendTo($shell);
		$card.append(`<h3>4. Generar prenómina</h3>`);
		$card.append(
			`<p class="muted">Excel single-sheet, una fila por empleado, columnas por categoría agregada.</p>`
		);
		const $row = $(`<div class="pwsp-actions"></div>`).appendTo($card);
		$row.append('<button class="btn btn-success">Generar prenómina</button>')
			.find("button:last")
			.on("click", onExportRun);
		if (run.export_file) {
			$row.append(
				`<a class="btn btn-link" href="${esc(run.export_file)}" target="_blank">Última prenómina</a>`
			);
		}
	};

	// Boot
	refresh();
};
