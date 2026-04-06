
frappe.pages['persona_360'].on_page_load = function (wrapper) {
	injectPersona360Styles();
    var page = frappe.ui.make_app_page({
        parent: wrapper,
		title: 'Persona 360 - Vista integral',
        single_column: true
    });

    // NAVIGATION
    if (page.clear_breadcrumbs) {
        page.clear_breadcrumbs();
    }
    if (page.add_breadcrumb_item) {
        page.add_breadcrumb_item("Inicio", function () {
            frappe.set_route('app');
        });
    }

	page.add_inner_button('Volver al listado', function () {
        page._suppress_render = true;
        page.fields_dict.empleado.set_value('');
        render_overview(page);
    });

    page.add_field({
        fieldname: 'empleado',
		label: 'Persona',
        fieldtype: 'Link',
        options: 'Ficha Empleado',
        change: function () {
            if (page._suppress_render) {
                page._suppress_render = false;
                return;
            }
            if (!page.fields_dict.empleado.get_value()) {
                render_overview(page);
                return;
            }
            render_persona(page);
        }
    });

    page.add_field({
        fieldname: 'empleado_buscar',
        label: 'Buscar en listado',
        fieldtype: 'Data',
        placeholder: 'Nombre, cédula o punto…',
        change: function () {
            page._emp_filter = page.fields_dict.empleado_buscar.get_value() || '';
            if (!page.fields_dict.empleado.get_value()) {
                render_overview(page);
            }
        }
    });

    $(page.body).off('click', '.emp-card').on('click', '.emp-card', function () {
        const empId = $(this).data('emp');
        if (!empId) return;
        page.fields_dict.empleado.set_value(empId);
    });

    // Check for URL parameters to pre-fill
    if (frappe.route_options && frappe.route_options.empleado) {
        page.fields_dict.empleado.set_value(frappe.route_options.empleado);
        frappe.route_options = null;
    }

    $(wrapper).bind('show', function () {
        if (frappe.route_options && frappe.route_options.empleado) {
            page.fields_dict.empleado.set_value(frappe.route_options.empleado);
            frappe.route_options = null;
        } else if (!page.fields_dict.empleado.get_value()) {
            render_overview(page);
        }
    });

    if (!page.fields_dict.empleado.get_value()) {
        render_overview(page);
    }
}

function render_overview(page) {
    clear_contextual_action_buttons(page);
    frappe.call({
        method: "hubgh.hubgh.page.persona_360.persona_360.get_all_personas_overview",
        callback: function (r) {
            if (r.message) {
                const personas = r.message;
                const filter_text = (page._emp_filter || '').toLowerCase();
                const filtered = personas.filter(p => {
                    const nombre = (p.full_name || '').toLowerCase();
                    const cedula = (p.cedula || '').toLowerCase();
                    const pdv = (p.pdv_nombre || '').toLowerCase();
                    return !filter_text || nombre.includes(filter_text) || cedula.includes(filter_text) || pdv.includes(filter_text);
                });

                let $container = $(page.main || page.body);
                $container.empty();
				let html = `
					<div class="persona360-shell">
						<div class="persona360-overview-header">
							<div>
								<div class="persona360-kickers"><span>People Ops</span><span>Vista general</span></div>
								<h4>Personas activas</h4>
								<p class="text-muted">Buscá por persona, cédula o punto y abrí el detalle operativo sin perder contexto.</p>
							</div>
							<div class="persona360-overview-count">${filtered.length} visibles</div>
						</div>
						<div class="row" style="padding: 20px; padding-top: 8px;">
                        <div class="col-md-12">
							<hr style="margin-top: 0;">
                        </div>
                        <div class="col-md-12">
                            <div class="persona360-employee-list-scroll">
                                <div class="row" style="margin: 0;">
                                    ${filtered.map(p => `
                                        <div class="col-md-4" style="padding-left: 8px; padding-right: 8px;">
											<div class="emp-card persona360-overview-card" data-emp="${p.name}">
												<div class="persona360-card-name">${p.full_name}</div>
												<div class="text-muted small">${p.cargo || 'Sin cargo'} · ${p.pdv_nombre || 'Sin punto'}</div>
												<div class="text-muted small">Documento ${p.cedula || '-'}</div>
												<div class="d-flex justify-content-between text-muted small mt-2 persona360-card-metrics">
													<span>Novedades: ${p.novedades}</span>
													<span>Bienestar: ${p.feedback_count}</span>
												</div>
												${p.feedback_last ? `<div class="text-muted small mt-2">“${p.feedback_last}”</div>` : ''}
											</div>
                                        </div>
                                    `).join('')}
                                    ${filtered.length === 0 ? '<div class="col-md-12"><p class="text-muted">Sin resultados</p></div>' : ''}
                                </div>
                            </div>
                        </div>
						</div>
					</div>
                `;
                $container.append(html);
            }
        }
    });
}

