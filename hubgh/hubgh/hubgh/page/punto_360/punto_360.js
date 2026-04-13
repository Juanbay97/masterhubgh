

frappe.pages['punto_360'].on_page_load = function (wrapper) {
	injectPunto360ScrollStyles();
    var page = frappe.ui.make_app_page({
        parent: wrapper,
		title: 'Punto 360 - Vista operativa',
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
        page.fields_dict.punto.set_value('');
        render_overview(page);
    });

    page.add_field({
        fieldname: 'punto',
        label: 'Punto de Venta',
        fieldtype: 'Link',
        options: 'Punto de Venta',
        change: function () {
            if (page._suppress_render) {
                page._suppress_render = false;
                return;
            }
            if (!page.fields_dict.punto.get_value()) {
                render_overview(page);
                return;
            }
            render_dashboard(page);
        }
    });

    page.add_field({
        fieldname: 'punto_buscar',
        label: 'Buscar en listado',
        fieldtype: 'Data',
        placeholder: 'Nombre o zona…',
        change: function () {
            page._pdv_filter = page.fields_dict.punto_buscar.get_value() || '';
            if (!page.fields_dict.punto.get_value()) {
                render_overview(page);
            }
        }
    });

    $(page.body).off('click', '.pdv-card').on('click', '.pdv-card', function () {
        const pdvId = $(this).data('pdv');
        if (!pdvId) return;
        page.fields_dict.punto.set_value(pdvId);
    });

    // Check for URL parameters to pre-fill
    let route = frappe.get_route();
    if (route.length > 1 && route[1] === 'punto_360' && frappe.route_options && frappe.route_options.pdv) {
        page.fields_dict.punto.set_value(frappe.route_options.pdv);
        frappe.route_options = null; // consume options
    }

    $(wrapper).bind('show', function () {
        // Re-check options on show if navigating back
        if (frappe.route_options && frappe.route_options.pdv) {
            page.fields_dict.punto.set_value(frappe.route_options.pdv);
            frappe.route_options = null;
        } else if (!page.fields_dict.punto.get_value()) {
            render_overview(page);
        }
    });

    // Initial load check
    if (!page.fields_dict.punto.get_value()) {
        render_overview(page);
    }
}

function render_overview(page) {
    frappe.call({
        method: "hubgh.hubgh.page.punto_360.punto_360.get_all_puntos_overview",
        callback: function (r) {
            if (r.message) {
                let pdvs = r.message;
                let $container = $(page.main || page.body);
                $container.empty();

                const filter_text = (page._pdv_filter || '').toLowerCase();
                const filtered = pdvs.filter(p => {
                    const name = (p.title || '').toLowerCase();
                    const zona = (p.zona || '').toLowerCase();
                    return !filter_text || name.includes(filter_text) || zona.includes(filter_text);
                });

                let html = `
					<div class="punto360-shell">
						<div class="punto360-overview-header">
							<div>
								<div class="punto360-kickers"><span>People Ops</span><span>Puntos</span></div>
								<h4>Puntos de venta</h4>
								<p class="text-muted">Entrá al tablero del punto con headcount, casos y alertas sin duplicar navegación.</p>
							</div>
							<div class="punto360-overview-count">${filtered.length} visibles</div>
						</div>
						<div class="row" style="padding: 20px; padding-top: 8px;">
                        <div class="col-md-12">
							<hr style="margin-top: 0;">
                        </div>
                        ${filtered.map(p => `
                            <div class="col-md-3">
								<div class="pdv-card punto360-overview-card" data-pdv="${p.name}">
									<div class="punto360-card-name">${p.title}</div>
                                    <div class="text-muted small mb-2">${p.zona}</div>
									<div class="d-flex justify-content-between text-muted small punto360-card-metrics">
										<span>Headcount ${p.headcount}</span>
										<span class="${p.novedades > 0 ? 'text-danger' : ''}">Novedades ${p.novedades}</span>
									</div>
								</div>
                            </div>
                        `).join('')}
                        ${filtered.length === 0 ? '<div class="col-md-12"><p class="text-muted">Sin resultados</p></div>' : ''}
						</div>
					</div>
                `;
                $container.append(html);
            }
        }
    });
}

