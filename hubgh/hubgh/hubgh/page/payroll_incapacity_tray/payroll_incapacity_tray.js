frappe.pages['payroll_incapacity_tray'].on_page_load = function(wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __('Nómina - Bandeja de incapacidades'),
		single_column: true,
	});

	new PayrollIncapacityTray(wrapper, page);
};

class PayrollIncapacityTray {
	constructor(wrapper, page) {
		this.wrapper = wrapper;
		this.$wrapper = $(wrapper);
		this.page = page;
		this.state = { items: [], summary: {} };
		this.make_filters();
		this.make_actions();
		this.refresh();
	}

	make_filters() {
		this.page.add_field({
			fieldname: 'search',
			label: __('Buscar persona o cédula'),
			fieldtype: 'Data',
			change: () => this.refresh(),
		});

		this.page.add_field({
			fieldname: 'status',
			label: __('Estado'),
			fieldtype: 'Select',
			options: '\nAbierta\nEn seguimiento\nCerrada',
			change: () => this.refresh(),
		});
	}

	make_actions() {
		this.page.set_primary_action(__('Actualizar datos'), () => this.refresh());
		this.page.add_action_item(__('Abrir aprobación final'), () => frappe.set_route('app', 'payroll_tp_tray'));
		this.page.add_action_item(__('Abrir revisión inicial'), () => frappe.set_route('app', 'payroll_tc_tray'));
	}

	get_filter_value(fieldname) {
		const field = this.page.fields_dict?.[fieldname];
		return field && typeof field.get_value === 'function' ? field.get_value() : null;
	}

	refresh() {
		frappe.call({
			method: 'hubgh.hubgh.page.payroll_incapacity_tray.payroll_incapacity_tray.get_page_data',
			args: {
				search: this.get_filter_value('search'),
				status: this.get_filter_value('status'),
				limit: 200,
			},
			callback: (r) => this.render(r.message || {}),
		});
	}

	render(data) {
		if (!data || data.status !== 'success') {
			this.$wrapper.find('.layout-main-section').html(`<div class="text-muted py-5">${__('No fue posible cargar la bandeja de incapacidades.')}</div>`);
			return;
		}

		this.state = data;
		const items = data.items || [];
		const summary = data.summary || {};
		const rows = items.map((item) => this.render_row(item)).join('');

		this.$wrapper.find('.layout-main-section').html(`
			<div class="payroll-incapacity-tray">
				<div class="incapacity-hero">
					<div>
						<div class="incapacity-kickers"><span>Nómina</span><span>Recobro</span></div>
						<h3 class="incapacity-title">Bandeja operativa de incapacidades</h3>
						<p class="incapacity-copy">Controlá incapacidades con soporte listo para recobro sin mezclar otras bandejas de nómina.</p>
					</div>
					<div class="incapacity-summary">
						<div class="incapacity-summary-card"><strong>${summary.total || 0}</strong><span>Incapacidades</span></div>
						<div class="incapacity-summary-card"><strong>${summary.with_evidence || 0}</strong><span>Con soporte</span></div>
						<div class="incapacity-summary-card"><strong>${summary.without_evidence || 0}</strong><span>Sin soporte</span></div>
					</div>
				</div>
				<div class="incapacity-table-shell">
					<table class="table table-bordered table-sm incapacity-table">
						<thead>
							<tr>
								<th>${__('Persona')}</th>
								<th>${__('Cédula')}</th>
								<th>${__('Fecha inicio')}</th>
								<th>${__('Fecha fin')}</th>
								<th>${__('Días')}</th>
								<th>${__('Estado')}</th>
								<th>${__('Soporte')}</th>
							</tr>
						</thead>
						<tbody>
							${rows || `<tr><td colspan="7" class="text-center text-muted py-4">${__('No hay incapacidades con los filtros actuales.')}</td></tr>`}
						</tbody>
					</table>
				</div>
			</div>
		`);

		this.$wrapper.find('.btn-download-evidence').on('click', (event) => {
			const url = $(event.currentTarget).data('url');
			if (url) {
				window.open(url, '_blank');
			}
		});
	}

	render_row(item) {
		const hasEvidence = Boolean(item.evidence_url);
		const downloadButton = hasEvidence
			? `<button class="btn btn-sm btn-default btn-download-evidence" data-url="${this.escape_html(item.evidence_url)}"><i class="fa fa-download"></i> ${__('Descargar')}</button><div class="text-muted small mt-1">${this.escape_html(item.evidence_source || '')}</div>`
			: `<span class="text-muted">${__('Sin soporte disponible')}</span>`;

		return `
			<tr>
				<td>
					<div class="font-weight-bold">${this.escape_html(item.persona || '')}</div>
					<div class="text-muted small">${this.escape_html(item.name || '')}</div>
				</td>
				<td>${this.escape_html(item.cedula || '')}</td>
				<td>${this.format_date(item.fecha_inicio)}</td>
				<td>${this.format_date(item.fecha_fin)}</td>
				<td>${frappe.format(item.dias_incapacidad || 0, { fieldtype: 'Int' })}</td>
				<td>${this.escape_html(item.estado || '')}</td>
				<td>${downloadButton}</td>
			</tr>
		`;
	}

	format_date(value) {
		return value ? frappe.datetime.str_to_user(value) : '';
	}

	escape_html(value) {
		return frappe.utils.escape_html(String(value || ''));
	}
}