function render_persona(page) {
    let emp_id = page.fields_dict.empleado.get_value();
    if (!emp_id) return;

    frappe.call({
        method: "hubgh.hubgh.page.persona_360.persona_360.get_persona_stats",
        args: { employee_id: emp_id },
        callback: function (r) {
            if (r.message) {
                let data = r.message;
                let info = data.info;
                let timeline = data.timeline;
                let sst = data.sst_cards || {};
				let contextual_actions = data.contextual_actions || {};
                let payroll_block = data.payroll_block || {};

				clear_contextual_action_buttons(page);

                let $container = $(page.main || page.body);
                $container.empty();

                let status_color = {
                    "Activo": "green",
                    "Inactivo": "red",
                    "Vacaciones": "blue",
                    "Incapacitado": "orange",
                    "Licencia": "orange",
                    "Suspensión": "orange",
                    "Separación del Cargo": "orange",
                    "Recomendación Médica": "orange",
                    "Embarazo": "orange",
                    "Retirado": "red"
                }[info.estado] || "gray";

				let html = `
					<div class="persona360-shell persona360-detail-shell">
						<div class="persona360-detail-header dashboard-section p-4">
							<div class="persona360-detail-header-main">
								<div class="persona360-kickers"><span>Persona 360</span><span>Vista integral</span></div>
								<h3>${info.nombres} ${info.apellidos}</h3>
								<p class="text-muted mb-2">${info.cargo || 'Sin cargo'} · ${info.pdv_nombre || 'Sin punto asignado'}</p>
								<div class="persona360-detail-meta">
									<span class="indicator-pill ${status_color}">${info.estado}</span>
									<span>Ingreso ${frappe.datetime.str_to_user(info.fecha_ingreso)}</span>
									<span>Documento ${info.cedula}</span>
								</div>
							</div>
							<div class="persona360-quick-actions">
								<div class="persona360-quick-actions-title">Acciones rápidas</div>
								<div class="persona360-quick-actions-body">
									${render_contextual_actions_panel(contextual_actions)}
								</div>
							</div>
						</div>
						<div class="row">
                        <div class="col-md-12" style="margin-bottom: 15px;">
                            <div class="row">
                                <div class="col-md-3"><div class="dashboard-card-stat"><span class="stat-label">AT activos</span><span class="stat-val">${sst.at_activos || 0}</span></div></div>
                                <div class="col-md-3"><div class="dashboard-card-stat"><span class="stat-label">Incapacidades activas</span><span class="stat-val">${sst.incapacidades_activas || 0}</span></div></div>
                                <div class="col-md-3"><div class="dashboard-card-stat"><span class="stat-label">Casos en radar</span><span class="stat-val">${sst.casos_radar || 0}</span></div></div>
                                <div class="col-md-3"><div class="dashboard-card-stat"><span class="stat-label">Alertas pendientes</span><span class="stat-val">${sst.alertas_pendientes || 0}</span></div></div>
                            </div>
                        </div>
                        <!-- Payroll Block - Sprint 7 Integration -->
                        ${payroll_block && Object.keys(payroll_block).length > 0 ? `
                        <div class="col-md-12" style="margin-bottom: 20px;">
                            <div class="dashboard-section p-3">
                                <h5>Bloque de nómina</h5>
                                <div class="row">
                                    <div class="col-md-3">
                                        <div class="payroll-card">
                                            <span class="payroll-label">Días vacaciones</span>
                                            <span class="payroll-val">${(payroll_block.vacation_balance && payroll_block.vacation_balance.days_remaining) || 0}</span>
                                            <small class="text-muted">${(payroll_block.vacation_balance && payroll_block.vacation_balance.calculation_note) || ''}</small>
                                        </div>
                                    </div>
                                    <div class="col-md-3">
                                        <div class="payroll-card">
                                            <span class="payroll-label">Incapacidades activas</span>
                                            <span class="payroll-val">${(payroll_block.active_incapacidades && payroll_block.active_incapacidades.total_estimated) || 0}</span>
                                            <small class="text-muted">${(payroll_block.active_incapacidades && payroll_block.active_incapacidades.note) || ''}</small>
                                        </div>
                                    </div>
                                    <div class="col-md-3">
                                        <div class="payroll-card">
                                            <span class="payroll-label">Deducciones pendientes</span>
                                            <span class="payroll-val">$${((payroll_block.pending_deductions && payroll_block.pending_deductions.total_amount) || 0).toLocaleString()}</span>
                                            <small class="text-muted">${(payroll_block.pending_deductions && payroll_block.pending_deductions.total_items) || 0} items</small>
                                        </div>
                                    </div>
                                    <div class="col-md-3">
                                        <div class="payroll-card">
                                            <span class="payroll-label">Novedades (12m)</span>
                                            <span class="payroll-val">${Object.keys(payroll_block.novelty_summary || {}).length}</span>
                                            <small class="text-muted">tipos diferentes</small>
                                        </div>
                                    </div>
                                </div>
                                ${Object.keys(payroll_block.novelty_summary || {}).length > 0 ? `
                                <div class="mt-3">
                                    <h6>Resumen de Novedades (últimos 12 meses):</h6>
                                    <div class="row">
                                        ${Object.entries(payroll_block.novelty_summary || {}).map(([type, summary]) => `
                                            <div class="col-md-4 mb-2">
                                                <div class="small-novelty-card">
                                                    <strong>${type}</strong>: ${summary.count} eventos
                                                    ${summary.total_quantity ? ` (${summary.total_quantity} total)` : ''}
                                                    ${summary.last_date ? `<br><small>Último: ${frappe.datetime.str_to_user(summary.last_date)}</small>` : ''}
                                                </div>
                                            </div>
                                        `).join('')}
                                    </div>
                                </div>
                                ` : ''}
                            </div>
                        </div>
                        ` : ''}
                        <!-- Left Column: Employee Profile -->
						<div class="col-md-4 persona360-profile-column">
                            <div class="dashboard-section text-center p-4">
                                <div class="avatar avatar-xl mb-3" style="width: 100px; height: 100px; margin: 0 auto; background-color: var(--bg-light-gray); display: flex; align-items: center; justify-content: center; border-radius: 50%;">
                                    <span style="font-size: 40px;">${info.nombres[0]}${info.apellidos[0]}</span>
                                </div>
                                <h4>${info.nombres} ${info.apellidos}</h4>
                                <p class="text-muted">${info.cargo || 'Sin Cargo'}</p>
                                <span class="indicator-pill ${status_color}">${info.estado}</span>
                                
                                <hr>
                                
                                <div class="text-left mt-4" style="text-align: left;">
                                    <p><strong>🆔 Cédula:</strong> ${info.cedula}</p>
                                    <p><strong>🏢 Punto:</strong> ${info.pdv_nombre}</p>
                                    <p><strong>📅 Ingreso:</strong> ${frappe.datetime.str_to_user(info.fecha_ingreso)}</p>
                                    <p><strong>📧 Email:</strong> ${info.email || '-'}</p>
                                </div>
                            </div>
                        </div>
                        
                        <!-- Right Column: Timeline -->
						<div class="col-md-8 persona360-timeline-column">
                            <div class="dashboard-section p-4">
                                <h5>Historial y eventos</h5>
                                <hr>
                                <div class="timeline persona360-timeline-scroll">
                                    ${timeline.length > 0 ? timeline.map(event => `
                                        <div class="timeline-item" style="border-left: 3px solid ${mapColor(event.color)}; padding-left: 15px; margin-bottom: 20px; position: relative;">
                                            <div class="timeline-date small text-muted">${frappe.datetime.str_to_user(event.date)}</div>
                                            <div class="timeline-content">
                                                <strong>${event.title}</strong>
                                                <p class="mb-0 text-muted small">${event.desc}</p>
                                                <small><a href="/app/${getDocTypeFromEvent(event)}/${event.ref}">Ver Detalle</a></small>
                                            </div>
                                        </div>
                                    `).join('') : '<p class="text-muted">No hay eventos registrados.</p>'}
                                </div>
                            </div>
                        </div>
						</div>
					</div>
                `;

                $container.append(html);
				bind_contextual_action_panel($container, contextual_actions, emp_id);
            }
        }
    });
}