function render_dashboard(page) {
    let pdv_id = page.fields_dict.punto.get_value();
    if (!pdv_id) return;

    frappe.call({
        method: "hubgh.hubgh.page.punto_360.punto_360.get_punto_stats",
        args: { pdv_id: pdv_id },
        callback: function (r) {
			if (r.message) {
                let data = r.message;
                let $container = $(page.main || page.body);
                $container.empty();

				$container.append(`
					<div class="punto360-shell punto360-detail-shell">
						<div class="punto360-detail-header dashboard-section p-4">
							<div>
								<div class="punto360-kickers"><span>Punto 360</span><span>Vista operativa</span></div>
								<h3>${data.info.pdv_nombre || pdv_id}</h3>
								<p class="text-muted mb-2">${data.info.zona || 'Sin zona'} · Headcount activo ${data.info.headcount || 0} / ${data.info.planta_autorizada || 0}</p>
								<div class="punto360-detail-meta">
									<span>Faltantes ${data.info.faltantes || 0}</span>
									<span>Novedades ${data.novedades.length}</span>
									<span>Casos ${data.disciplinarios.length + data.sst.length}</span>
								</div>
							</div>
							<div class="punto360-quick-actions">
								<div class="punto360-quick-actions-title">Acciones rápidas</div>
								<div class="punto360-quick-actions-body">
									${renderPuntoQuickActions()}
								</div>
							</div>
						</div>
						<div class="row" style="margin-bottom: 20px;">
                        <div class="col-md-3">
                            <div class="dashboard-card-stat">
                                <span class="stat-label">Headcount</span>
                                <span class="stat-val">${data.info.headcount} / ${data.info.planta_autorizada}</span>
                            </div>
                        </div>
                        <div class="col-md-3">
                            <div class="dashboard-card-stat ${data.info.faltantes > 0 ? 'text-danger' : ''}">
                                <span class="stat-label">Faltantes</span>
                                <span class="stat-val">${data.info.faltantes}</span>
                            </div>
                        </div>
                        <div class="col-md-3">
                            <div class="dashboard-card-stat">
                                <span class="stat-label">Novedades Activas</span>
                                <span class="stat-val">${data.novedades.length}</span>
                            </div>
                        </div>
                        <div class="col-md-3">
                            <div class="dashboard-card-stat">
                                <span class="stat-label">Casos Abiertos</span>
                                <span class="stat-val">${data.disciplinarios.length + data.sst.length}</span>
                            </div>
                        </div>
						</div>
					</div>
				`);

                const kpi = (data.info && data.info.kpi_sst) || {};
                const kpiOperativo = (data.info && data.info.kpi_operativo) || {};
                const kpiBienestar = (data.info && data.info.kpi_bienestar) || {};
                const kpiFormacion = (data.info && data.info.kpi_formacion) || {};
                $container.append(`
                    <div class="row" style="margin-bottom: 20px;">
                        <div class="col-md-3"><div class="dashboard-card-stat"><span class="stat-label">AT periodo</span><span class="stat-val">${kpi.accidentes_periodo || 0}</span></div></div>
                        <div class="col-md-3"><div class="dashboard-card-stat"><span class="stat-label">Incapacidades activas</span><span class="stat-val">${kpi.incapacidades_activas || 0}</span></div></div>
                        <div class="col-md-3"><div class="dashboard-card-stat"><span class="stat-label">Personas radar</span><span class="stat-val">${kpi.personas_radar || 0}</span></div></div>
                        <div class="col-md-3"><div class="dashboard-card-stat"><span class="stat-label">Alertas SST</span><span class="stat-val">${kpi.alertas_pendientes || 0}</span></div></div>
                    </div>
                `);

                $container.append(`
                    <div class="row" style="margin-bottom: 20px;">
                        <div class="col-md-3"><div class="dashboard-card-stat"><span class="stat-label">Cobertura Dotación</span><span class="stat-val">${kpiOperativo.cobertura_dotacion_pct || 0}%</span></div></div>
                        <div class="col-md-3"><div class="dashboard-card-stat"><span class="stat-label">Feedback 30d</span><span class="stat-val">${kpiBienestar.feedback_30d || 0}</span></div></div>
                        <div class="col-md-3"><div class="dashboard-card-stat"><span class="stat-label">Valoración prom. 30d</span><span class="stat-val">${kpiBienestar.valoracion_promedio_30d || 0}</span></div></div>
                        <div class="col-md-3"><div class="dashboard-card-stat"><span class="stat-label">Formación completada</span><span class="stat-val">${kpiFormacion.porcentaje_completud || 0}%</span></div></div>
                    </div>
                `);

                // DETAILS SECTIONS
                let html = `<div class="row">`;

                // Novedades Table
                html += `
                    <div class="col-md-6">
                        <div class="dashboard-section">
                            <h5>Novedades activas</h5>
                            <div class="punto360-table-scroll">
                                <table class="table table-bordered table-sm">
                                    <thead class="thead-light">
                                        <tr><th>Empleado</th><th>Tipo</th><th>Hasta</th></tr>
                                    </thead>
                                    <tbody>
                                        ${data.novedades.map(n => `
                                            <tr>
                                                <td>
                                                    <a href="#" onclick="navigateToPersonaFromPunto('${n.empleado}'); return false;">${n.empleado_nombres} ${n.empleado_apellidos}</a>
                                                    <div class="small text-muted">
                                                        <a href="#" onclick="navigateToExpedienteFromPunto('${n.empleado}'); return false;">Expediente</a>
                                                    </div>
                                                </td>
                                                <td>${n.tipo_novedad}</td>
                                                <td>${n.fecha_fin ? frappe.datetime.str_to_user(n.fecha_fin) : '-'}</td>
                                            </tr>
                                        `).join('')}
                                        ${data.novedades.length === 0 ? '<tr><td colspan="3" class="text-muted text-center">Sin novedades activas</td></tr>' : ''}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                `;

                // Disciplinarios & SST
                html += `
                    <div class="col-md-6">
                        <div class="dashboard-section">
                            <h5>Casos que requieren atención</h5>
                            <div class="punto360-table-scroll">
                                 <table class="table table-bordered table-sm">
                                    <thead class="thead-light">
                                        <tr><th>Ref</th><th>Tipo</th><th>Fecha</th></tr>
                                    </thead>
                                    <tbody>
                                        ${data.disciplinarios.map(d => `
                                            <tr>
                                                <td><a href="/app/caso-disciplinario/${d.name}">${d.name}</a></td>
                                                <td>Falta ${d.tipo_falta}</td>
                                                <td>${frappe.datetime.str_to_user(d.fecha_incidente)}</td>
                                            </tr>
                                        `).join('')}
                                        ${data.sst.map(s => `
                                            <tr>
                                                <td><a href="/app/caso-sst/${s.name}">${s.name}</a></td>
                                                <td>SST: ${s.tipo_evento} (${s.severidad})</td>
                                                <td>${frappe.datetime.str_to_user(s.fecha_evento)}</td>
                                            </tr>
                                        `).join('')}
                                         ${(data.disciplinarios.length + data.sst.length) === 0 ? '<tr><td colspan="3" class="text-muted text-center">Sin casos abiertos</td></tr>' : ''}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                `;

                html += `
                    <div class="col-md-6" style="margin-top: 20px;">
                        <div class="dashboard-section">
                            <h5>No disponibles por incapacidad</h5>
                            <div class="punto360-table-scroll">
                                <table class="table table-bordered table-sm">
                                    <thead class="thead-light">
                                        <tr><th>Empleado</th><th>Desde</th><th>Hasta</th></tr>
                                    </thead>
                                    <tbody>
                                        ${(data.no_disponibles || []).map(n => `
                                            <tr>
                                                <td>${n.empleado_nombres || ''} ${n.empleado_apellidos || ''}</td>
                                                <td>${n.fecha_inicio ? frappe.datetime.str_to_user(n.fecha_inicio) : '-'}</td>
                                                <td>${n.fecha_fin ? frappe.datetime.str_to_user(n.fecha_fin) : '-'}</td>
                                            </tr>
                                        `).join('')}
                                        ${(data.no_disponibles || []).length === 0 ? '<tr><td colspan="3" class="text-muted text-center">Sin personas incapacitadas</td></tr>' : ''}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                `;

                html += `
                    <div class="col-md-6" style="margin-top: 20px;">
                        <div class="dashboard-section">
                            <h5>Alertas SST pendientes</h5>
                            <div class="punto360-table-scroll">
                                <table class="table table-bordered table-sm">
                                    <thead class="thead-light">
                                        <tr><th>Alerta</th><th>Fecha</th><th>Tipo</th></tr>
                                    </thead>
                                    <tbody>
                                        ${(data.alertas_sst || []).map(a => `
                                            <tr>
                                                <td><a href="/app/sst-alerta/${a.name}">${a.name}</a></td>
                                                <td>${a.fecha_programada ? frappe.datetime.str_to_user(a.fecha_programada) : '-'}</td>
                                                <td>${a.tipo_alerta || '-'}</td>
                                            </tr>
                                        `).join('')}
                                        ${(data.alertas_sst || []).length === 0 ? '<tr><td colspan="3" class="text-muted text-center">Sin alertas pendientes</td></tr>' : ''}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                `;

                // Feedback Section
                if (data.feedback && data.feedback.length > 0) {
                    html += `
                        <div class="col-md-12" style="margin-top: 20px;">
                            <div class="dashboard-section">
                                <h5>Feedback reciente</h5>
                                <div class="punto360-table-scroll">
                                    <table class="table table-bordered table-sm">
                                        <thead class="thead-light">
                                            <tr><th>Fecha</th><th>Valoración</th><th>Comentario</th></tr>
                                        </thead>
                                        <tbody>
                                            ${data.feedback.map(f => `
                                                <tr>
                                                    <td>${frappe.datetime.str_to_user(f.fecha)}</td>
                                                    <td>${f.valoracion}/5</td>
                                                    <td>${f.comentarios}</td>
                                                </tr>
                                            `).join('')}
                                        </tbody>
                                    </table>
                                </div>
                            </div>
                        </div>
                    `;
                }

				html += `</div>`;

				$container.append(html);
				bindPuntoQuickActions($container, pdv_id);
			}
		}
	});
}

