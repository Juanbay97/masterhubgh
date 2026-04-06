frappe.pages['operacion_punto_lite'].on_page_load = function (wrapper) {
	injectOplScrollStyles();
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Operación Punto Lite',
		single_column: true
	});

	const state = {
		point: null,
		kpis: {},
		personas: [],
		cursos: [],
		novedad_tab: 'Incapacidad',
		persona_actual: null,
		person_map: {}
	};

	render_shell(page);
	bind_actions(page, state);
	load_page_data(state);
};

function render_shell(page) {
	const $container = $(page.main || page.body);
	$container.empty();

	$container.append(`
		<div class="opl-page" style="padding:12px 16px 24px;background:#f8fafc;min-height:calc(100vh - 120px);">
			<div class="card" style="border:none;border-radius:12px;margin-bottom:12px;">
				<div class="card-body">
					<div class="d-flex justify-content-between align-items-start flex-wrap" style="gap:10px;">
						<div>
							<h4 style="margin:0 0 6px 0;font-weight:700;">Operación Punto Lite</h4>
							<div id="opl-point" class="text-muted small">Punto: cargando...</div>
						</div>
						<button class="btn btn-primary btn-sm" id="opl-btn-reportar">Reportar novedad</button>
					</div>
					<div class="row" style="margin-top:12px;" id="opl-kpis"></div>
				</div>
			</div>

			<div class="card" style="border:none;border-radius:12px;margin-bottom:12px;">
				<div class="card-body">
					<div class="d-flex justify-content-between align-items-center flex-wrap" style="gap:8px;">
						<h6 style="font-weight:700;margin:0;">Novedades</h6>
						<div style="display:flex;gap:6px;flex-wrap:wrap;">
							<button class="btn btn-xs btn-primary opl-tab" data-tab="Incapacidad">Incapacidades</button>
							<button class="btn btn-xs btn-default opl-tab" data-tab="Accidente SST">Accidentes</button>
							<button class="btn btn-xs btn-default opl-tab" data-tab="Otras">Otras</button>
						</div>
					</div>
					<div id="opl-novedades" class="opl-scroll-list" style="display:grid;gap:8px;margin-top:10px;"></div>
				</div>
			</div>

			<div class="card" style="border:none;border-radius:12px;margin-bottom:12px;">
				<div class="card-body">
					<div class="d-flex justify-content-between align-items-center flex-wrap" style="gap:8px;">
						<h6 style="font-weight:700;margin:0;">Documentos por persona</h6>
						<div style="display:flex;gap:6px;flex-wrap:wrap;">
							<select id="opl-persona-select" class="form-control form-control-sm" style="min-width:260px;"></select>
							<input id="opl-month" type="month" class="form-control form-control-sm" style="width:160px;" />
							<button class="btn btn-sm btn-default" id="opl-export-persona">ZIP persona</button>
							<button class="btn btn-sm btn-default" id="opl-export-mes">ZIP punto/mes</button>
						</div>
					</div>
					<div id="opl-docs" class="opl-scroll-table" style="margin-top:10px;"></div>
				</div>
			</div>

			<div class="card" style="border:none;border-radius:12px;">
				<div class="card-body">
					<div class="d-flex justify-content-between align-items-center flex-wrap" style="gap:8px;">
						<h6 style="font-weight:700;margin:0;">Reporte cursos de calidad</h6>
						<button class="btn btn-sm btn-default" id="opl-export-cursos">Descargar PDF</button>
					</div>
					<div id="opl-cursos" class="opl-scroll-table" style="margin-top:10px;"></div>
				</div>
			</div>
		</div>
	`);

	$('#opl-month').val(frappe.datetime.now_date().slice(0, 7));
}

function bind_actions(page, state) {
	const $root = $(page.main || page.body);

	$root.off('click', '.opl-tab').on('click', '.opl-tab', function () {
		state.novedad_tab = $(this).data('tab') || 'Incapacidad';
		$root.find('.opl-tab').removeClass('btn-primary').addClass('btn-default');
		$(this).removeClass('btn-default').addClass('btn-primary');
		load_novedades(state);
	});

	$root.off('click', '#opl-btn-reportar').on('click', '#opl-btn-reportar', function () {
		open_reportar_modal(state);
	});

	$root.off('change', '#opl-persona-select').on('change', '#opl-persona-select', function () {
		state.persona_actual = $(this).val() || null;
		if (state.persona_actual) {
			load_person_docs(state);
		}
	});

	$root.off('click', '#opl-export-persona').on('click', '#opl-export-persona', function () {
		if (!state.persona_actual) {
			frappe.msgprint('Selecciona una persona para exportar documentos.');
			return;
		}
		export_docs_zip({ mode: 'persona', persona: state.persona_actual });
	});

	$root.off('click', '#opl-export-mes').on('click', '#opl-export-mes', function () {
		const month = $('#opl-month').val();
		export_docs_zip({ mode: 'punto_mes', month: month });
	});

	$root.off('click', '#opl-export-cursos').on('click', '#opl-export-cursos', function () {
		frappe.call({
			method: 'hubgh.api.ops.export_cursos_pdf',
			args: { filters: { scope: 'operacion_punto_lite' } },
			callback: function (r) {
				const out = r.message || {};
				if (out.file_url) {
					window.open(out.file_url, '_blank');
				}
			}
		});
	});
}