function clear_contextual_action_buttons(page) {
    page._persona_action_buttons = page._persona_action_buttons || [];
    page._persona_action_buttons.forEach(btn => {
        if (btn && btn.remove) btn.remove();
    });
    page._persona_action_buttons = [];
}

function render_contextual_action_buttons(page, contextual_actions, emp_id) {
    clear_contextual_action_buttons(page);

    const actions = (contextual_actions.quick_actions || []).filter(a => a && a.visible);
    actions.forEach(action => {
        const btn = page.add_inner_button(action.label, function () {
            if (action.key === 'view_documents') {
                frappe.route_options = { persona: emp_id };
                frappe.set_route('query-report', 'Person Documents');
                return;
            }
            if (action.doctype) {
                const prefill = Object.assign({}, action.prefill || {}, { empleado: emp_id });
                frappe.new_doc(action.doctype, prefill);
            }
        });
        page._persona_action_buttons.push(btn);
    });
}

function render_contextual_actions_panel(contextual_actions) {
	const actions = (contextual_actions.quick_actions || []).filter(a => a && a.visible);
	if (!actions.length) {
		return '<div class="persona360-quick-empty">No hay acciones directas para este perfil.</div>';
	}

	return actions.map(action => `
		<button class="btn btn-sm btn-default persona-action-btn" data-action-key="${action.key || ''}">
			${action.label}
		</button>
	`).join('');
}

