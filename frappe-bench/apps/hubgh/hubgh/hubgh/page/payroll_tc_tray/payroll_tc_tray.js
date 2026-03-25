frappe.pages['payroll_tc_tray'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __('Nómina - Revisión inicial de novedades'),
		single_column: true
	});

	wrapper.tc_tray = new PayrollTCTray(wrapper, page);
};

class PayrollTCTray {
    constructor(wrapper, page) {
        this.wrapper = wrapper;
        this.page = page;
        this.page.start = 0;
        
        this.make_filters();
        this.make_actions();
        this.refresh();
    }
    
    make_filters() {
        // Batch filter
        this.page.add_field({
            fieldname: "batch",
            label: __("Lote"),
            fieldtype: "Link",
            options: "Payroll Import Batch",
            reqd: 0,
            change: () => this.refresh()
        });
        
		// Operational-stage status filter
		this.page.add_field({
			fieldname: "status",
			label: __("Estado de revisión inicial"),
            fieldtype: "Select",
            options: "\nPendiente\nRevisado\nAprobado\nRechazado",
            reqd: 0,
            change: () => this.refresh()
        });
        
        // Employee filter
        this.page.add_field({
            fieldname: "employee",
            label: __("Empleado"),
            fieldtype: "Data",
            reqd: 0,
            change: () => this.refresh()
        });
        
        // Period filter
        this.page.add_field({
            fieldname: "period",
            label: __("Período"),
            fieldtype: "Link",
            options: "Payroll Period Config",
            reqd: 0,
            change: () => this.refresh()
        });
    }
    
	make_actions() {
		this.page.set_primary_action(__("Aprobar selección"), () => {
			this.bulk_approve();
		});

		this.page.add_inner_button(__("Rechazar selección"), () => {
			this.bulk_reject();
		});
		
		this.page.add_action_item(__("Abrir aprobación final"), () => {
			frappe.set_route('app', 'payroll_tp_tray');
		});

		this.page.add_action_item(__("Ver lotes cargados"), () => {
			frappe.set_route('List', 'Payroll Import Batch');
		});
        
		this.page.add_action_item(__("Actualizar datos"), () => {
            this.refresh();
        });
	}

	get_filter_value(fieldname) {
		const field = (this.page.fields_dict && this.page.fields_dict[fieldname]) || null;
		return field && typeof field.get_value === 'function' ? field.get_value() : null;
	}
    
    refresh() {
        var me = this;
        var filters = {
            batch: me.get_filter_value('batch'),
            status: me.get_filter_value('status'),
            employee: me.get_filter_value('employee'),
            period: me.get_filter_value('period')
        };
        
		frappe.call({
			method: "hubgh.hubgh.page.payroll_tc_tray.payroll_tc_tray.get_consolidated_view",
			args: { filters: JSON.stringify(filters) },
			callback: function(r) {
				me.render(r.message || {});
			}
		});
    }
    
