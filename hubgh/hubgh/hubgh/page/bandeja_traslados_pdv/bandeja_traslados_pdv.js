frappe.pages['bandeja_traslados_pdv'].on_page_load = function(wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Bandeja Traslados PDV',
		single_column: true,
	});

	wrapper.traslados_tray = new BandejaTraslados(wrapper, page);
};

class BandejaTraslados {
	constructor(wrapper, page) {
		this.wrapper = $(wrapper);
		this.page = page;
		this.context = null;
		this.data = [];
		this.makeFilters();
		this.makeActions();
		this.renderLoading('Validando acceso a la bandeja de traslados...');
		this.loadContext();
	}

	makeFilters() {
		this.page.add_field({
			fieldname: 'search',
			label: __('Buscar empleado'),
			fieldtype: 'Data',
			change: () => this.refresh(),
		});
		this.page.add_field({
			fieldname: 'estado',
			label: __('Estado'),
			fieldtype: 'Select',
			options: '\nProgramado\nAplicado\nAnulado',
			change: () => this.refresh(),
		});
		this.page.add_field({
			fieldname: 'fecha_desde',
			label: __('Fecha desde'),
			fieldtype: 'Date',
			change: () => this.refresh(),
		});
		this.page.add_field({
			fieldname: 'fecha_hasta',
			label: __('Fecha hasta'),
			fieldtype: 'Date',
			change: () => this.refresh(),
		});
		this.page.add_field({
			fieldname: 'pdv',
			label: __('PDV'),
			fieldtype: 'Link',
			options: 'Punto de Venta',
			change: () => this.refresh(),
		});
	}

	makeActions() {
		this.page.set_primary_action(__('Nuevo traslado'), () => frappe.new_doc('Traslado PDV'));
		this.page.add_inner_button(__('Actualizar'), () => this.refresh());
	}

	getFieldValue(fieldname) {
		const field = this.page.fields_dict && this.page.fields_dict[fieldname];
		return field && typeof field.get_value === 'function' ? field.get_value() : null;
	}

	loadContext() {
		frappe.call({
			method: 'hubgh.hubgh.page.bandeja_traslados_pdv.bandeja_traslados_pdv.get_traslado_flow_context',
			callback: (response) => {
				this.context = response.message || {};
				const routePdv = frappe.route_options && frappe.route_options.pdv;
				if (routePdv && this.page.fields_dict.pdv) {
					this.page.fields_dict.pdv.set_value(routePdv);
				}
				frappe.route_options = null;
				this.refresh();
			},
			error: () => this.renderError('No pudimos validar el acceso a la bandeja de traslados.'),
		});
	}

	buildFilters() {
		const filters = {};
		const estado = this.getFieldValue('estado');
		if (estado) filters.estado = estado;
		const pdv = this.getFieldValue('pdv');
		if (pdv) {
			// PDV can be origin or destination — service-side filter handles it
			filters.pdv = pdv;
		}
		return filters;
	}

	refresh() {
		if (!this.context) return;
		this.renderLoading('Actualizando traslados...');
		frappe.call({
			method: 'hubgh.hubgh.page.bandeja_traslados_pdv.bandeja_traslados_pdv.get_traslados_tray',
			args: {
				filters: JSON.stringify(this.buildFilters()),
			},
			callback: (response) => {
				this.data = response.message || [];
				// Client-side filter for search text (name/empleado)
				const search = (this.getFieldValue('search') || '').toLowerCase();
				const fechaDesde = this.getFieldValue('fecha_desde');
				const fechaHasta = this.getFieldValue('fecha_hasta');
				let rows = this.data;
				if (search) {
					rows = rows.filter((r) =>
						(r.empleado || '').toLowerCase().includes(search) ||
						(r.empleado_nombre || '').toLowerCase().includes(search)
					);
				}
				if (fechaDesde) {
					rows = rows.filter((r) => r.fecha_aplicacion && r.fecha_aplicacion >= fechaDesde);
				}
				if (fechaHasta) {
					rows = rows.filter((r) => r.fecha_aplicacion && r.fecha_aplicacion <= fechaHasta);
				}
				this.render(rows);
			},
			error: (err) => this.renderError((err && err.message) || 'No pudimos cargar los traslados.'),
		});
	}

	applyTraslado(row) {
		frappe.confirm(
			__('¿Confirmar la aplicación del traslado {0}?', [row.name]),
			() => {
				frappe.call({
					method: 'hubgh.hubgh.page.bandeja_traslados_pdv.bandeja_traslados_pdv.apply_traslado_action',
					args: { traslado_name: row.name },
					callback: (response) => {
						const result = response.message || {};
						const msg = result.status === 'applied'
							? __('Traslado aplicado correctamente.')
							: __('El traslado ya fue procesado ({0}).', [result.reason || result.status]);
						frappe.show_alert({ message: msg, indicator: result.status === 'applied' ? 'green' : 'blue' });
						this.refresh();
					},
					error: (err) => {
						frappe.show_alert({ message: err.message || __('Error al aplicar el traslado.'), indicator: 'red' });
					},
				});
			}
		);
	}

