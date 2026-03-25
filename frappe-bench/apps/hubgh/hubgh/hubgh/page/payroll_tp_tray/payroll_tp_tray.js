/**
 * Payroll TP Tray Page - Frontend interface for TP approval workflow.
 * 
 * Executive dashboard for final payroll approval before Prenomina generation.
 * Features period selection, employee summaries, bulk approval, and export.
 */

frappe.pages['payroll_tp_tray'].on_page_load = function(wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Nómina - Aprobación final de prenómina',
		single_column: false
	});

	// Initialize page state
	page.tp_tray_data = {
		current_period: null,
		consolidation: null,
		selected_employees: new Set(),
		filters: {
			period: null,
			batch: null,
			jornada_type: 'Todas',
			show_approved: false
		}
	};

	// Create page layout
	page.setup_page_layout = function() {
		// Create main container
		page.main_container = $(frappe.render_template('tp_tray_main', {}))
			.appendTo(page.main);

		// Setup filters section
		page.setup_filters();
		
		// Setup executive summary section
		page.setup_executive_summary();
		
		// Setup employee consolidation table
		page.setup_employee_table();
		
		// Setup action buttons
		page.setup_action_buttons();
		
		// Load initial data
		page.load_page_data();
	};

	page.setup_filters = function() {
		// Period filter
		page.period_filter = frappe.ui.form.make_control({
			parent: page.main_container.find('.filters-section'),
			df: {
				fieldtype: 'Select',
				fieldname: 'period_filter',
				label: 'Período',
				placeholder: 'Seleccionar período...',
				onchange: function() {
					page.tp_tray_data.filters.period = this.get_value();
					page.tp_tray_data.filters.batch = null; // Reset batch filter
					page.refresh_data();
				}
			}
		});

		// Batch filter (secondary)
		page.batch_filter = frappe.ui.form.make_control({
			parent: page.main_container.find('.filters-section'),
			df: {
				fieldtype: 'Link',
				fieldname: 'batch_filter',
				label: 'Lote Específico',
				options: 'Payroll Import Batch',
				placeholder: 'Opcional: filtrar por lote...',
				onchange: function() {
					page.tp_tray_data.filters.batch = this.get_value();
					page.refresh_data();
				}
			}
		});

		page.jornada_filter = frappe.ui.form.make_control({
			parent: page.main_container.find('.filters-section'),
			df: {
				fieldtype: 'Select',
				fieldname: 'jornada_type',
				label: 'Tipo de jornada',
				options: 'Todas\nTiempo Completo\nTiempo Parcial',
				default: 'Todas',
				onchange: function() {
					page.tp_tray_data.filters.jornada_type = this.get_value() || 'Todas';
					page.refresh_data();
				}
			}
		});
		page.jornada_filter.refresh();
		page.jornada_filter.set_value('Todas');

		// Show approved toggle
		page.show_approved_filter = frappe.ui.form.make_control({
			parent: page.main_container.find('.filters-section'),
			df: {
				fieldtype: 'Check',
				fieldname: 'show_approved',
				label: 'Mostrar ya aprobados',
				onchange: function() {
					page.tp_tray_data.filters.show_approved = this.get_value();
					page.refresh_employee_table();
				}
			}
		});
	};

	page.setup_executive_summary = function() {
		page.summary_container = page.main_container.find('.executive-summary');
		// Summary will be populated by update_executive_summary()
	};

	page.setup_employee_table = function() {
		page.employee_table_container = page.main_container.find('.employee-table');
		
		// Create DataTable for employee consolidation
		page.employee_table = null; // Will be initialized in refresh_employee_table()
	};

	page.setup_action_buttons = function() {
		page.set_primary_action('Aprobar selección', function() {
			page.approve_selected_employees();
		});

		page.add_inner_button('Aprobar período o lote', function() {
			page.approve_entire_period();
		});

		page.add_inner_button('Generar prenómina', function() {
			page.generate_prenomina();
		});

		page.add_action_item('Actualizar datos', function() {
			page.refresh_data();
		}, true);

		page.add_action_item('Abrir revisión inicial', function() {
			frappe.set_route('app', 'payroll_tc_tray');
		});

		page.add_action_item('Ver lotes cargados', function() {
			frappe.set_route('List', 'Payroll Import Batch');
		});
	};

	page.isSuccessfulResponse = function(status) {
		return ['success', 'partial'].includes(status);
	};

	page.showOperationalEmptyState = function(config) {
		const defaults = {
			title: 'Todavía no hay personas listas para la aprobación final',
			message: 'Esta vista se alimenta cuando la revisión inicial deja novedades válidas y listas para cerrar el lote.',
			next_step: 'Próximo paso: revisá la bandeja de revisión inicial o los lotes cargados antes de volver acá.',
		};
		const state = Object.assign({}, defaults, config || {});
		page.employee_table_container.html(`
			<div class="text-center text-muted py-5 tp-empty-state">
				<h5>${state.title}</h5>
				<p class="mb-2">${state.message}</p>
				<p class="mb-4">${state.next_step}</p>
				<div class="d-flex justify-content-center flex-wrap" style="gap: 12px;">
					<button class="btn btn-primary go-tc-tray">Abrir revisión inicial</button>
					<button class="btn btn-default go-batches">Ver lotes cargados</button>
					<button class="btn btn-default go-liquidations">Abrir liquidaciones</button>
				</div>
			</div>
		`);

		page.employee_table_container.find('.go-tc-tray').on('click', function() {
			frappe.set_route('payroll_tc_tray');
		});
		page.employee_table_container.find('.go-batches').on('click', function() {
			frappe.set_route('List', 'Payroll Import Batch');
		});
		page.employee_table_container.find('.go-liquidations').on('click', function() {
			frappe.set_route('List', 'Payroll Liquidation Case');
		});
	};

	page.handleApprovalResponse = function(response, targetLabel) {
		if (!response || !page.isSuccessfulResponse(response.status)) {
			frappe.msgprint({
				title: 'Error en Aprobación',
				message: response?.message || `Error aprobando ${targetLabel}`,
				indicator: 'red'
			});
			return;
		}

		frappe.show_alert({
			message: response.status === 'partial'
				? `${targetLabel} aprobado con observaciones`
				: `${targetLabel} aprobado exitosamente`,
			indicator: response.status === 'partial' ? 'orange' : 'green'
		});

		if (response.prenomina_results && response.prenomina_results.length > 0) {
			page.show_prenomina_results(response.prenomina_results);
		}

		page.refresh_data();
	};

	page.resolveBatchForGeneration = function() {
		const explicitBatch = page.tp_tray_data.filters.batch;
		if (explicitBatch) {
			return explicitBatch;
		}

		const batches = page.tp_tray_data.consolidation?.period_summary?.batches || [];
		return batches.length === 1 ? batches[0] : null;
	};

	// Data loading and refresh
	page.load_page_data = function() {
		frappe.show_progress('Cargando datos TP...', 50);
		page.employee_table_container.html('<div class="table-loading">Cargando consolidado de prenómina...</div>');
		
		frappe.call({
			method: 'hubgh.hubgh.page.payroll_tp_tray.payroll_tp_tray.get_page_data',
			callback: function(r) {
				frappe.hide_progress();
				
				if (r.message && r.message.status === 'success') {
					// Update period options
					const periods = r.message.available_periods;
					page.period_filter.df.options = periods.join('\n');
					page.period_filter.refresh();
					
					// Set current period
					if (r.message.current_period) {
						page.tp_tray_data.current_period = r.message.current_period;
						page.period_filter.set_value(r.message.current_period);
					}
					
					// Update data
					page.tp_tray_data.consolidation = r.message.consolidation;
					page.update_ui_with_data();
					
					frappe.show_alert({
						message: 'Vista de aprobación final actualizada',
						indicator: 'green'
					});
				} else {
					frappe.msgprint({
						title: 'Error',
						message: r.message?.message || 'Error cargando datos TP',
						indicator: 'red'
					});
				}
			}
		});
	};

	page.refresh_data = function() {
		const period = page.tp_tray_data.filters.period;
		const batch = page.tp_tray_data.filters.batch;
		const jornada_type = page.tp_tray_data.filters.jornada_type || 'Todas';
		
		if (!period && !batch) {
			frappe.msgprint('Seleccione un período o lote para continuar.');
			return;
		}

		frappe.show_progress('Actualizando datos...', 70);
		
		frappe.call({
			method: 'hubgh.hubgh.page.payroll_tp_tray.payroll_tp_tray.refresh_period_data',
			args: {
				period: period,
				batch: batch,
				jornada_type: jornada_type
			},
			callback: function(r) {
				frappe.hide_progress();
				
				if (r.message && r.message.status === 'success') {
					page.tp_tray_data.consolidation = r.message;
					page.update_ui_with_data();
					
					frappe.show_alert({
						message: 'Datos actualizados',
						indicator: 'blue'
					});
				} else {
					frappe.msgprint({
						title: 'Error',
						message: r.message?.message || 'Error actualizando datos',
						indicator: 'red'
					});
				}
			}
		});
	};

	page.update_ui_with_data = function() {
		// Update executive summary
		page.update_executive_summary();
		
		// Update employee table
		page.refresh_employee_table();
		
		// Clear selections
		page.tp_tray_data.selected_employees.clear();
	};

	page.update_executive_summary = function() {
		const summary = page.tp_tray_data.consolidation?.executive_summary || {};
		const period_info = page.tp_tray_data.consolidation?.period_summary || {};
		const jornadaFilter = page.tp_tray_data.consolidation?.jornada_filter || 'Todas';
		const jornadaWarning = page.tp_tray_data.consolidation?.jornada_filter_warning;
		const selectedCount = page.tp_tray_data.selected_employees.size;
		
		const summary_html = `
			<div class="tp-summary-shell">
				<div class="tp-hero">
					<div>
						<div class="tp-kickers"><span>Nómina</span><span>Aprobación final</span></div>
						<h3 class="tp-hero-title">Cierre operativo antes de generar prenómina</h3>
						<p class="tp-hero-copy">Priorizá la selección visible, revisá montos clave y recién después generá la prenómina del lote.</p>
					</div>
					<div class="tp-hero-actions">
						<button class="btn btn-sm btn-primary tp-approve-selected">Aprobar selección</button>
						<button class="btn btn-sm btn-default tp-generate-prenomina">Generar prenómina</button>
					</div>
				</div>

				<div class="row tp-summary-grid">
					<div class="col-md-3">
						<div class="card text-center tp-summary-card">
							<div class="card-body">
								<h4 class="text-primary">${summary.total_employees || 0}</h4>
								<p class="text-muted">Personas consolidadas</p>
							</div>
						</div>
					</div>
					<div class="col-md-3">
						<div class="card text-center tp-summary-card">
							<div class="card-body">
								<h4 class="text-success">$${format_currency(summary.total_payroll_amount || 0)}</h4>
								<p class="text-muted">Valor neto estimado</p>
							</div>
						</div>
					</div>
					<div class="col-md-3">
						<div class="card text-center tp-summary-card">
							<div class="card-body">
								<h4 class="text-warning">${summary.employees_ready_for_approval || 0}</h4>
								<p class="text-muted">Listos para aprobar</p>
							</div>
						</div>
					</div>
					<div class="col-md-3">
						<div class="card text-center tp-summary-card">
							<div class="card-body">
								<h4 class="text-info">${selectedCount}</h4>
								<p class="text-muted">En la selección actual</p>
							</div>
						</div>
					</div>
				</div>
				
				<div class="row mt-3 tp-context-row">
					<div class="col-md-6">
						<h6>Estado de aprobación</h6>
						<div class="approval-status">
							<span class="badge badge-success">Listos: ${summary.approval_readiness?.ready || 0}</span>
							<span class="badge badge-warning">Pendientes: ${summary.approval_readiness?.needs_review || 0}</span>
							<span class="badge badge-danger">Con observaciones: ${summary.approval_readiness?.has_rejections || 0}</span>
						</div>
						<p class="text-muted mt-2 mb-0">La etapa final no cambia el contrato: ordena mejor qué aprobar primero y qué queda para revisión.</p>
					</div>
					<div class="col-md-6">
						<h6>Período: ${period_info.period_identifier || 'Sin Período'}</h6>
						<p class="text-muted">
							${period_info.unique_employees || 0} personas únicas,
							${period_info.total_lines || 0} líneas procesadas
						</p>
						<p class="mb-0"><strong>Tipo de jornada aplicado:</strong> ${jornadaFilter}</p>
					</div>
				</div>
				${jornadaWarning ? `<div class="alert alert-warning mt-3 mb-0">${jornadaWarning}</div>` : ''}
			</div>
		`;
		
		page.summary_container.html(summary_html);
		page.summary_container.find('.tp-approve-selected').on('click', function() {
			page.approve_selected_employees();
		});
		page.summary_container.find('.tp-generate-prenomina').on('click', function() {
			page.generate_prenomina();
		});
	};

	page.refresh_employee_table = function() {
		const employees = page.tp_tray_data.consolidation?.employee_consolidation || [];
		const show_approved = page.tp_tray_data.filters.show_approved;
		
		// Filter employees based on approval status
		const filtered_employees = employees.filter(emp => {
			if (show_approved) {
				return true; // Show all
			} else {
				return emp.overall_tp_status !== 'Aprobado'; // Hide already approved
			}
		});
		
		// Destroy existing table
		if (page.employee_table) {
			page.employee_table.destroy();
		}
		
		// Clear container
		page.employee_table_container.empty();
		
		if (filtered_employees.length === 0) {
			const hasEmployees = employees.length > 0;
			page.showOperationalEmptyState(hasEmployees
				? {
					title: 'No hay personas pendientes en la vista actual',
					message: show_approved
						? 'No encontramos registros para el filtro seleccionado.'
						: 'Todas las personas visibles ya quedaron aprobadas o rechazadas en la aprobación final.',
					next_step: show_approved
						? 'Probá cambiando el período o el lote para seguir con el flujo.'
						: 'Si necesitás volver a generar la prenómina, elegí un lote específico o revisá los lotes cargados.'
				}
				: null);
			return;
		}
		
		// Prepare table data
		const table_data = filtered_employees.map(emp => {
			const noveltySummary = Object.keys(emp.novelty_breakdown || {}).join(', ');
			return [
				`<input type="checkbox" class="employee-checkbox" data-employee-id="${emp.employee_id}" ${page.tp_tray_data.selected_employees.has(emp.employee_id) ? 'checked' : ''}>`,
				`<div class="tp-employee-name">${emp.employee_name || 'Sin nombre'}</div><div class="tp-employee-meta">${emp.employee_id || 'Sin documento'} · ${emp.tipo_jornada_display || 'Sin tipo de jornada'}</div>`,
				emp.employee_id || '',
					emp.tipo_jornada_display || 'Sin dato canónico en Ficha Empleado',
				noveltySummary || 'Sin novedades resumidas',
				format_currency(emp.total_devengado || 0),
				format_currency(emp.total_deducciones || 0),
				format_currency(emp.neto_a_pagar || 0),
				`<span class="badge badge-${get_status_badge_class(emp.overall_tp_status)}">${emp.overall_tp_status || 'Pendiente'}</span>`,
				`<button class="btn btn-sm btn-outline-primary view-detail" data-employee-id="${emp.employee_id}">Ver resumen</button>`
			];
		});
		
		// Create table HTML
		const table_html = `
			<div class="tp-table-head">
				<div>
					<div class="tp-table-title">Personas visibles para aprobación final</div>
					<div class="tp-table-copy">Mostrando ${filtered_employees.length} de ${employees.length} registros según filtros y estado.</div>
				</div>
			</div>
			<div class="tp-table-scroll">
			<table class="table table-striped employee-consolidation-table">
				<thead>
					<tr>
						<th><input type="checkbox" id="select-all-employees"></th>
						<th>Empleado</th>
						<th>ID</th>
						<th>Tipo de jornada</th>
						<th>Tipos de Novedad</th>
						<th>Total Devengado</th>
						<th>Total Deducciones</th>
						<th>Neto a Pagar</th>
						<th>Estado etapa TP</th>
						<th>Acciones</th>
					</tr>
				</thead>
				<tbody></tbody>
			</table>
			</div>
		`;
		
		page.employee_table_container.html(table_html);
		const table = page.employee_table_container.find('table')[0];
		
		// Initialize DataTable
		page.employee_table = $(table).DataTable({
			data: table_data,
			pageLength: 15,
			order: [[7, 'desc']],
			columnDefs: [
				{ orderable: false, targets: [0, 9] },
				{ className: 'text-right', targets: [5, 6, 7] }
			],
			language: {
				url: '/assets/frappe/js/lib/dataTables.spanish.json'
			}
		});
		
		// Setup event handlers
		page.setup_table_event_handlers();
	};

	page.setup_table_event_handlers = function() {
		// Select all checkbox
		$(document).off('change', '#select-all-employees').on('change', '#select-all-employees', function() {
			const checked = $(this).is(':checked');
			$('.employee-checkbox').prop('checked', checked);
			
			// Update selected set
			page.tp_tray_data.selected_employees.clear();
			if (checked) {
				$('.employee-checkbox').each(function() {
					const emp_id = $(this).data('employee-id');
					page.tp_tray_data.selected_employees.add(emp_id);
				});
			}
		});
		
		// Individual employee checkboxes
		$(document).off('change', '.employee-checkbox').on('change', '.employee-checkbox', function() {
			const emp_id = $(this).data('employee-id');
			
			if ($(this).is(':checked')) {
				page.tp_tray_data.selected_employees.add(emp_id);
			} else {
				page.tp_tray_data.selected_employees.delete(emp_id);
			}
			
			// Update select-all checkbox
			const total_checkboxes = $('.employee-checkbox').length;
			const checked_checkboxes = $('.employee-checkbox:checked').length;
			$('#select-all-employees').prop('checked', checked_checkboxes === total_checkboxes);
		});
		
		// View detail button
		$(document).off('click', '.view-detail').on('click', '.view-detail', function() {
			const emp_id = $(this).data('employee-id');
			page.show_employee_detail(emp_id);
		});
	};

	// Actions
	page.approve_selected_employees = function() {
		const selected = Array.from(page.tp_tray_data.selected_employees);
		
		if (selected.length === 0) {
			frappe.msgprint('Seleccione al menos un empleado para aprobar.');
			return;
		}
		
		frappe.prompt([
			{
				fieldname: 'comments',
				fieldtype: 'Text',
				label: 'Comentarios de Aprobación (Opcional)',
				placeholder: 'Ingrese comentarios sobre la aprobación...'
			}
		], function(values) {
			frappe.show_progress(`Aprobando ${selected.length} empleados...`, 80);
			
			frappe.call({
				method: 'hubgh.hubgh.page.payroll_tp_tray.payroll_tp_tray.approve_employees',
				args: {
					employee_ids: selected,
					comments: values.comments,
					jornada_type: page.tp_tray_data.filters.jornada_type || 'Todas'
				},
				callback: function(r) {
					frappe.hide_progress();
					
					page.handleApprovalResponse(r.message, 'Empleados seleccionados');
				}
			});
		}, 'Aprobar selección actual', 'Aprobar');
	};

	page.approve_entire_period = function() {
		const period = page.tp_tray_data.filters.period;
		const batch = page.tp_tray_data.filters.batch;
		
		if (!period && !batch) {
			frappe.msgprint('Seleccione un período o lote para aprobar.');
			return;
		}
		
		const target = batch || period;
		const target_type = batch ? 'lote' : 'período';
		
		frappe.confirm(
			`¿Está seguro de aprobar todo el ${target_type} "${target}"? Esta acción generará las prenóminas correspondientes.`,
			function() {
				frappe.prompt([
					{
						fieldname: 'comments',
						fieldtype: 'Text',
						label: 'Comentarios de Aprobación (Opcional)',
						placeholder: 'Ingrese comentarios sobre la aprobación masiva...'
					}
				], function(values) {
					frappe.show_progress(`Aprobando ${target_type} completo...`, 90);
					
					frappe.call({
						method: 'hubgh.hubgh.page.payroll_tp_tray.payroll_tp_tray.approve_period',
						args: {
							period: period,
							batch: batch,
							comments: values.comments,
							jornada_type: page.tp_tray_data.filters.jornada_type || 'Todas'
						},
						callback: function(r) {
							frappe.hide_progress();
							
							page.handleApprovalResponse(r.message, `${target_type.toUpperCase()} ${target}`);
						}
					});
				}, `Aprobar ${target_type.toUpperCase()} "${target}"`, 'Aprobar');
			}
		);
	};

	page.generate_prenomina = function() {
		const batch = page.resolveBatchForGeneration();
		
		if (!batch) {
			frappe.msgprint('Seleccione un lote específico para generar la prenómina. Si el período tiene un solo lote, la bandeja lo toma automáticamente.');
			return;
		}
		
		frappe.show_progress('Generando prenómina...', 95);
		
		frappe.call({
			method: 'hubgh.hubgh.page.payroll_tp_tray.payroll_tp_tray.generate_prenomina',
			args: {
				batch_name: batch,
				jornada_type: page.tp_tray_data.filters.jornada_type || 'Todas'
			},
			callback: function(r) {
				frappe.hide_progress();
				
				if (r.message && r.message.status === 'success') {
					frappe.show_alert({
						message: 'Prenómina generada exitosamente',
						indicator: 'green'
					});
					
					// Show download link
					page.show_prenomina_download(r.message);
				} else {
					frappe.msgprint({
						title: 'Error',
						message: r.message?.message || 'Error generando prenómina',
						indicator: 'red'
					});
				}
			}
		});
	};

	page.show_employee_detail = function(employee_id) {
		// Find employee data
		const employees = page.tp_tray_data.consolidation?.employee_consolidation || [];
		const employee = employees.find(emp => emp.employee_id === employee_id);
		
		if (!employee) {
			frappe.msgprint('No se encontraron datos del empleado.');
			return;
		}
		
		// Create detail dialog
		const dialog = new frappe.ui.Dialog({
			title: `Resumen de liquidación: ${employee.employee_name}`,
			size: 'large',
			fields: [
				{
					fieldtype: 'HTML',
					fieldname: 'employee_detail',
					options: page.get_employee_detail_html(employee)
				}
			],
			primary_action_label: 'Cerrar',
			primary_action: function() {
				dialog.hide();
			}
		});
		
		dialog.show();
	};

	page.get_employee_detail_html = function(employee) {
		const novelty_rows = Object.entries(employee.novelty_breakdown || {}).map(([type, data]) => {
			return `
				<tr>
					<td>${type}</td>
					<td class="text-right">${data.quantity || 0}</td>
					<td class="text-right">$${format_currency(data.amount || 0)}</td>
					<td class="text-right">${data.line_count || 0}</td>
				</tr>
			`;
		}).join('');
		
		return `
			<div class="employee-detail">
				<div class="row">
					<div class="col-md-6">
						<h6>Información General</h6>
						<table class="table table-sm">
							<tr><td><strong>Ficha canónica:</strong></td><td>${employee.matched_employee || employee.employee_id}</td></tr>
							<tr><td><strong>DocType:</strong></td><td>${employee.matched_employee_doctype || 'Ficha Empleado'}</td></tr>
							<tr><td><strong>Nombre:</strong></td><td>${employee.employee_name}</td></tr>
						<tr><td><strong>Tipo de jornada:</strong></td><td>${employee.tipo_jornada_display || 'Sin dato canónico en Ficha Empleado'}</td></tr>
						<tr><td><strong>Estado etapa TP:</strong></td><td><span class="badge badge-${get_status_badge_class(employee.overall_tp_status)}">${employee.overall_tp_status}</span></td></tr>
							<tr><td><strong>Lotes:</strong></td><td>${(employee.batches || []).join(', ')}</td></tr>
						</table>
					</div>
					<div class="col-md-6">
						<h6>Totales Financieros</h6>
						<table class="table table-sm">
							<tr><td><strong>Total Devengado:</strong></td><td class="text-right">$${format_currency(employee.total_devengado || 0)}</td></tr>
							<tr><td><strong>Total Deducciones:</strong></td><td class="text-right">$${format_currency(employee.total_deducciones || 0)}</td></tr>
							<tr><td><strong>Auxilios:</strong></td><td class="text-right">$${format_currency(employee.auxilios_total || 0)}</td></tr>
							<tr><td><strong>Recargos:</strong></td><td class="text-right">$${format_currency(Object.values(employee.recargos || {}).reduce((a, b) => a + b, 0))}</td></tr>
							<tr class="table-success"><td><strong>Neto a Pagar:</strong></td><td class="text-right"><strong>$${format_currency(employee.neto_a_pagar || 0)}</strong></td></tr>
						</table>
					</div>
				</div>
				
				<h6>Desglose por Tipo de Novedad</h6>
				<table class="table table-striped table-sm">
					<thead>
						<tr>
							<th>Tipo de Novedad</th>
							<th class="text-right">Cantidad</th>
							<th class="text-right">Monto</th>
							<th class="text-right">Líneas</th>
						</tr>
					</thead>
					<tbody>
						${novelty_rows}
					</tbody>
				</table>
				
				<div class="row mt-3">
					<div class="col-md-6">
						<h6>Horas Trabajadas</h6>
						<table class="table table-sm">
							<tr><td>Horas Diurnas:</td><td class="text-right">${employee.hour_totals?.HD || 0}</td></tr>
							<tr><td>Horas Nocturnas:</td><td class="text-right">${employee.hour_totals?.HN || 0}</td></tr>
							<tr><td>Extras Diurnas:</td><td class="text-right">${employee.hour_totals?.HED || 0}</td></tr>
							<tr><td>Extras Nocturnas:</td><td class="text-right">${employee.hour_totals?.HEN || 0}</td></tr>
						</table>
					</div>
					<div class="col-md-6">
						<h6>Recargos Calculados</h6>
						<table class="table table-sm">
							<tr><td>Recargo Nocturno:</td><td class="text-right">$${format_currency(employee.recargos?.nocturnal_amount || 0)}</td></tr>
							<tr><td>Recargo Dominical:</td><td class="text-right">$${format_currency(employee.recargos?.dominical_amount || 0)}</td></tr>
							<tr><td>Horas Extras:</td><td class="text-right">$${format_currency(employee.recargos?.extra_hours_amount || 0)}</td></tr>
						</table>
					</div>
				</div>
			</div>
		`;
	};

	page.show_prenomina_results = function(results) {
		const results_html = results.map(result => {
			const status_class = result.prenomina_status === 'success' ? 'text-success' : 'text-danger';
			const download_link = result.prenomina_status === 'success' && result.file_path ? 
				`<br><a href="#" class="download-prenomina" data-file-path="${result.file_path}">Descargar Prenómina</a>` : '';
			
			return `
				<div class="prenomina-result mb-2">
					<strong>${result.batch}:</strong> 
					<span class="text-muted">[${result.jornada_filter || 'Todas'}]</span>
					<br>
					<span class="${status_class}">${result.message}</span>
					${download_link}
				</div>
			`;
		}).join('');
		
		const dialog = new frappe.ui.Dialog({
			title: 'Resultados de generación de prenómina',
			fields: [
				{
					fieldtype: 'HTML',
					fieldname: 'results',
					options: `<div class="prenomina-results">${results_html}</div>`
				}
			],
			primary_action_label: 'Cerrar',
			primary_action: function() {
				dialog.hide();
			}
		});
		
		dialog.show();
		
		// Setup download handlers
		$(dialog.body).on('click', '.download-prenomina', function(e) {
			e.preventDefault();
			const file_path = $(this).data('file-path');
			page.download_prenomina_file(file_path);
		});
	};

	page.show_prenomina_download = function(prenomina_data) {
		frappe.msgprint({
			title: 'Prenómina generada',
			message: `
				<p><strong>Archivo:</strong> ${prenomina_data.batch_name}</p>
				<p><strong>Empleados:</strong> ${prenomina_data.employee_count}</p>
				<p><strong>Período:</strong> ${prenomina_data.period}</p>
				<p><strong>Tipo de jornada:</strong> ${prenomina_data.jornada_filter || 'Todas'}</p>
				<br>
				<button class="btn btn-primary download-prenomina-btn" data-file-path="${prenomina_data.file_path}">
					Descargar Prenómina Excel
				</button>
			`,
			indicator: 'green'
		});
		
		// Setup download handler
		$(document).off('click', '.download-prenomina-btn').on('click', '.download-prenomina-btn', function() {
			const file_path = $(this).data('file-path');
			page.download_prenomina_file(file_path);
		});
	};

	page.download_prenomina_file = function(file_path) {
		if (!file_path) {
			frappe.msgprint({
				title: 'Error',
				message: 'No encontramos la ruta del archivo de prenómina para descargar.',
				indicator: 'red'
			});
			return;
		}

		const query = $.param({ file_path: file_path });
		window.open(`/api/method/hubgh.hubgh.payroll_export_prenomina.download_prenomina_file?${query}`, '_blank');
		frappe.show_alert({
			message: 'Descarga solicitada en una nueva pestaña',
			indicator: 'blue'
		});
	};

	// Initialize page
	page.setup_page_layout();
};