    render(data) {
		if (!data || !data.total_lines) {
			this.render_empty_state(data || {});
			return;
		}
        
		var summary_html = `
			<div class="payroll-tc-tray">
				<div class="tc-hero">
					<div>
						<div class="tc-kickers"><span>Nómina</span><span>Revisión inicial</span></div>
						<h3 class="tc-hero-title">Revisión inicial de novedades cargadas</h3>
						<p class="tc-hero-copy">Revisá novedades por lote, aprobá rápido lo que está listo y dejá visible qué pasa a la aprobación final.</p>
					</div>
					<div class="tc-hero-actions">
						<button class="btn btn-sm btn-primary tc-go-upload">Cargar novedades</button>
						<button class="btn btn-sm btn-default tc-go-tp">Abrir aprobación final</button>
					</div>
				</div>
				<div class="row tc-summary-row">
	                <div class="col-md-3">
	                    <div class="card tc-summary-card">
	                        <div class="card-body text-center">
	                            <h3>${data.total_employees || 0}</h3>
	                            <div class="text-muted">Personas alcanzadas</div>
	                        </div>
	                    </div>
	                </div>
	                <div class="col-md-3">
	                    <div class="card tc-summary-card">
	                        <div class="card-body text-center">
	                            <h3>${data.total_lines || 0}</h3>
	                            <div class="text-muted">Novedades cargadas</div>
	                        </div>
	                    </div>
	                </div>
	                <div class="col-md-3">
	                    <div class="card tc-summary-card">
	                        <div class="card-body text-center">
	                            <h3>${data.pending_count || 0}</h3>
	                            <div class="text-muted">Pendientes de revisión</div>
	                        </div>
	                    </div>
	                </div>
	                <div class="col-md-3">
	                    <div class="card tc-summary-card">
	                        <div class="card-body text-center">
	                            <h3>${data.ready_count || 0}</h3>
							<div class="text-muted">Listos para aprobación final</div>
	                        </div>
	                    </div>
	                </div>
            </div>
				</div>
		`;
        
		var table_html = `
			<div class="mt-4 tc-table-shell">
				<div class="tc-table-head">
					<div>
						<div class="tc-table-title">Novedades listas para revisar</div>
						<div class="tc-table-copy">Usá la selección masiva para priorizar lotes sin perder el estado de cada novedad.</div>
					</div>
					<div class="tc-selection-summary">
						<span class="tc-selected-count">0 seleccionadas</span>
						<div class="tc-selection-actions">
							<button class="btn btn-sm btn-primary tc-bulk-approve">Aprobar selección</button>
							<button class="btn btn-sm btn-default tc-bulk-reject">Rechazar selección</button>
						</div>
					</div>
				</div>
				<div class="tc-table-scroll">
				<table class="table table-bordered table-sm tc-compact-table">
                    <thead class="thead-dark">
                        <tr>
                            <th style="width: 30px;"><input type="checkbox" id="select-all"></th>
                            <th>Empleado</th>
                            <th>Documento</th>
                            <th>Tipo Novedad</th>
                            <th>Cantidad</th>
							<th>Estado etapa TC</th>
                            <th>Regla Aplicada</th>
                            <th>Acciones</th>
                        </tr>
                    </thead>
                    <tbody>
        `;
        
        if (data.employees && data.employees.length > 0) {
            data.employees.forEach(function(emp) {
                emp.lines.forEach(function(line) {
                    var status_color = {
                        'Pendiente': 'warning',
                        'Revisado': 'info',
                        'Aprobado': 'success',
                        'Rechazado': 'danger'
                    };
                    
                    table_html += `
						<tr data-name="${line.name}">
							<td><input type="checkbox" class="row-checkbox"></td>
							<td>
								<div class="tc-employee-name">${line.employee_name || '-'}</div>
								<div class="tc-employee-meta">Documento ${line.employee_id || '-'}</div>
							</td>
							<td>${line.employee_id || '-'}</td>
							<td>${line.novedad_type || '-'}</td>
							<td>${line.quantity || 0}</td>
							<td><span class="badge badge-${status_color[line.tc_status] || 'secondary'}">${line.tc_status || 'Pendiente'}</span></td>
							<td><small>${line.rule_applied || '-'}</small></td>
							<td class="tc-row-actions">
								<button class="btn btn-sm btn-success btn-approve" data-name="${line.name}">Aprobar</button>
								<button class="btn btn-sm btn-outline-danger btn-reject" data-name="${line.name}">Rechazar</button>
							</td>
						</tr>
                    `;
                });
            });
        } else {
            table_html += `
                <tr>
                    <td colspan="8" class="text-center text-muted">No hay datos</td>
                </tr>
            `;
        }
        
			        table_html += '</tbody></table></div></div>';
		        
			table_html += `</div>`;
		this.page.main.html(summary_html + table_html);
		this.setup_event_handlers();
		this.wrapper.find('.tc-go-upload').on('click', function() { frappe.set_route('app', 'payroll_import_upload'); });
		this.wrapper.find('.tc-go-tp').on('click', function() { frappe.set_route('app', 'payroll_tp_tray'); });
    }

	render_empty_state(data) {
		const emptyState = data.empty_state || {};
		const summaryHtml = `
			<div class="payroll-tc-tray">
				<div class="tc-hero">
					<div>
						<div class="tc-kickers"><span>Nómina</span><span>Revisión inicial</span></div>
						<h3 class="tc-hero-title">Revisión inicial de novedades cargadas</h3>
						<p class="tc-hero-copy">Todavía no hay novedades listas para revisar. El siguiente paso es cargar un archivo o abrir el historial de lotes.</p>
					</div>
					<div class="tc-hero-actions">
						<button class="btn btn-sm btn-primary go-upload">Cargar novedades</button>
						<button class="btn btn-sm btn-default go-batches">Ver lotes cargados</button>
					</div>
				</div>
			<div class="row">
				<div class="col-md-3"><div class="card tc-summary-card"><div class="card-body text-center"><h3>0</h3><div class="text-muted">Personas alcanzadas</div></div></div></div>
				<div class="col-md-3"><div class="card tc-summary-card"><div class="card-body text-center"><h3>0</h3><div class="text-muted">Novedades cargadas</div></div></div></div>
				<div class="col-md-3"><div class="card tc-summary-card"><div class="card-body text-center"><h3>0</h3><div class="text-muted">Pendientes de revisión</div></div></div></div>
				<div class="col-md-3"><div class="card tc-summary-card"><div class="card-body text-center"><h3>0</h3><div class="text-muted">Listos para aprobación final</div></div></div></div>
			</div>
			</div>
		`;

		const emptyHtml = `
			<div class="card mt-4">
				<div class="card-body text-center p-5">
					<h4>${emptyState.title || __('No hay novedades de revisión inicial para mostrar')}</h4>
					<p class="text-muted mb-2">${emptyState.message || __('Esta bandeja se alimenta desde lotes procesados.')}</p>
					<p class="text-muted mb-4">${emptyState.next_step || __('Próximo paso: cargá novedades y volvé cuando el lote termine de procesarse.')}</p>
					<div class="d-flex justify-content-center gap-2 flex-wrap">
						<button class="btn btn-primary go-upload">${__('Cargar novedades')}</button>
						<button class="btn btn-default go-batches">${__('Ver lotes cargados')}</button>
					</div>
				</div>
			</div>
		`;

		this.page.main.html(summaryHtml + emptyHtml);
		this.wrapper.find('.go-upload').on('click', function() {
			frappe.set_route('payroll_import_upload');
		});
		this.wrapper.find('.go-batches').on('click', function() {
			frappe.set_route('List', 'Payroll Import Batch');
		});
	}
    