	cancelTraslado(row) {
		const dialog = new frappe.ui.Dialog({
			title: __('Anular traslado'),
			fields: [
				{
					fieldname: 'motivo_anulacion',
					label: __('Motivo de anulación'),
					fieldtype: 'Small Text',
					reqd: 1,
					description: __('Mínimo 5 caracteres.'),
				},
			],
			primary_action_label: __('Confirmar anulación'),
			primary_action: (values) => {
				const motivo = (values.motivo_anulacion || '').trim();
				if (motivo.length < 5) {
					frappe.show_alert({ message: __('El motivo debe tener al menos 5 caracteres.'), indicator: 'red' });
					return;
				}
				frappe.call({
					method: 'hubgh.hubgh.page.bandeja_traslados_pdv.bandeja_traslados_pdv.cancel_traslado_action',
					args: {
						traslado_name: row.name,
						motivo: motivo,
					},
					callback: (response) => {
						dialog.hide();
						frappe.show_alert({ message: __('Traslado anulado correctamente.'), indicator: 'green' });
						this.refresh();
					},
					error: (err) => {
						frappe.show_alert({ message: err.message || __('Error al anular el traslado.'), indicator: 'red' });
					},
				});
			},
		});
		dialog.show();
	}

	canApplyNow(row) {
		if (row.estado !== 'Programado') return false;
		const today = frappe.datetime.get_today();
		return row.fecha_aplicacion && row.fecha_aplicacion <= today;
	}

	canCancel(row) {
		return row.estado === 'Programado';
	}

	render(rows) {
		const canManage = this.context && this.context.can_manage;
		const today = frappe.datetime.get_today();

		const tableRows = rows.length
			? rows.map((row) => {
				const actionButtons = canManage
					? `
						${this.canApplyNow(row)
							? `<button class="btn btn-xs btn-success btn-apply-traslado me-1" data-name="${frappe.utils.escape_html(row.name)}">Aplicar ahora</button>`
							: ''}
						${this.canCancel(row)
							? `<button class="btn btn-xs btn-danger btn-cancel-traslado" data-name="${frappe.utils.escape_html(row.name)}">Anular</button>`
							: ''}
					`.trim()
					: '<span class="text-muted">Solo lectura</span>';

				return `
					<tr>
						<td><a href="/app/traslado-pdv/${frappe.utils.escape_html(row.name)}">${frappe.utils.escape_html(row.name)}</a></td>
						<td>
							<strong>${frappe.utils.escape_html(row.empleado_nombre || row.empleado || '')}</strong>
							<br><small class="text-muted">${frappe.utils.escape_html(row.empleado || '')}</small>
						</td>
						<td>${frappe.utils.escape_html(row.pdv_origen || '-')}</td>
						<td>${frappe.utils.escape_html(row.pdv_destino || '-')}</td>
						<td>${this.formatDate(row.fecha_aplicacion)}</td>
						<td><span class="indicator-pill ${this.estadoColor(row.estado)}">${frappe.utils.escape_html(row.estado || '')}</span></td>
						<td>${frappe.utils.escape_html(row.motivo || '-')}</td>
						<td>${frappe.utils.escape_html(row.solicitado_por || '-')}</td>
						<td>${actionButtons}</td>
					</tr>
				`;
			}).join('')
			: '<tr><td colspan="9" class="text-muted text-center">No hay traslados visibles con los filtros actuales.</td></tr>';

		const html = `
			<div class="retirement-shell">
				<div class="retirement-hero">
					<div>
						<div class="retirement-kickers"><span>Operación</span><span>Traslados PDV</span></div>
						<h3>Bandeja Traslados PDV</h3>
						<p class="text-muted mb-0">Gestión centralizada de traslados de empleados entre Puntos de Venta.</p>
					</div>
				</div>
				<div class="retirement-table-card">
					<table class="table table-bordered">
						<thead>
							<tr>
								<th>ID</th>
								<th>Empleado</th>
								<th>PDV Origen</th>
								<th>PDV Destino</th>
								<th>Fecha aplicación</th>
								<th>Estado</th>
								<th>Motivo</th>
								<th>Solicitado por</th>
								<th>Acciones</th>
							</tr>
						</thead>
						<tbody>${tableRows}</tbody>
					</table>
				</div>
			</div>
		`;
		this.wrapper.find('.layout-main-section').html(html);

		// Bind action buttons
		this.wrapper.find('.btn-apply-traslado').on('click', (event) => {
			const name = $(event.currentTarget).data('name');
			const row = rows.find((r) => r.name === name);
			if (row) this.applyTraslado(row);
		});

		this.wrapper.find('.btn-cancel-traslado').on('click', (event) => {
			const name = $(event.currentTarget).data('name');
			const row = rows.find((r) => r.name === name);
			if (row) this.cancelTraslado(row);
		});
	}

	estadoColor(estado) {
		if (estado === 'Aplicado') return 'green';
		if (estado === 'Programado') return 'orange';
		if (estado === 'Anulado') return 'red';
		return 'gray';
	}

	formatDate(value) {
		return value ? frappe.datetime.str_to_user(value) : '-';
	}

	renderLoading(message) {
		this.wrapper.find('.layout-main-section').html(`<div class="text-muted p-4">${message}</div>`);
	}

	renderError(message) {
		this.wrapper.find('.layout-main-section').html(`<div class="alert alert-danger">${message}</div>`);
	}
}
