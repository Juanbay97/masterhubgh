// Copyright (c) 2026, Antigravity and contributors
// For license information, please see license.txt

/**
 * sst_seguimiento_examenes — Bandeja SST de seguimiento de citas activas.
 *
 * Permite listar, agendar, anotar observaciones, cambiar estado y exportar
 * citas de examen médico que aún no tienen concepto_resultado registrado.
 *
 * Roles con acceso: System Manager, HR SST, HR Selection, Gestión Humana.
 */

frappe.pages["sst_seguimiento_examenes"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Bandeja SST – Seguimiento Exámenes",
		single_column: true,
	});

	// ─── Estado interno ────────────────────────────────────────────────────
	const state = {
		rows: [],
		total: 0,
		limit: 50,
		offset: 0,
		loading: false,
	};

	// Debounce para campos de texto (300 ms)
	let _debounceTimer = null;
	function debounce(fn, delay) {
		clearTimeout(_debounceTimer);
		_debounceTimer = setTimeout(fn, delay);
	}

	// ─── Helpers ───────────────────────────────────────────────────────────
	const esc = (v) => frappe.utils.escape_html(v == null ? "" : String(v));

	function today() {
		return frappe.datetime.get_today();
	}

	function defaultFechaDesde() {
		return frappe.datetime.add_days(today(), -7);
	}

	function defaultFechaHasta() {
		return frappe.datetime.add_days(today(), 30);
	}

	function estadoBadge(estado) {
		const e = (estado || "").toLowerCase();
		if (e === "agendada") return `<span class="indicator-pill green">${esc(estado)}</span>`;
		if (e === "pendiente agendamiento") return `<span class="indicator-pill orange">${esc(estado)}</span>`;
		if (e === "aplazada") return `<span class="indicator-pill yellow">${esc(estado)}</span>`;
		if (e === "no asistió") return `<span class="indicator-pill red">${esc(estado)}</span>`;
		return `<span class="indicator-pill gray">${esc(estado)}</span>`;
	}

	// ─── T12: Layout base + filtros ───────────────────────────────────────
	// Inyectar estilos de bandeja
	if (!document.getElementById("sst-seguimiento-styles")) {
		const style = document.createElement("style");
		style.id = "sst-seguimiento-styles";
		style.textContent = `
			.sst-seg-toolbar { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 12px; align-items: flex-end; }
			.sst-seg-toolbar .form-group { margin-bottom: 0; }
			.sst-seg-toolbar label { font-size: 11px; font-weight: 600; color: #6b7280; }
			.sst-seg-toolbar input, .sst-seg-toolbar select { font-size: 12px; }
			.sst-seg-table-wrap { overflow-x: auto; }
			.sst-seg-table { width: 100%; border-collapse: collapse; font-size: 12px; }
			.sst-seg-table th { background: #1d4ed8; color: #fff; padding: 8px 10px; text-align: left; white-space: nowrap; }
			.sst-seg-table td { padding: 7px 10px; border-bottom: 1px solid #e5e7eb; vertical-align: middle; }
			.sst-seg-table tr:hover td { background: #f9fafb; }
			.row-datos-faltantes { border-left: 3px solid #dc3545 !important; background: #fff5f5 !important; }
			.badge-manual-sin-agendar { background: #dc3545; color: #fff; font-size: 10px; padding: 2px 6px; border-radius: 10px; margin-left: 6px; }
			.sst-seg-empty { text-align: center; padding: 32px; color: #6b7280; }
			.sst-seg-pagination { display: flex; align-items: center; gap: 12px; margin-top: 12px; font-size: 13px; }
			.sst-seg-spinner { text-align: center; padding: 24px; color: #6b7280; }
			.obs-preview { color: #6b7280; font-size: 11px; font-style: italic; max-width: 160px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
		`;
		document.head.appendChild(style);
	}

	const $body = $(page.body);
	$body.html(`
		<div style="padding: 12px 16px;">
			<!-- Filtros -->
			<div class="sst-seg-toolbar" id="sst-seg-toolbar">
				<div class="form-group">
					<label>Desde</label>
					<input type="date" id="f-fecha-desde" class="form-control" value="${defaultFechaDesde()}" style="width:130px" />
				</div>
				<div class="form-group">
					<label>Hasta</label>
					<input type="date" id="f-fecha-hasta" class="form-control" value="${defaultFechaHasta()}" style="width:130px" />
				</div>
				<div class="form-group">
					<label>Estado</label>
					<select id="f-estado" class="form-control" style="width:160px">
						<option value="">Todos</option>
						<option value='["Pendiente Agendamiento"]'>Pendiente Agendamiento</option>
						<option value='["Agendada"]'>Agendada</option>
						<option value='["Aplazada"]'>Aplazada</option>
						<option value='["No Asistió"]'>No Asistió</option>
					</select>
				</div>
				<div class="form-group">
					<label>Modo</label>
					<select id="f-modo" class="form-control" style="width:140px">
						<option value="">Ambos</option>
						<option value="Manual">Manual</option>
						<option value="Autogestionado">Autogestionado</option>
					</select>
				</div>
				<div class="form-group">
					<label>Ciudad</label>
					<input type="text" id="f-ciudad" class="form-control" placeholder="Ej: Bogotá" style="width:120px" />
				</div>
				<div class="form-group">
					<label>Tipo cargo</label>
					<select id="f-tipo-cargo" class="form-control" style="width:130px">
						<option value="">Todos</option>
						<option value="Operativo">Operativo</option>
						<option value="Administrativo">Administrativo</option>
					</select>
				</div>
				<div class="form-group">
					<label>Sede</label>
					<input type="text" id="f-sede" class="form-control" placeholder="Sede" style="width:110px" />
				</div>
				<div class="form-group">
					<label>Buscar</label>
					<input type="text" id="f-search" class="form-control" placeholder="Nombre, cédula..." style="width:150px" />
				</div>
				<div class="form-group" style="padding-top:20px">
					<label>
						<input type="checkbox" id="f-solo-manuales" />
						Solo manuales sin datos
					</label>
				</div>
				<div style="margin-left:auto; display:flex; gap:8px; padding-top:16px;">
					<button class="btn btn-sm btn-primary" id="btn-actualizar">Actualizar</button>
					<button class="btn btn-sm btn-default" id="btn-exportar">Exportar Excel</button>
				</div>
			</div>

			<!-- Spinner -->
			<div id="sst-seg-spinner" class="sst-seg-spinner" style="display:none;">
				<span class="fa fa-spinner fa-spin"></span> Cargando...
			</div>

			<!-- Tabla -->
			<div class="sst-seg-table-wrap" id="sst-seg-table-wrap"></div>

			<!-- Paginación -->
			<div class="sst-seg-pagination" id="sst-seg-pagination" style="display:none;">
				<button class="btn btn-xs btn-default" id="btn-prev">&#9664; Anterior</button>
				<span id="lbl-pagina">Página 1 de 1</span>
				<button class="btn btn-xs btn-default" id="btn-next">Siguiente &#9654;</button>
			</div>
		</div>
	`);

	// ─── Leer filtros actuales ─────────────────────────────────────────────
	function getFilters() {
		const soloManuales = $("#f-solo-manuales").prop("checked");
		const estadoVal = $("#f-estado").val();
		return {
			fecha_desde: soloManuales ? undefined : ($("#f-fecha-desde").val() || undefined),
			fecha_hasta: soloManuales ? undefined : ($("#f-fecha-hasta").val() || undefined),
			estados: estadoVal ? JSON.parse(estadoVal) : undefined,
			modo: $("#f-modo").val() || undefined,
			ciudad: $("#f-ciudad").val().trim() || undefined,
			tipo_cargo: $("#f-tipo-cargo").val() || undefined,
			sede: $("#f-sede").val().trim() || undefined,
			search: $("#f-search").val().trim() || undefined,
			solo_manuales_sin_datos: soloManuales,
		};
	}

	// ─── T12: fetchRows con spinner ───────────────────────────────────────
	function fetchRows() {
		if (state.loading) return;
		state.loading = true;
		$("#sst-seg-spinner").show();
		$("#sst-seg-table-wrap").html("");
		$("#sst-seg-pagination").hide();

		frappe.call({
			method: "hubgh.hubgh.page.sst_seguimiento_examenes.sst_seguimiento_examenes.list_seguimiento_examenes",
			args: {
				filters: getFilters(),
				limit: state.limit,
				offset: state.offset,
			},
			callback(r) {
				state.loading = false;
				$("#sst-seg-spinner").hide();
				if (r && r.message) {
					state.rows = r.message.rows || [];
					state.total = r.message.total || 0;
					renderTable(state.rows);
					renderPagination();
				}
			},
			error() {
				state.loading = false;
				$("#sst-seg-spinner").hide();
				frappe.msgprint(__("Error al cargar la bandeja. Intentá de nuevo."));
			},
		});
	}

	// ─── T13: Render tabla + paginación + visual hint ─────────────────────
	function renderTable(rows) {
		if (!rows || rows.length === 0) {
			$("#sst-seg-table-wrap").html(
				`<div class="sst-seg-empty">
					<strong>Sin citas activas</strong><br>
					<span>No hay citas de examen médico con los filtros seleccionados.</span>
				</div>`
			);
			return;
		}

		const rowsHtml = rows.map((r) => {
			const clsDatos = r.datos_faltantes ? ' class="row-datos-faltantes"' : "";
			const badgeDatos = r.datos_faltantes
				? `<span class="badge-manual-sin-agendar">Manual sin agendar</span>`
				: "";
			return `
				<tr${clsDatos}>
					<td>${estadoBadge(r.estado)}${badgeDatos}</td>
					<td>${esc(r.nombre_completo)}</td>
					<td>${esc(r.numero_documento)}</td>
					<td>${esc(r.celular)}</td>
					<td>${esc(r.ciudad)}</td>
					<td>${esc(r.cargo_nombre || r.cargo_al_enviar)}</td>
					<td>${esc(r.ips)}</td>
					<td>${esc(r.fecha_cita || "—")}</td>
					<td>${esc(r.hora_cita || "—")}</td>
					<td>${esc(r.modo)}</td>
					<td class="obs-preview" title="${esc(r.observaciones_sst)}">${esc(r.observaciones_preview)}</td>
					<td>
						<div style="display:flex;gap:4px;flex-wrap:wrap;">
							<button class="btn btn-xs btn-default btn-agendar" data-cita="${esc(r.name)}"
								data-fecha="${esc(r.fecha_cita || "")}" data-hora="${esc(r.hora_cita || "")}"
								data-sede="${esc(r.sede_seleccionada || "")}" data-nombre="${esc(r.nombre_completo)}">
								Agendar
							</button>
							<button class="btn btn-xs btn-default btn-outcome" data-cita="${esc(r.name)}"
								data-nombre="${esc(r.nombre_completo)}" data-fecha="${esc(r.fecha_cita || "")}">
								Estado
							</button>
							<button class="btn btn-xs btn-default btn-obs" data-cita="${esc(r.name)}"
								data-obs="${esc(r.observaciones_sst || "")}">
								Obs.
							</button>
							<button class="btn btn-xs btn-danger btn-cancelar" data-cita="${esc(r.name)}"
								data-nombre="${esc(r.nombre_completo)}" data-fecha="${esc(r.fecha_cita || "—")}">
								Cancelar
							</button>
						</div>
					</td>
				</tr>
			`;
		}).join("");

		const tableHtml = `
			<table class="sst-seg-table">
				<thead>
					<tr>
						<th>Estado</th>
						<th>Nombre</th>
						<th>Cédula</th>
						<th>Celular</th>
						<th>Ciudad</th>
						<th>Cargo</th>
						<th>IPS</th>
						<th>Fecha</th>
						<th>Hora</th>
						<th>Modo</th>
						<th>Observaciones</th>
						<th>Acciones</th>
					</tr>
				</thead>
				<tbody>${rowsHtml}</tbody>
			</table>
		`;
		$("#sst-seg-table-wrap").html(tableHtml);
	}

	function renderPagination() {
		const totalPages = Math.max(1, Math.ceil(state.total / state.limit));
		const currentPage = Math.floor(state.offset / state.limit) + 1;
		$("#lbl-pagina").text(`Página ${currentPage} de ${totalPages} (${state.total} citas)`);
		$("#btn-prev").prop("disabled", state.offset === 0);
		$("#btn-next").prop("disabled", state.offset + state.limit >= state.total);
		$("#sst-seg-pagination").show();
	}

	// ─── T14: Dialog "Editar agendamiento" + confirmación fecha pasada ────
	function openAgendarDialog(citaName, nombre, fechaActual, horaActual, sedeActual) {
		const d = new frappe.ui.Dialog({
			title: `Editar agendamiento — ${nombre}`,
			fields: [
				{
					fieldname: "fecha_cita",
					fieldtype: "Date",
					label: "Fecha cita",
					reqd: 1,
					default: fechaActual || undefined,
				},
				{
					fieldname: "hora_cita",
					fieldtype: "Time",
					label: "Hora cita",
					reqd: 1,
					default: horaActual || undefined,
				},
				{
					fieldname: "sede_seleccionada",
					fieldtype: "Autocomplete",
					label: "Sede",
					default: sedeActual || undefined,
					options: [],
					description: "Cargando sedes...",
				},
				{
					fieldname: "confirmar_pasado",
					fieldtype: "Check",
					label: "Confirmo que la fecha es pasada (fecha anterior a hoy)",
					hidden: 1,
				},
			],
			primary_action_label: "Guardar",
			primary_action(values) {
				const fechaSel = values.fecha_cita;
				const fechaHoy = frappe.datetime.get_today();
				const esPasada = fechaSel < fechaHoy;

				if (esPasada && !values.confirmar_pasado) {
					// Mostrar checkbox de confirmación
					d.set_df_property("confirmar_pasado", "hidden", 0);
					frappe.msgprint(__("La fecha es anterior a hoy. Marcá el checkbox de confirmación y guardá de nuevo."));
					return;
				}

				frappe.call({
					method: "hubgh.hubgh.page.sst_seguimiento_examenes.sst_seguimiento_examenes.set_cita_schedule",
					args: {
						cita_name: citaName,
						fecha: fechaSel,
						hora: values.hora_cita,
						sede: values.sede_seleccionada || null,
						force_pasado: esPasada && !!values.confirmar_pasado,
					},
					callback(r) {
						if (r && r.message && r.message.ok) {
							d.hide();
							frappe.show_alert({ message: __("Agendamiento actualizado."), indicator: "green" });
							resetAndFetch();
						}
					},
					error() {
						// El mensaje de error viene desde el servidor vía frappe.throw
					},
				});
			},
		});
		d.show();
		// Cargar sedes válidas para esta cita y refrescar el Autocomplete
		frappe.call({
			method: "hubgh.hubgh.page.sst_seguimiento_examenes.sst_seguimiento_examenes.list_sedes_for_cita",
			args: { cita_name: citaName },
			callback(r) {
				const data = (r && r.message) || { ciudad: "", sedes: [] };
				const opts = (data.sedes || []).map(s => s.nombre_sede).filter(Boolean);
				const help = opts.length
					? `Sedes activas en ${data.ciudad}: ${opts.length}.`
					: `Sin sedes activas para "${data.ciudad || "(sin ciudad)"}".`;
				const fld = d.fields_dict.sede_seleccionada;
				if (fld) {
					fld.df.options = opts;
					fld.df.description = help;
					if (fld.refresh) fld.refresh();
					// Si el Autocomplete ya está montado, actualizar su lista
					if (fld.awesomplete) {
						fld.awesomplete.list = opts;
					}
				}
			},
		});
	}

	// ─── T15: Dialog "Cambiar estado" + acción "Cancelar cita" ───────────
	function openOutcomeDialog(citaName, nombre, fecha) {
		const d = new frappe.ui.Dialog({
			title: `Cambiar estado — ${nombre}`,
			fields: [
				{
					fieldname: "estado",
					fieldtype: "Select",
					label: "Estado",
					reqd: 1,
					options: "\nRealizada\nAplazada\nNo Asistió",
				},
				{
					fieldname: "concepto",
					fieldtype: "Select",
					label: "Concepto médico",
					options: "\nFavorable\nDesfavorable\nAplazado",
					depends_on: "eval:doc.estado=='Realizada'",
				},
				{
					fieldname: "motivo",
					fieldtype: "Small Text",
					label: "Motivo",
					depends_on: "eval:['Aplazada','No Asistió'].includes(doc.estado)",
				},
				{
					fieldname: "instrucciones",
					fieldtype: "Small Text",
					label: "Instrucciones de reagendamiento",
					depends_on: "eval:doc.estado=='Aplazada'",
				},
			],
			primary_action_label: "Confirmar",
			primary_action(values) {
				if (values.estado === "Realizada" && !values.concepto) {
					frappe.msgprint(__("Seleccioná el concepto médico para estado Realizada."));
					return;
				}
				if (values.estado === "Aplazada" && !(values.motivo || "").trim()) {
					frappe.msgprint(__("Ingresá el motivo de aplazamiento."));
					return;
				}

				frappe.call({
					method: "hubgh.hubgh.page.sst_seguimiento_examenes.sst_seguimiento_examenes.set_cita_outcome",
					args: {
						cita_name: citaName,
						estado: values.estado,
						concepto: values.concepto || null,
						motivo: values.motivo || null,
						instrucciones: values.instrucciones || null,
					},
					callback(r) {
						if (r && r.message && r.message.ok) {
							d.hide();
							frappe.show_alert({
								message: __("Estado actualizado a {0}.", [values.estado]),
								indicator: "green",
							});
							resetAndFetch();
						}
					},
				});
			},
		});
		d.show();
	}

	function cancelarCita(citaName, nombre, fecha) {
		// T15: Confirmación explícita con nombre + fecha antes de cancelar
		frappe.confirm(
			__("¿Cancelar la cita de {0} del {1}? Esta acción no se puede deshacer.", [nombre, fecha || "—"]),
			() => {
				// Usuario confirmó — pedir motivo
				const dm = new frappe.ui.Dialog({
					title: "Motivo de cancelación",
					fields: [
						{
							fieldname: "motivo",
							fieldtype: "Small Text",
							label: "Motivo",
							reqd: 1,
						},
					],
					primary_action_label: "Cancelar cita",
					primary_action(vals) {
						frappe.call({
							method: "hubgh.hubgh.page.sst_seguimiento_examenes.sst_seguimiento_examenes.set_cita_outcome",
							args: {
								cita_name: citaName,
								estado: "Cancelada",
								motivo: vals.motivo,
							},
							callback(r) {
								if (r && r.message && r.message.ok) {
									dm.hide();
									frappe.show_alert({ message: __("Cita cancelada."), indicator: "orange" });
									resetAndFetch();
								}
							},
						});
					},
				});
				dm.show();
			}
		);
	}

	// ─── T16: Dialog "Editar observaciones" ───────────────────────────────
	function openObservacionesDialog(citaName, obsActual) {
		const d = new frappe.ui.Dialog({
			title: "Observaciones SST",
			fields: [
				{
					fieldname: "texto",
					fieldtype: "Long Text",
					label: "Observaciones",
					default: obsActual || "",
				},
			],
			primary_action_label: "Guardar",
			primary_action(values) {
				frappe.call({
					method: "hubgh.hubgh.page.sst_seguimiento_examenes.sst_seguimiento_examenes.set_cita_observaciones",
					args: {
						cita_name: citaName,
						texto: values.texto || "",
					},
					callback(r) {
						if (r && r.message && r.message.ok) {
							d.hide();
							frappe.show_alert({ message: __("Observaciones guardadas."), indicator: "green" });
							resetAndFetch();
						}
					},
				});
			},
		});
		d.show();
	}

	// ─── T16: Exportar Excel ──────────────────────────────────────────────
	function exportarExcel() {
		frappe.show_alert({ message: __("Exportando..."), indicator: "blue" });
		frappe.call({
			method: "hubgh.hubgh.page.sst_seguimiento_examenes.sst_seguimiento_examenes.export_seguimiento_examenes_xlsx",
			args: { filters: getFilters() },
			callback(r) {
				if (!r || !r.message) return;
				const { filename, content_b64, count } = r.message;
				// Decodificar base64 y descargar
				const byteChars = atob(content_b64);
				const byteArr = new Uint8Array(byteChars.length);
				for (let i = 0; i < byteChars.length; i++) {
					byteArr[i] = byteChars.charCodeAt(i);
				}
				const blob = new Blob([byteArr], {
					type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
				});
				const url = URL.createObjectURL(blob);
				const a = document.createElement("a");
				a.href = url;
				a.download = filename;
				document.body.appendChild(a);
				a.click();
				document.body.removeChild(a);
				URL.revokeObjectURL(url);
				frappe.show_alert({
					message: __("Excel descargado: {0} filas.", [count]),
					indicator: "green",
				});
			},
			error() {
				frappe.msgprint(__("Error al exportar. Intentá de nuevo."));
			},
		});
	}

	// ─── Helpers de navegación ────────────────────────────────────────────
	function resetAndFetch() {
		state.offset = 0;
		fetchRows();
	}

	// ─── Event listeners ──────────────────────────────────────────────────
	$body.on("click", "#btn-actualizar", resetAndFetch);
	$body.on("click", "#btn-exportar", exportarExcel);

	// Paginación
	$body.on("click", "#btn-prev", () => {
		if (state.offset > 0) {
			state.offset = Math.max(0, state.offset - state.limit);
			fetchRows();
		}
	});
	$body.on("click", "#btn-next", () => {
		if (state.offset + state.limit < state.total) {
			state.offset += state.limit;
			fetchRows();
		}
	});

	// Debounce en campos texto (T13 — cambio de filtros reset página 1)
	$body.on("input", "#f-ciudad, #f-sede, #f-search", () => {
		debounce(resetAndFetch, 300);
	});
	// Selects y fechas: reset inmediato
	$body.on("change", "#f-fecha-desde, #f-fecha-hasta, #f-estado, #f-modo, #f-tipo-cargo", resetAndFetch);
	$body.on("change", "#f-solo-manuales", resetAndFetch);

	// Acciones de tabla
	$body.on("click", ".btn-agendar", function () {
		const $btn = $(this);
		openAgendarDialog(
			$btn.data("cita"),
			$btn.data("nombre"),
			$btn.data("fecha"),
			$btn.data("hora"),
			$btn.data("sede")
		);
	});

	$body.on("click", ".btn-outcome", function () {
		const $btn = $(this);
		openOutcomeDialog($btn.data("cita"), $btn.data("nombre"), $btn.data("fecha"));
	});

	$body.on("click", ".btn-obs", function () {
		const $btn = $(this);
		openObservacionesDialog($btn.data("cita"), $btn.data("obs"));
	});

	$body.on("click", ".btn-cancelar", function () {
		const $btn = $(this);
		cancelarCita($btn.data("cita"), $btn.data("nombre"), $btn.data("fecha"));
	});

	// ─── Carga inicial ────────────────────────────────────────────────────
	fetchRows();
};