    setup_event_handlers() {
        var me = this;
        
        // Select all checkbox
        this.wrapper.find('#select-all').on('change', function() {
            var checked = $(this).prop('checked');
            me.wrapper.find('.row-checkbox').prop('checked', checked);
			me.update_selection_summary();
        });

		this.wrapper.find('.row-checkbox').on('change', function() {
			me.update_selection_summary();
		});

		this.wrapper.find('.tc-bulk-approve').on('click', function() {
			me.bulk_approve();
		});

		this.wrapper.find('.tc-bulk-reject').on('click', function() {
			me.bulk_reject();
		});
        
        // Individual approve buttons
        this.wrapper.find('.btn-approve').on('click', function() {
            var name = $(this).data('name');
            me.approve_single(name);
        });
        
        // Individual reject buttons
        this.wrapper.find('.btn-reject').on('click', function() {
            var name = $(this).data('name');
            me.reject_single(name);
        });

		this.update_selection_summary();
    }

	update_selection_summary() {
		const selectedCount = this.get_selected_lines().length;
		this.wrapper.find('.tc-selected-count').text(`${selectedCount} seleccionadas`);
	}
    
    get_selected_lines() {
        var selected = [];
        this.wrapper.find('.row-checkbox:checked').each(function() {
            selected.push($(this).closest('tr').data('name'));
        });
        return selected;
    }
    
    bulk_approve() {
        var me = this;
        var selected = this.get_selected_lines();
        
        if (selected.length === 0) {
            frappe.msgprint(__('Seleccione al menos una línea'));
            return;
        }
        
        frappe.call({
            method: "hubgh.hubgh.page.payroll_tc_tray.payroll_tc_tray.approve_lines",
            args: { line_names: JSON.stringify(selected) },
            callback: function(r) {
                if (r.message && r.message.success) {
                    frappe.msgprint(__('Líneas aprobadas exitosamente'));
                    me.refresh();
                } else {
                    frappe.msgprint(__('Error al aprobar líneas'));
                }
            }
        });
    }
    
    bulk_reject() {
        var me = this;
        var selected = this.get_selected_lines();
        
        if (selected.length === 0) {
            frappe.msgprint(__('Seleccione al menos una línea'));
            return;
        }
        
        frappe.call({
            method: "hubgh.hubgh.page.payroll_tc_tray.payroll_tc_tray.reject_lines",
            args: { line_names: JSON.stringify(selected) },
            callback: function(r) {
                if (r.message && r.message.success) {
                    frappe.msgprint(__('Líneas rechazadas'));
                    me.refresh();
                } else {
                    frappe.msgprint(__('Error al rechazar líneas'));
                }
            }
        });
    }
    
    approve_single(name) {
        var me = this;
        frappe.call({
            method: "hubgh.hubgh.page.payroll_tc_tray.payroll_tc_tray.approve_lines",
            args: { line_names: JSON.stringify([name]) },
            callback: function(r) {
                if (r.message && r.message.success) {
                    frappe.msgprint(__('Línea aprobada'));
                    me.refresh();
                }
            }
        });
    }
    
    reject_single(name) {
        var me = this;
        frappe.call({
            method: "hubgh.hubgh.page.payroll_tc_tray.payroll_tc_tray.reject_lines",
            args: { line_names: JSON.stringify([name]) },
            callback: function(r) {
                if (r.message && r.message.success) {
                    frappe.msgprint(__('Línea rechazada'));
                    me.refresh();
                }
            }
        });
    }
}