function load_page_data(state) {
	frappe.call({
		method: 'hubgh.api.ops.get_punto_lite',
		callback: function (r) {
			const data = r.message || {};
			state.point = data.punto || null;
			state.kpis = data.kpis || {};
			state.personas = data.personas || [];
			state.cursos = data.cursos_reporte || [];

			state.person_map = {};
			(state.personas || []).forEach(function (p) {
				state.person_map[p.name] = p.nombre || p.name;
			});

			state.persona_actual = state.personas.length ? state.personas[0].name : null;

			render_header(state);
			render_person_selector(state);
			render_cursos(state);
			load_novedades(state);
			if (state.persona_actual) {
				load_person_docs(state);
			}
		}
	});
}

function render_header(state) {
	const pointName = (state.point && state.point.name) || 'Sin punto asignado';
	$('#opl-point').text(`Punto: ${pointName}`);

	const kpis = state.kpis || {};
	const cards = [
		{ label: 'Personal activo', value: kpis.personal_activo || 0, color: '#0ea5e9' },
		{ label: 'Incapacidades abiertas', value: kpis.incapacidades_abiertas || 0, color: '#f59e0b' },
		{ label: 'Accidentes 30 días', value: kpis.accidentes_30d || 0, color: '#ef4444' },
		{ label: 'Cursos calidad vencidos', value: kpis.cursos_calidad_vencidos || 0, color: '#10b981' }
	];

	$('#opl-kpis').html(cards.map((c) => `
		<div class="col-lg-3 col-md-6 col-sm-12" style="margin-bottom:8px;">
			<div style="border:1px solid #e2e8f0;border-radius:10px;padding:10px;background:#fff;">
				<div class="small text-muted">${escape_html(c.label)}</div>
				<div style="font-size:24px;font-weight:700;color:${c.color};line-height:1.2;">${c.value}</div>
			</div>
		</div>
	`).join(''));
}

function load_novedades(state) {
	frappe.call({
		method: 'hubgh.api.ops.get_punto_novedades',
		args: { tipo: state.novedad_tab },
		callback: function (r) {
			const rows = r.message || [];
			if (!rows.length) {
				$('#opl-novedades').html('<div class="text-muted small">Sin novedades para este filtro.</div>');
				return;
			}

			$('#opl-novedades').html(rows.map((row) => `
				<div style="border:1px solid #e2e8f0;border-radius:10px;padding:10px;background:#fff;">
					<div class="d-flex justify-content-between align-items-center" style="gap:8px;">
						<strong>${escape_html(row.tipo || 'Novedad')}</strong>
						<span class="badge badge-light">${escape_html(row.estado || '')}</span>
					</div>
					<div class="small text-muted" style="margin-top:4px;">
						Persona: ${escape_html(row.persona_nombre || row.persona || '')}
						· Inicio: ${fmt_date(row.fecha_inicio)}
						${row.fecha_fin ? ` · Fin: ${fmt_date(row.fecha_fin)}` : ''}
					</div>
					<div style="margin-top:6px;">${escape_html(row.descripcion || '')}</div>
				</div>
			`).join(''));
		}
	});
}

function render_person_selector(state) {
	const opts = (state.personas || []).map((p) => {
		const selected = p.name === state.persona_actual ? 'selected' : '';
		return `<option value="${escape_html(p.name)}" ${selected}>${escape_html(p.nombre || p.name)}</option>`;
	});

	$('#opl-persona-select').html(opts.join('') || '<option value="">Sin personas</option>');
}

