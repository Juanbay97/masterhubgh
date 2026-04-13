const RETIREMENT_REASON_OPTIONS = [
	'',
	'Renuncia',
	'Terminación con justa causa',
	'Terminación sin justa causa',
	'Mutuo acuerdo',
	'Fin de contrato',
	'Jubilación',
	'Fallecimiento',
	'Abandono',
	'Otro',
];

frappe.pages['bandeja_retiros_empleados'].on_page_load = function(wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Bandeja de retiros',
		single_column: true,
	});

	wrapper.employeeRetirementTray = new EmployeeRetirementTray(wrapper, page);
};

class EmployeeRetirementTray {
	constructor(wrapper, page) {
		this.wrapper = $(wrapper);
		this.page = page;
		this.context = null;
		this.data = { rows: [], summary: {} };
		this.makeFilters();
		this.makeActions();
		this.renderLoading('Validando acceso a la bandeja de retiros...');
		this.loadContext();
	}

	makeFilters() {
		this.page.add_field({
			fieldname: 'search',
			label: __('Buscar persona'),
			fieldtype: 'Data',
			change: () => this.refresh(),
		});
		this.page.add_field({
			fieldname: 'status',
			label: __('Estado retiro'),
			fieldtype: 'Select',
			options: '\nProgramado\nEjecutado\nRevertido\nLegado Retirado',
			change: () => this.refresh(),
		});
	}

	makeActions() {
		this.page.set_primary_action(__('Registrar retiro'), () => this.openRetirementDialog());
		this.page.add_inner_button(__('Actualizar'), () => this.refresh());
	}

	getFieldValue(fieldname) {
		const field = this.page.fields_dict && this.page.fields_dict[fieldname];
		return field && typeof field.get_value === 'function' ? field.get_value() : null;
	}

	loadContext() {
		frappe.call({
			method: 'hubgh.hubgh.page.bandeja_retiros_empleados.bandeja_retiros_empleados.get_retirement_flow_context',
			callback: (response) => {
				this.context = response.message || {};
				if (!this.context.can_manage) {
					this.renderUnauthorized();
					return;
				}
				this.refresh();
				const routeEmployee = frappe.route_options && frappe.route_options.employee;
				if (routeEmployee) {
					const employee = routeEmployee;
					frappe.route_options = null;
					this.openRetirementDialog(employee);
				}
			},
			error: () => this.renderError('No pudimos validar el acceso a la bandeja de retiros.'),
		});
	}

	refresh() {
		if (!this.context || !this.context.can_manage) return;
		this.renderLoading('Actualizando base histórica de retiros...');
		frappe.call({
			method: 'hubgh.hubgh.page.bandeja_retiros_empleados.bandeja_retiros_empleados.get_retirement_tray',
			args: {
				filters: JSON.stringify({
					search: this.getFieldValue('search') || '',
					status: this.getFieldValue('status') || '',
					limit: 200,
				}),
			},
			callback: (response) => {
				this.data = response.message || { rows: [], summary: {} };
				this.render();
			},
			error: (error) => this.renderError((error && error.message) || 'No pudimos cargar la bandeja de retiros.'),
		});
	}

	openRetirementDialog(prefillEmployee) {
		if (!this.context || !this.context.can_manage) return;
		const dialog = new frappe.ui.Dialog({
			title: __('Registrar retiro empleado'),
			fields: [
				{ fieldname: 'employee', label: __('Empleado'), fieldtype: 'Link', options: 'Ficha Empleado', reqd: 1, default: prefillEmployee || '' },
				{ fieldname: 'last_worked_date', label: __('Último día laborado'), fieldtype: 'Date', reqd: 1, default: frappe.datetime.get_today() },
				{ fieldname: 'reason', label: __('Motivo retiro'), fieldtype: 'Select', options: RETIREMENT_REASON_OPTIONS.join('\n'), reqd: 1 },
				{ fieldname: 'closure_date', label: __('Fecha cierre'), fieldtype: 'Date', default: frappe.datetime.get_today() },
				{ fieldname: 'closure_summary', label: __('Detalle cierre'), fieldtype: 'Small Text' },
			],
			primary_action_label: __('Guardar retiro'),
			primary_action: (values) => {
				frappe.call({
					method: 'hubgh.hubgh.page.bandeja_retiros_empleados.bandeja_retiros_empleados.submit_employee_retirement',
					args: {
						employee: values.employee,
						last_worked_date: values.last_worked_date,
						reason: values.reason,
						closure_date: values.closure_date,
						closure_summary: values.closure_summary,
					},
					callback: (response) => {
						const result = response.message || {};
						dialog.hide();
						frappe.show_alert({
							message: result.status === 'scheduled' ? __('Retiro programado correctamente.') : __('Retiro registrado correctamente.'),
							indicator: 'green',
						});
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
						<div class="retirement-kickers"><span>Relaciones Laborales</span><span>Base histórica</span></div>
						<h3>Retiro y desvinculación de personal</h3>
						<p class="text-muted mb-0">La bandeja consolida retiros programados, ejecutados y legados para trazabilidad futura y cálculo de métricas.</p>
					</div>
				</div>
				<div class="row retirement-kpi-grid">
					${this.renderKpi('Total en base', summary.total || 0)}
					${this.renderKpi('Programados', summary.scheduled || 0)}
					${this.renderKpi('Ejecutados', summary.executed || 0)}
					${this.renderKpi('Legado retirado', summary.legacy_retired || 0)}
				</div>
				<div class="retirement-table-card">
					<table class="table table-bordered">
						<thead>
							<tr>
								<th>Persona</th>
								<th>Motivo</th>
								<th>Último día</th>
								<th>Fecha retiro</th>
								<th>Fecha cierre</th>
								<th>Estado flujo</th>
								<th>Estado empleado</th>
							</tr>
						</thead>
						<tbody>
							${rows.length ? rows.map((row) => `
								<tr>
									<td><strong>${frappe.utils.escape_html(row.full_name || row.employee || '')}</strong><br><small class="text-muted">${frappe.utils.escape_html(row.employee || '')} · ${frappe.utils.escape_html(row.cedula || '')}</small></td>
									<td>${frappe.utils.escape_html(row.reason || 'Sin motivo')}</td>
									<td>${this.formatDate(row.last_worked_date)}</td>
									<td>${this.formatDate(row.retirement_date)}</td>
									<td>${this.formatDate(row.closure_date)}</td>
									<td><span class="indicator-pill ${this.flowColor(row.flow_status)}">${frappe.utils.escape_html(row.flow_status || '')}</span></td>
									<td>${frappe.utils.escape_html(row.employee_status || '')}</td>
								</tr>
							`).join('') : '<tr><td colspan="7" class="text-muted text-center">No hay retiros visibles con los filtros actuales.</td></tr>'}
						</tbody>
					</table>
				</div>
			</div>
		`;
		this.wrapper.find('.layout-main-section').html(html);
	}

	renderKpi(label, value) {
		return `<div class="col-md-3"><div class="dashboard-card-stat"><span class="stat-label">${label}</span><span class="stat-val">${value}</span></div></div>`;
	}

	formatDate(value) {
		return value ? frappe.datetime.str_to_user(value) : '-';
	}

	flowColor(status) {
		if (status === 'Ejecutado' || status === 'Legado Retirado') return 'red';
		if (status === 'Programado') return 'orange';
		if (status === 'Revertido') return 'green';
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