// Helper functions
function format_currency(amount) {
	return new Intl.NumberFormat('es-CO', {
		minimumFractionDigits: 0,
		maximumFractionDigits: 0
	}).format(amount || 0);
}

function get_status_badge_class(status) {
	const status_map = {
		'Pendiente': 'secondary',
		'Revisado': 'warning', 
		'Aprobado': 'success',
		'Rechazado': 'danger'
	};
	return status_map[status] || 'secondary';
}

// Template for main page structure
frappe.templates['tp_tray_main'] = `
<div class="tp-tray-main">
	<div class="filters-section mb-4">
		<div class="row align-items-end">
			<div class="col-md-6">
				<h5>Filtros para la aprobación final</h5>
				<p class="text-muted mb-0">Elegí período, lote y tipo de jornada sin romper el flujo operativo entre revisión inicial y prenómina.</p>
			</div>
			<div class="col-md-6">
				<div class="tp-filter-help">TC y TP siguen siendo etapas operativas; el tipo de jornada sale de Ficha Empleado.</div>
			</div>
		</div>
	</div>
	
	<div class="executive-summary mb-4">
		<!-- Executive summary will be populated dynamically -->
	</div>
	
	<div class="employee-table mb-4">
		<h5>Personas para aprobación final</h5>
		<!-- Employee table will be populated dynamically -->
	</div>
</div>
`;