function bind_contextual_action_panel($container, contextual_actions, emp_id) {
	const actions = (contextual_actions.quick_actions || []).filter(a => a && a.visible);
	const actionMap = {};
	actions.forEach(action => {
		actionMap[action.key] = action;
	});

	$container.off('click', '.persona-action-btn').on('click', '.persona-action-btn', function () {
		const action = actionMap[$(this).data('action-key')];
		if (!action) return;

		if (action.key === 'view_documents') {
			frappe.route_options = { persona: emp_id };
			frappe.set_route('query-report', 'Person Documents');
			return;
		}

		if (action.doctype) {
			const prefill = Object.assign({}, action.prefill || {}, { empleado: emp_id });
			frappe.new_doc(action.doctype, prefill);
		}
	});
}

function mapColor(color_name) {
    const colors = {
        "blue": "#3498db",
        "red": "#e74c3c",
        "orange": "#f39c12",
        "purple": "#9b59b6",
        "green": "#2ecc71"
    };
    return colors[color_name] || "#7f8c8d";
}

function getDocTypeFromEvent(event) {
    const type = event && event.type;
    const module = event && event.module;

    // Prefer module-specific routing for new Bienestar model
    if (module === 'Bienestar Seguimiento Ingreso') return 'bienestar-seguimiento-ingreso';
    if (module === 'Bienestar Evaluacion Periodo Prueba') return 'bienestar-evaluacion-periodo-prueba';
    if (module === 'Bienestar Alerta') return 'bienestar-alerta';
    if (module === 'Bienestar Compromiso') return 'bienestar-compromiso';

    // Backward-compatible fallbacks
    if (type === 'Novedad') return 'novedad-sst';
    if (type === 'Disciplinario') return 'caso-disciplinario';
    if (type === 'SST') return 'caso-sst';
    if (type === 'Bienestar') return 'comentario-bienestar';
    if (module === 'GH Novedad') return 'gh-novedad';
    return '';
}

function injectPersona360Styles() {
    if (document.getElementById('persona-360-scroll-styles')) return;
    const style = document.createElement('style');
    style.id = 'persona-360-scroll-styles';
    style.innerHTML = `
        .persona360-employee-list-scroll {
            max-height: 720px;
            overflow-y: auto;
            overflow-x: hidden;
            padding-right: 4px;
        }
        .persona360-timeline-scroll {
            max-height: 640px;
            overflow-y: auto;
            overflow-x: hidden;
            padding-right: 6px;
        }
        .payroll-card {
            text-align: center;
            padding: 15px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            border: 1px solid #e3e8f0;
            height: 100%;
        }
        .payroll-label {
            display: block;
            font-size: 12px;
            color: #6c757d;
            font-weight: 500;
            margin-bottom: 8px;
        }
        .payroll-val {
            display: block;
            font-size: 24px;
            font-weight: bold;
            color: #2c3e50;
            margin-bottom: 4px;
        }
        .small-novelty-card {
            padding: 8px 12px;
            background: #f8f9fa;
            border-radius: 4px;
            border-left: 3px solid #007bff;
            font-size: 13px;
        }
    `;
    document.head.appendChild(style);
}