function renderPuntoQuickActions() {
	return `
		<button class="btn btn-sm btn-default punto-action-btn" data-action-key="novedad_sst">Registrar novedad SST</button>
		<button class="btn btn-sm btn-default punto-action-btn" data-action-key="caso">Abrir caso disciplinario</button>
		<button class="btn btn-sm btn-default punto-action-btn" data-action-key="feedback">Registrar feedback</button>
	`;
}

function bindPuntoQuickActions($container, pdvId) {
	$container.off('click', '.punto-action-btn').on('click', '.punto-action-btn', function () {
		const actionKey = $(this).data('action-key');
		if (!pdvId) {
			frappe.msgprint('Seleccione un Punto de Venta');
			return;
		}

		if (actionKey === 'novedad_sst') {
			frappe.new_doc('Novedad SST', { pdv: pdvId });
			return;
		}

		if (actionKey === 'feedback') {
			frappe.new_doc('Feedback Punto', { pdv: pdvId });
			return;
		}

		if (actionKey === 'caso') {
			frappe.new_doc('Caso Disciplinario', { pdv: pdvId });
		}
	});
}

function navigateToPersonaFromPunto(employeeId) {
    if (!employeeId) return;
    frappe.set_route('persona_360', { empleado: employeeId });
}

function navigateToExpedienteFromPunto(employeeId) {
    if (!employeeId) return;
    frappe.route_options = { persona: employeeId };
    frappe.set_route('query-report', 'Person Documents');
}

function injectPunto360ScrollStyles() {
    if (document.getElementById('punto-360-scroll-styles')) return;
    const style = document.createElement('style');
    style.id = 'punto-360-scroll-styles';
    style.innerHTML = `
        .punto360-table-scroll {
            max-height: 380px;
            overflow-y: auto;
            overflow-x: auto;
        }
        .punto360-table-scroll table {
            margin-bottom: 0;
        }
    `;
    document.head.appendChild(style);
}
