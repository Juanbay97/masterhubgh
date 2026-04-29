frappe.pages['bandeja_casos_disciplinarios'].on_page_load = function(wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Bandeja Disciplinaria RRLL',
		single_column: true,
	});

	(window.hubghBandejasUI || { injectBaseStyles() {} }).injectBaseStyles();

	const $root = $("<div class='hubgh-board-shell'></div>").appendTo(page.body);
	const esc = value => frappe.utils.escape_html(value == null ? "" : String(value));

	let state = {
		rows: [],
		summary: {},
		context: null,
		status: 'idle',
		error: '',
	};

	// ---------------------------------------------------------------------------
	// Filters
	// ---------------------------------------------------------------------------
	const makeFilters = () => {
		page.add_field({ fieldname: 'search', label: __('Buscar caso o persona'), fieldtype: 'Data', change: () => refresh() });
		page.add_field({
			fieldname: 'estado',
			label: __('Estado'),
			fieldtype: 'Select',
			options: '\nSolicitado\nEn Triage\nDescargos Programados\nCitado\nEn Descargos\nEn Deliberación\nCerrado',
			change: () => refresh(),
		});
		page.add_field({
			fieldname: 'outcome',
			label: __('Resultado'),
			fieldtype: 'Select',
			options: '\nArchivo\nRecordatorio de Funciones\nLlamado de Atención Directo\nLlamado de Atención\nSuspensión\nTerminación',
			change: () => refresh(),
		});
		page.add_field({ fieldname: 'pdv', label: __('PDV'), fieldtype: 'Link', options: 'Punto de Venta', change: () => refresh() });
		page.add_field({ fieldname: 'date_from', label: __('Desde'), fieldtype: 'Date', change: () => refresh() });
		page.add_field({ fieldname: 'date_to', label: __('Hasta'), fieldtype: 'Date', change: () => refresh() });
	};

	const makeActions = () => {
		page.set_primary_action(__('Nuevo caso'), () => frappe.new_doc('Caso Disciplinario'));
		page.add_inner_button(__('Actualizar'), () => refresh());
	};

	const getFieldValue = fieldname => {
		const field = page.fields_dict && page.fields_dict[fieldname];
		return field && typeof field.get_value === 'function' ? field.get_value() : null;
	};

	// ---------------------------------------------------------------------------
	// Status colors
	// ---------------------------------------------------------------------------
	const statusPill = estado => {
		const map = {
			'En Triage': 'orange',
			'Descargos Programados': 'blue',
			'Citado': 'blue',
			'En Descargos': 'yellow',
			'En Deliberación': 'yellow',
			'Cerrado': 'green',
			'Solicitado': 'gray',
		};
		return `<span class="indicator-pill ${map[estado] || 'gray'}">${esc(estado || '')}</span>`;
	};

	const outcomePill = outcome => {
		if (!outcome) return '';
		const map = {
			'Suspensión': 'red',
			'Terminación': 'red',
			'Llamado de Atención': 'orange',
			'Llamado de Atención Directo': 'orange',
			'Recordatorio de Funciones': 'gray',
			'Archivo': 'gray',
		};
		return `<span class="indicator-pill ${map[outcome] || 'gray'}">${esc(outcome)}</span>`;
	};

	// ---------------------------------------------------------------------------
	// Próxima acción button
	// ---------------------------------------------------------------------------
	const renderAccionBtn = row => {
		const accion = row.proxima_accion || '';
		const caseName = esc(row.name);
		if (!accion || row.estado === 'Cerrado') {
			return '<span class="text-muted">Sin acciones</span>';
		}
		if (accion.includes('Hacer triage') || accion.includes('triage')) {
			return `<button class="btn btn-xs btn-warning btn-accion-triage" data-case="${caseName}" title="${esc(accion)}">Hacer triage</button>`;
		}
		if (accion.includes('Emitir citación')) {
			return `<button class="btn btn-xs btn-info btn-accion-citacion" data-case="${caseName}" title="${esc(accion)}">Emitir citación</button>`;
		}
		if (accion.includes('Conducir descargos')) {
			return `<a href="/app/caso-disciplinario/${caseName}" class="btn btn-xs btn-primary" title="${esc(accion)}">Conducir descargos</a>`;
		}
		if (accion.includes('Completar acta')) {
			return `<a href="/app/acta-descargos?afectado=${caseName}" class="btn btn-xs btn-secondary" title="${esc(accion)}">Completar acta</a>`;
		}
		if (accion.includes('Deliberar')) {
			return `<button class="btn btn-xs btn-danger btn-accion-deliberar" data-case="${caseName}" title="${esc(accion)}">Deliberar</button>`;
		}
		return `<a href="/app/caso-disciplinario/${caseName}" class="btn btn-xs btn-default" title="${esc(accion)}">Ejecutar acción</a>`;
	};

	// ---------------------------------------------------------------------------
	// Dialog cierre
	// ---------------------------------------------------------------------------
	const openClosureDialog = row => {
		const dialog = new frappe.ui.Dialog({
			title: __('Cerrar caso disciplinario'),
			fields: [
				{ fieldname: 'decision', label: __('Resultado'), fieldtype: 'Select', options: '\nArchivo\nLlamado de atención\nSuspensión\nTerminación', reqd: 1 },
				{ fieldname: 'closure_date', label: __('Fecha cierre'), fieldtype: 'Date', reqd: 1, default: frappe.datetime.get_today() },
				{ fieldname: 'closure_summary', label: __('Resumen de cierre'), fieldtype: 'Small Text', reqd: 1 },
				{ fieldname: 'suspension_start', label: __('Inicio suspensión'), fieldtype: 'Date', depends_on: 'eval:doc.decision=="Suspensión"' },
				{ fieldname: 'suspension_end', label: __('Fin suspensión'), fieldtype: 'Date', depends_on: 'eval:doc.decision=="Suspensión"' },
			],
			primary_action_label: __('Cerrar caso'),
			primary_action: values => {
				frappe.call({
					method: 'hubgh.hubgh.page.bandeja_casos_disciplinarios.bandeja_casos_disciplinarios.close_disciplinary_case',
					args: {
						case_name: row.name,
						decision: values.decision,
						closure_date: values.closure_date,
						closure_summary: values.closure_summary,
						suspension_start: values.suspension_start,
						suspension_end: values.suspension_end,
					},
					callback: () => {
						dialog.hide();
						frappe.show_alert({ message: __('Caso cerrado correctamente.'), indicator: 'green' });
						refresh();
					},
				});
			},
		});
		dialog.show();
	};

	// ---------------------------------------------------------------------------
	// Render
	// ---------------------------------------------------------------------------
	const renderHero = () => {
		const s = state.summary || {};
		const total = s.total || 0;
		const abiertos = total - (s.closed || 0);
		const cerrados = s.closed || 0;
		return `
			<div class='hubgh-board-hero'>
				<div class='hubgh-board-hero-head'>
					<div>
						<div class='hubgh-board-kickers'>
							<span class='hubgh-board-kicker'>Relaciones Laborales</span>
							<span class='hubgh-board-kicker'>Disciplina</span>
						</div>
						<h3 class='hubgh-board-title'>Casos Disciplinarios</h3>
						<p class='hubgh-board-copy'>Esta bandeja concentra todos los procesos disciplinarios activos y permite ejecutar la próxima acción de cada caso con un solo click.</p>
					</div>
					<div class='hubgh-board-meta'>
						<span class='hubgh-meta-pill'>${total} total · ${abiertos} abiertos · ${cerrados} cerrados</span>
					</div>
				</div>
				<div class='hubgh-board-shortcuts'>
					<button class='btn btn-sm btn-primary btn-nuevo-caso'>Nuevo caso</button>
					<a href='/app/carpeta-documental-empleado' class='btn btn-sm btn-default'>Ver carpeta documental</a>
				</div>
			</div>
		`;
	};

	const renderCards = rows => {
		if (!rows || !rows.length) {
			return `
				<div class='hubgh-empty'>
					<span class='hubgh-empty-title'>Sin casos con los filtros actuales</span>
					<p class='hubgh-empty-copy'>Ajustá los filtros o creá un nuevo caso disciplinario.</p>
				</div>
			`;
		}
		return rows.map(row => {
			const afectados = row.afectados_summary || {};
			const preview = (afectados.preview || []).map(n => esc(n)).join(', ');
			const countExtra = afectados.count > 3 ? ` <span class="text-muted">+${afectados.count - 3} más</span>` : '';
			const vencidaBadge = row.citacion_vencida ? '<span class="indicator-pill red">Vencida</span>' : '';
			const accionBtn = renderAccionBtn(row);
			const fechaMovimiento = row.fecha_ultimo_movimiento ? frappe.datetime.str_to_user(row.fecha_ultimo_movimiento) : '-';
			return `
				<div class='hubgh-card${row.citacion_vencida ? ' hubgh-card--danger' : ''}'>
					<div class='hubgh-card-head'>
						<div class='hubgh-main'>
							<div class='hubgh-title-row'>
								<a class='hubgh-name' href='/app/caso-disciplinario/${esc(row.name)}'>${esc(row.name)}</a>
								${statusPill(row.estado)}
								${vencidaBadge}
							</div>
							<div class='hubgh-meta'>
								${preview ? `${preview}${countExtra}` : '<span class="text-muted">Sin afectados</span>'}
							</div>
							<div class='hubgh-submeta'>
								<span>PDV: ${esc(row.pdv || '—')}</span>
								<span>Falta: ${esc(row.fault_type || '—')}</span>
								<span>Últ. mov: ${esc(fechaMovimiento)}</span>
							</div>
							<div class='hubgh-badges-grid'>
								${row.outcome ? `<div class='hubgh-badge'><span class='hubgh-badge-label'>Resultado</span>${outcomePill(row.outcome)}</div>` : ''}
								<div class='hubgh-badge'>
									<span class='hubgh-badge-label'>Próxima acción</span>
									<span>${esc(row.proxima_accion || '—')}</span>
								</div>
							</div>
						</div>
					</div>
					<div class='hubgh-actions'>
						${accionBtn}
						${row.can_close ? `<button class='btn btn-xs btn-primary btn-close-case ml-1' data-case='${esc(row.name)}'>Cerrar caso</button>` : ''}
					</div>
				</div>
			`;
		}).join('');
	};

	const renderLoading = msg => {
		$root.html(`
			<div class='hubgh-empty'>
				<span class='hubgh-empty-title'>${esc(msg || 'Cargando...')}</span>
			</div>
		`);
	};

	const renderUnauthorized = () => {
		$root.html('<div class="alert alert-warning">Solo Relaciones Laborales puede operar esta bandeja.</div>');
	};

	const renderError = msg => {
		$root.html(`<div class="alert alert-danger">${esc(msg)}</div>`);
	};

	const render = () => {
		const rows = state.rows || [];
		$root.html(`
			${renderHero()}
			<div class='hubgh-cards-grid'>
				${renderCards(rows)}
			</div>
		`);

		// Bind shortcuts
		$root.find('.btn-nuevo-caso').on('click', () => frappe.new_doc('Caso Disciplinario'));

		// Bind cierre
		$root.find('.btn-close-case').on('click', event => {
			const caseName = $(event.currentTarget).data('case');
			const row = rows.find(r => r.name === caseName);
			if (row) openClosureDialog(row);
		});

		// Bind triage
		$root.find('.btn-accion-triage').on('click', event => {
			frappe.set_route('Form', 'Caso Disciplinario', $(event.currentTarget).data('case'));
		});

		// Bind citacion
		$root.find('.btn-accion-citacion').on('click', event => {
			frappe.set_route('Form', 'Caso Disciplinario', $(event.currentTarget).data('case'));
		});

		// Bind deliberar
		$root.find('.btn-accion-deliberar').on('click', event => {
			const caseName = $(event.currentTarget).data('case');
			const row = rows.find(r => r.name === caseName);
			if (row) openClosureDialog(row);
		});
	};

	// ---------------------------------------------------------------------------
	// Load
	// ---------------------------------------------------------------------------
	const loadContext = () => {
		frappe.call({
			method: 'hubgh.hubgh.page.bandeja_casos_disciplinarios.bandeja_casos_disciplinarios.get_disciplinary_flow_context',
			callback: response => {
				state.context = response.message || {};
				if (!state.context.can_manage) {
					renderUnauthorized();
					return;
				}
				const routePdv = frappe.route_options && frappe.route_options.pdv;
				if (routePdv && page.fields_dict.pdv) {
					page.fields_dict.pdv.set_value(routePdv);
				}
				frappe.route_options = null;
				refresh();
			},
			error: () => renderError('No pudimos validar el acceso a la bandeja disciplinaria.'),
		});
	};

	const refresh = () => {
		if (!state.context || !state.context.can_manage) return;
		renderLoading('Actualizando casos disciplinarios...');
		frappe.call({
			method: 'hubgh.hubgh.page.bandeja_casos_disciplinarios.bandeja_casos_disciplinarios.get_disciplinary_tray',
			args: {
				filters: JSON.stringify({
					search: getFieldValue('search') || '',
					estado: getFieldValue('estado') || '',
					outcome: getFieldValue('outcome') || '',
					pdv: getFieldValue('pdv') || '',
					date_from: getFieldValue('date_from') || '',
					date_to: getFieldValue('date_to') || '',
					limit: 200,
				}),
			},
			callback: response => {
				const data = response.message || { rows: [], summary: {} };
				state.rows = data.rows || [];
				state.summary = data.summary || {};
				render();
			},
			error: err => renderError((err && err.message) || 'No pudimos cargar la bandeja disciplinaria.'),
		});
	};

	makeFilters();
	makeActions();
	renderLoading('Validando acceso a la bandeja disciplinaria...');
	loadContext();
};