function load_person_docs(state) {
	frappe.call({
		method: 'hubgh.api.ops.get_person_docs',
		args: { persona: state.persona_actual },
		callback: function (r) {
			const data = r.message || {};
			const items = data.items || [];
			if (!items.length) {
				$('#opl-docs').html('<div class="text-muted small">No hay categorías documentales activas.</div>');
				return;
			}

			$('#opl-docs').html(`
				<table class="table table-sm table-bordered" style="margin:0;background:#fff;">
					<thead>
						<tr>
							<th>Categoría</th>
							<th>Requerido</th>
							<th>Estado</th>
							<th>Archivo</th>
						</tr>
					</thead>
					<tbody>
						${items.map((it) => `
							<tr>
								<td>${escape_html(it.nombre || it.clave || '')}</td>
								<td>${Number(it.requerido) ? 'Sí' : 'No'}</td>
								<td>${escape_html(it.status || 'Pendiente')}</td>
								<td>${it.file ? `<a href="${escape_html(it.file)}" target="_blank">Abrir</a>` : '<span class="text-muted">-</span>'}</td>
							</tr>
						`).join('')}
					</tbody>
				</table>
			`);
		}
	});
}

function render_cursos(state) {
	const rows = state.cursos || [];
	if (!rows.length) {
		$('#opl-cursos').html('<div class="text-muted small">Sin registros para el período consultado.</div>');
		return;
	}

	$('#opl-cursos').html(`
		<table class="table table-sm table-bordered" style="margin:0;background:#fff;">
			<thead>
				<tr>
					<th>Persona</th>
					<th>Estado</th>
					<th>Avance</th>
				</tr>
			</thead>
			<tbody>
				${rows.map((r) => `
					<tr>
						<td>${escape_html(r.nombre || r.persona || '')}</td>
						<td>${escape_html(r.estado || 'Pendiente LMS')}</td>
						<td>${Number(r.avance || 0)}%</td>
					</tr>
				`).join('')}
			</tbody>
		</table>
	`);
}

function open_reportar_modal(state) {
	const personOptions = (state.personas || []).map((p) => ({
		label: p.nombre || p.name,
		value: p.name
	}));

	const d = new frappe.ui.Dialog({
		title: 'Reportar novedad',
		fields: [
			{
				label: 'Persona',
				fieldname: 'persona',
				fieldtype: 'Select',
				options: personOptions.map((o) => o.value),
				reqd: 1,
				default: state.persona_actual || (personOptions[0] && personOptions[0].value)
			},
			{
				label: 'Tipo',
				fieldname: 'tipo',
				fieldtype: 'Select',
				options: 'Accidente SST\nIncapacidad\nAusentismo\nLlamado de atención\nOtro',
				reqd: 1
			},
			{
				label: 'Fecha evento/inicio',
				fieldname: 'fecha_inicio',
				fieldtype: 'Date',
				default: frappe.datetime.now_date(),
				reqd: 1
			},
			{
				label: 'Fecha fin',
				fieldname: 'fecha_fin',
				fieldtype: 'Date'
			},
			{
				label: 'Descripción',
				fieldname: 'descripcion',
				fieldtype: 'Small Text',
				reqd: 1
			},
			{
				label: 'Evidencias (URLs o referencias separadas por coma o salto de línea)',
				fieldname: 'evidencias',
				fieldtype: 'Small Text'
			}
		],
		primary_action_label: 'Guardar',
		primary_action(values) {
			frappe.call({
				method: 'hubgh.api.ops.create_novedad',
				args: {
					payload: {
						persona: values.persona,
						tipo: values.tipo,
						fecha_inicio: values.fecha_inicio,
						fecha_fin: values.fecha_fin,
						descripcion: values.descripcion,
						evidencias: values.evidencias
					}
				},
				freeze: true,
				freeze_message: 'Creando novedad...',
				callback: function () {
					d.hide();
					frappe.show_alert({ message: 'Novedad creada', indicator: 'green' });
					load_page_data(state);
				}
			});
		}
	});

	d.show();
}

function export_docs_zip(args) {
	frappe.call({
		method: 'hubgh.api.ops.export_docs_zip',
		args: args,
		callback: function (r) {
			const out = r.message || {};
			if (out.file_url) {
				window.open(out.file_url, '_blank');
			}
		}
	});
}

function escape_html(v) {
	return frappe.utils.escape_html(v == null ? '' : String(v));
}

function fmt_date(v) {
	if (!v) return '';
	return frappe.datetime.str_to_user(v);
}

function injectOplScrollStyles() {
	if (document.getElementById('opl-scroll-styles')) return;
	const style = document.createElement('style');
	style.id = 'opl-scroll-styles';
	style.innerHTML = `
		.opl-scroll-list {
			max-height: 700px;
			overflow-y: auto;
			overflow-x: hidden;
			padding-right: 4px;
		}
		.opl-scroll-table {
			max-height: 420px;
			overflow-y: auto;
			overflow-x: auto;
		}
		.opl-scroll-table table {
			margin-bottom: 0;
		}
	`;
	document.head.appendChild(style);
}
