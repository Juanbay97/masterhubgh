frappe.pages['bandeja_casos_disciplinarios'].on_page_load = function(wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Bandeja disciplinaria RRLL',
		single_column: true,
	});

	wrapper.disciplinaryTray = new DisciplinaryCaseTray(wrapper, page);
};

class DisciplinaryCaseTray {
	constructor(wrapper, page) {
		this.wrapper = $(wrapper);
		this.page = page;
		this.context = null;
		this.data = { rows: [], summary: {} };
		this.makeFilters();
		this.makeActions();
		this.renderLoading('Validando acceso a la bandeja disciplinaria...');
		this.loadContext();
	}

	makeFilters() {
		this.page.add_field({ fieldname: 'search', label: __('Buscar caso o persona'), fieldtype: 'Data', change: () => this.refresh() });
		this.page.add_field({ fieldname: 'status', label: __('Estado'), fieldtype: 'Select', options: '\nAbierto\nEn Proceso\nCerrado', change: () => this.refresh() });
		this.page.add_field({ fieldname: 'decision', label: __('Resultado'), fieldtype: 'Select', options: '\nArchivo\nLlamado de atención\nSuspensión\nTerminación', change: () => this.refresh() });
		this.page.add_field({ fieldname: 'pdv', label: __('PDV'), fieldtype: 'Link', options: 'Punto de Venta', change: () => this.refresh() });
	}

	makeActions() {
		this.page.set_primary_action(__('Nuevo caso'), () => frappe.new_doc('Caso Disciplinario'));
		this.page.add_inner_button(__('Actualizar'), () => this.refresh());
	}

	getFieldValue(fieldname) {
		const field = this.page.fields_dict && this.page.fields_dict[fieldname];
		return field && typeof field.get_value === 'function' ? field.get_value() : null;
	}

	loadContext() {
		frappe.call({
			method: 'hubgh.hubgh.page.bandeja_casos_disciplinarios.bandeja_casos_disciplinarios.get_disciplinary_flow_context',
			callback: (response) => {
				this.context = response.message || {};
				if (!this.context.can_manage) {
					this.renderUnauthorized();
					return;
				}
				const routePdv = frappe.route_options && frappe.route_options.pdv;
				if (routePdv && this.page.fields_dict.pdv) {
					this.page.fields_dict.pdv.set_value(routePdv);
				}
				frappe.route_options = null;
				this.refresh();
			},
			error: () => this.renderError('No pudimos validar el acceso a la bandeja disciplinaria.'),
		});
	}

	refresh() {
		if (!this.context || !this.context.can_manage) return;
		this.renderLoading('Actualizando casos disciplinarios...');
		frappe.call({
			method: 'hubgh.hubgh.page.bandeja_casos_disciplinarios.bandeja_casos_disciplinarios.get_disciplinary_tray',
			args: {
				filters: JSON.stringify({
					search: this.getFieldValue('search') || '',
					status: this.getFieldValue('status') || '',
					decision: this.getFieldValue('decision') || '',
					pdv: this.getFieldValue('pdv') || '',
					limit: 200,
				}),
			},
			callback: (response) => {
				this.data = response.message || { rows: [], summary: {} };
				this.render();
			},
			error: (error) => this.renderError((error && error.message) || 'No pudimos cargar la bandeja disciplinaria.'),
		});
	}

	openClosureDialog(row) {
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
			primary_action: (values) => {
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
						frappe.show_alert({ message: __('Caso disciplinario cerrado correctamente.'), indicator: 'green' });
						this.refresh();
					},
				});
			},
		});
		dialog.show();
	}

	render() {
		const summary = this.data.summary || {};
		const rows = this.data.rows || [];
		const html = `
			<div class="retirement-shell">
				<div class="retirement-hero">
					<div>
						<div class="retirement-kickers"><span>Relaciones Laborales</span><span>Disciplina</span></div>
						<h3>Casos disciplinarios</h3>
						<p class="text-muted mb-0">La bandeja concentra seguimiento operativo, cierre con resultado explícito y trazabilidad RRLL.</p>
					</div>
				</div>
				<div class="row retirement-kpi-grid">
					${this.renderKpi('Total', summary.total || 0)}
					${this.renderKpi('Abiertos', summary.open || 0)}
					${this.renderKpi('En proceso', summary.in_progress || 0)}
					${this.renderKpi('Cerrados', summary.closed || 0)}
				</div>
				<div class="retirement-table-card">
					<table class="table table-bordered">
						<thead>
							<tr>
								<th>Caso</th>
								<th>Persona</th>
								<th>PDV</th>
								<th>Falta</th>
								<th>Estado caso</th>
								<th>Resultado</th>
								<th>Cierre</th>
								<th>Acciones</th>
							</tr>
						</thead>
						<tbody>
							${rows.length ? rows.map((row) => `
								<tr>
									<td><a href="/app/caso-disciplinario/${frappe.utils.escape_html(row.name)}">${frappe.utils.escape_html(row.name)}</a></td>
									<td><strong>${frappe.utils.escape_html(row.employee_name || row.employee || '')}</strong><br><small class="text-muted">${frappe.utils.escape_html(row.employee || '')} · ${frappe.utils.escape_html(row.cedula || '')}</small></td>
									<td>${frappe.utils.escape_html(row.pdv || '-')}</td>
									<td>${frappe.utils.escape_html(row.fault_type || '-')}</td>
									<td><span class="indicator-pill ${this.statusColor(row.status)}">${frappe.utils.escape_html(row.status || '')}</span></td>
									<td>${frappe.utils.escape_html(row.decision || '-')}</td>
									<td>${this.formatDate(row.closure_date)}<br><small class="text-muted">${frappe.utils.escape_html(row.closure_summary || '')}</small></td>
									<td>${row.can_close ? `<button class="btn btn-xs btn-primary btn-close-case" data-case="${frappe.utils.escape_html(row.name)}">Cerrar</button>` : '<span class="text-muted">Sin acciones</span>'}</td>
								</tr>
							`).join('') : '<tr><td colspan="8" class="text-muted text-center">No hay casos visibles con los filtros actuales.</td></tr>'}
						</tbody>
					</table>
				</div>
			</div>
		`;
		this.wrapper.find('.layout-main-section').html(html);
		this.wrapper.find('.btn-close-case').on('click', (event) => {
			const caseName = $(event.currentTarget).data('case');
			const row = rows.find((item) => item.name === caseName);
			if (row) this.openClosureDialog(row);
		});
	}

	renderKpi(label, value) {
		return `<div class="col-md-3"><div class="dashboard-card-stat"><span class="stat-label">${label}</span><span class="stat-val">${value}</span></div></div>`;
	}

	formatDate(value) {
		return value ? frappe.datetime.str_to_user(value) : '-';
	}

	statusColor(status) {
		if (status === 'Cerrado') return 'green';
		if (status === 'En Proceso') return 'orange';
		if (status === 'Abierto') return 'red';
		return 'gray';
	}

	renderLoading(message) {
		this.wrapper.find('.layout-main-section').html(`<div class="text-muted p-4">${message}</div>`);
	}

	renderUnauthorized() {
		this.wrapper.find('.layout-main-section').html('<div class="alert alert-warning">Solo Relaciones Laborales puede operar esta bandeja.</div>');
	}

	renderError(message) {
		this.wrapper.find('.layout-main-section').html(`<div class="alert alert-danger">${message}</div>`);
	}
}
