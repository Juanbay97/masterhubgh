
frappe.pages['punto_360'].on_page_load = function (wrapper) {
	injectPunto360ScrollStyles();
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Punto 360 - Vista operativa',
		single_column: true
	});

	if (page.clear_breadcrumbs) {
		page.clear_breadcrumbs();
	}
	if (page.add_breadcrumb_item) {
		page.add_breadcrumb_item('Inicio', function () {
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

	decoratePunto360Toolbar(page);
	getPunto360Mount(page);

	$(page.body).off('click', '.pdv-card').on('click', '.pdv-card', function () {
		const pdvId = $(this).data('pdv');
		if (!pdvId) return;
		page.fields_dict.punto.set_value(pdvId);
	});

	let route = frappe.get_route();
	if (route.length > 1 && route[1] === 'punto_360' && frappe.route_options && frappe.route_options.pdv) {
		page.fields_dict.punto.set_value(frappe.route_options.pdv);
		frappe.route_options = null;
	}

	$(wrapper).bind('show', function () {
		if (frappe.route_options && frappe.route_options.pdv) {
			page.fields_dict.punto.set_value(frappe.route_options.pdv);
			frappe.route_options = null;
		} else if (!page.fields_dict.punto.get_value()) {
			render_overview(page);
		}
	});

	if (!page.fields_dict.punto.get_value()) {
		render_overview(page);
	}
};

function render_overview(page) {
	frappe.call({
		method: 'hubgh.hubgh.page.punto_360.punto_360.get_all_puntos_overview',
		callback: function (r) {
			if (!r.message) return;

			const puntos = r.message;
			const filterText = (page._pdv_filter || '').toLowerCase();
			const filtered = puntos.filter(function (punto) {
				const name = (punto.title || '').toLowerCase();
				const zona = (punto.zona || '').toLowerCase();
				return !filterText || name.includes(filterText) || zona.includes(filterText);
			});

			renderPunto360Content(page, `
				<div class="punto360-shell punto360-overview-shell">
					<section class="punto360-hero punto360-hero-overview">
						<div class="punto360-hero-copy">
							<div class="punto360-eyebrow">People Ops / Operación distribuida</div>
							<h2>Mapa de puntos con presión operativa</h2>
						<p>La búsqueda queda fija y el overview prioriza headcount, faltantes y señales de riesgo con una lectura más liviana sobre el canvas base.</p>
						</div>
						<div class="punto360-hero-aside">
							<div class="punto360-aside-label">Puntos visibles</div>
							<div class="punto360-aside-value">${filtered.length}</div>
							<div class="punto360-aside-meta">${filterText ? 'Filtrado activo' : 'Cobertura completa'}</div>
						</div>
					</section>
					<section class="punto360-list-grid">
						${filtered.map(renderPuntoOverviewCard).join('') || renderPuntoEmptyState('Sin resultados para la búsqueda actual.')}
					</section>
				</div>
			`);
		}
	});
}

function render_dashboard(page) {
	let pdvId = page.fields_dict.punto.get_value();
	if (!pdvId) return;

	frappe.call({
		method: 'hubgh.hubgh.page.punto_360.punto_360.get_punto_stats',
		args: { pdv_id: pdvId },
		callback: function (r) {
			if (!r.message) return;

			const data = r.message;
			const info = data.info || {};
			const kpi = info.kpi_sst || {};
			const kpiOperativo = info.kpi_operativo || {};
			const kpiBienestar = info.kpi_bienestar || {};
			const kpiFormacion = info.kpi_formacion || {};
			const empleados = data.empleados || [];
			const pointStatus = buildPuntoOperationalStatus(info, data, empleados);

			renderPunto360Content(page, `
				<div class="punto360-shell punto360-detail-shell">
					<section class="punto360-hero punto360-hero-detail punto360-hero-executive punto360-status-${pointStatus.tone}">
						<div class="punto360-hero-copy punto360-detail-copy">
							<div class="punto360-eyebrow">Punto 360 / Operativa moderna</div>
							<h2>${info.pdv_nombre || pdvId}</h2>
							<p>${info.zona || 'Sin zona'} · ${pointStatus.summary}</p>
							<div class="punto360-meta-strip">
								<span class="punto360-pill punto360-pill-${pointStatus.tone}">${pointStatus.label}</span>
								<span>Headcount ${info.headcount || 0} / ${info.planta_autorizada || 0}</span>
								<span>Faltantes ${info.faltantes || 0}</span>
								<span>Personas ${empleados.length}</span>
							</div>
							<div class="punto360-executive-notes">
								<div>
									<span class="punto360-note-label">Urgencia</span>
									<strong>${pointStatus.urgency}</strong>
								</div>
								<div>
									<span class="punto360-note-label">Continuidad</span>
									<strong>${pointStatus.continuity}</strong>
								</div>
								<div>
									<span class="punto360-note-label">Seguimiento</span>
									<strong>${pointStatus.followUp}</strong>
								</div>
							</div>
						</div>
						<aside class="punto360-panel punto360-actions-panel">
							<div class="punto360-panel-label">Mesa ejecutiva</div>
							<h3>Resolver o registrar</h3>
							<p class="punto360-panel-caption">Acciones directas para mover la operación sin salir del contexto del punto.</p>
							<div class="punto360-action-list">
								${renderPuntoQuickActions()}
							</div>
						</aside>
					</section>

					<section class="punto360-kpi-band punto360-kpi-band-primary">
						${renderPuntoKpiCard('Cobertura actual', `${info.headcount || 0} / ${info.planta_autorizada || 0}`, 'Dotación real sobre la autorizada')}
						${renderPuntoKpiCard('Faltantes', info.faltantes || 0, 'Brecha operativa inmediata')}
						${renderPuntoKpiCard('Urgencias abiertas', pointStatus.openPressure, 'Novedades + alertas + casos que exigen lectura inmediata')}
						${renderPuntoKpiCard('Continuidad afectada', data.no_disponibles.length, 'Personas no disponibles por incapacidad')}
					</section>

					<section class="punto360-kpi-band punto360-kpi-band-secondary">
						${renderPuntoKpiCard('AT período', kpi.accidentes_periodo || 0, 'Eventos SST del período')}
						${renderPuntoKpiCard('Incapacidades', kpi.incapacidades_activas || 0, 'Personas no disponibles')}
						${renderPuntoKpiCard('Feedback 30d', kpiBienestar.feedback_30d || 0, 'Escucha reciente del equipo')}
						${renderPuntoKpiCard('Formación completa', `${kpiFormacion.porcentaje_completud || 0}%`, `Cobertura ${kpiOperativo.cobertura_dotacion_pct || 0}%`) }
					</section>

					<div class="row punto360-detail-grid">
						<div class="col-md-12">
							${renderPuntoDataPanel('Equipo del punto', 'Pieza central de operación: quién sostiene el punto, quién está en riesgo y quién necesita navegar a Persona 360.', renderPuntoEmployeeList(empleados), 'Equipo')}
						</div>

						<div class="col-md-6">
							${renderPuntoDataPanel('Operación inmediata', 'Novedades activas que impactan cobertura, turnos o ejecución cotidiana.', renderPuntoDataList(data.novedades || [], function (n) {
								return `
									<div class="punto360-data-row punto360-data-row-linkable punto360-data-row-operativa">
										<div>
											<a href="#" onclick="navigateToPersonaFromPunto('${n.empleado}'); return false;">${n.empleado_nombres || ''} ${n.empleado_apellidos || ''}</a>
											<div class="punto360-row-meta">${n.tipo_novedad || 'Sin tipo'} · ${n.fecha_fin ? 'Hasta ' + formatPuntoUserDate(n.fecha_fin) : 'Sin fecha final'}</div>
										</div>
										<div class="punto360-row-side">
											<span class="punto360-pill punto360-pill-warning">Urgencia</span>
											<a class="punto360-inline-link" href="#" onclick="navigateToExpedienteFromPunto('${n.empleado}'); return false;">Expediente</a>
										</div>
									</div>
								`;
							}, 'Sin novedades activas'), 'Operación')}
						</div>

						<div class="col-md-6">
							${renderPuntoDataPanel('Riesgo y seguimiento', 'Casos, alertas y trazas que no pueden perder continuidad.', renderPuntoDataList([].concat(
								(data.disciplinarios || []).map(function (d) {
									return {
										title: d.name,
										meta: 'Falta ' + (d.tipo_falta || '-'),
										date: formatPuntoUserDate(d.fecha_incidente),
										url: '/app/caso-disciplinario/' + d.name,
										tone: 'warning'
									};
								}),
								(data.sst || []).map(function (s) {
									return {
										title: s.name,
										meta: 'SST ' + (s.tipo_evento || '-') + ' · ' + (s.severidad || '-'),
										date: formatPuntoUserDate(s.fecha_evento),
										url: '/app/caso-sst/' + s.name,
										tone: 'critical'
									};
								}),
								(data.alertas_sst || []).map(function (a) {
									return {
										title: a.name,
										meta: 'Alerta ' + (a.tipo_alerta || 'Sin tipo'),
										date: formatPuntoUserDate(a.fecha_programada),
										url: '/app/sst-alerta/' + a.name,
										tone: 'attention'
									};
								})
							), function (item) {
								return `
									<div class="punto360-data-row punto360-data-row-risk">
										<div>
											<a href="${item.url}">${item.title}</a>
											<div class="punto360-row-meta">${item.meta}</div>
										</div>
										<div class="punto360-row-side">
											<span class="punto360-pill punto360-pill-${item.tone || 'neutral'}">Seguimiento</span>
											<div class="punto360-row-date">${item.date}</div>
										</div>
									</div>
								`;
							}, 'Sin casos abiertos'))}
						</div>

						<div class="col-md-6">
							${renderPuntoDataPanel('Continuidad operativa', 'Ausencias que condicionan cobertura y estabilidad de la dotación.', renderPuntoDataList(data.no_disponibles || [], function (n) {
								return `
									<div class="punto360-data-row punto360-data-row-continuity">
										<div>
											<div class="punto360-row-title">${n.empleado_nombres || ''} ${n.empleado_apellidos || ''}</div>
											<div class="punto360-row-meta">Desde ${formatPuntoUserDate(n.fecha_inicio)}</div>
										</div>
										<div class="punto360-row-side">
											<span class="punto360-pill punto360-pill-attention">Continuidad</span>
											<div class="punto360-row-date">${n.fecha_fin ? 'Hasta ' + formatPuntoUserDate(n.fecha_fin) : 'Sin fecha final'}</div>
										</div>
									</div>
								`;
							}, 'Sin personas incapacitadas'), 'Continuidad')}
						</div>

						<div class="col-md-6">
							${data.feedback && data.feedback.length ? renderPuntoDataPanel('Pulso del equipo', 'Lectura cualitativa para entender clima y fricción de la operación.', renderPuntoDataList(data.feedback || [], function (f) {
								return `
									<div class="punto360-data-row punto360-feedback-row">
										<div>
											<div class="punto360-row-title">Valoración ${f.valoracion || 0}/5</div>
											<div class="punto360-row-meta">${f.comentarios || 'Sin comentario'}</div>
										</div>
										<div class="punto360-row-date">${formatPuntoUserDate(f.fecha)}</div>
									</div>
								`;
							}, 'Sin feedback reciente'), 'Seguimiento') : renderPuntoDataPanel('Pulso del equipo', 'No hay feedback reciente para leer en esta vista.', renderPuntoEmptyState('Sin feedback reciente'), 'Seguimiento')}
						</div>
					</div>
				</div>
			`);

			bindPuntoQuickActions(getPunto360Mount(page), pdvId);
		}
	});
}

function decoratePunto360Toolbar(page) {
	if (page._punto_toolbar_ready) return;
	page._punto_toolbar_ready = true;

	const puntoField = page.fields_dict.punto && page.fields_dict.punto.wrapper;
	const buscarField = page.fields_dict.punto_buscar && page.fields_dict.punto_buscar.wrapper;

	$(puntoField).addClass('punto360-toolbar-field punto360-toolbar-field-link');
	$(buscarField).addClass('punto360-toolbar-field punto360-toolbar-field-search');
}

function getPunto360Mount(page) {
	const base = page.main || page.body;
	let $mount = $(base).children('.punto360-render-root');
	if (!$mount.length) {
		$mount = $('<div class="punto360-render-root"></div>');
		$(base).append($mount);
	}
	return $mount;
}

function renderPunto360Content(page, html) {
	const $mount = getPunto360Mount(page);
	$mount.empty().append(html);
}

function renderPuntoOverviewCard(punto) {
	return `
		<article class="pdv-card punto360-overview-card" data-pdv="${punto.name}">
			<div class="punto360-card-topline">
				<div class="punto360-card-kicker">Punto</div>
				<div class="punto360-card-status">${punto.zona || 'Sin zona'}</div>
			</div>
			<h3>${punto.title || 'Sin nombre'}</h3>
			<p>Headcount actual ${punto.headcount || 0}</p>
			<div class="punto360-archive-list">
				${renderPuntoArchiveItem('Zona', punto.zona || '-')}
				${renderPuntoArchiveItem('Headcount', punto.headcount || 0)}
				${renderPuntoArchiveItem('Novedades', punto.novedades || 0)}
			</div>
		</article>
	`;
}

function renderPuntoKpiCard(label, value, meta) {
	return `
		<div class="punto360-kpi-card">
			<div class="punto360-kpi-label">${label}</div>
			<div class="punto360-kpi-value">${value}</div>
			<div class="punto360-kpi-meta">${meta}</div>
		</div>
	`;
}

function renderPuntoDataPanel(title, subtitle, content, label) {
	return `
		<section class="punto360-panel punto360-data-panel">
			<div class="punto360-panel-head">
				<div>
					<div class="punto360-panel-label">${label || 'Reporte'}</div>
					<h3>${title}</h3>
				</div>
				<div class="punto360-panel-caption">${subtitle}</div>
			</div>
			<div class="punto360-data-list punto360-table-scroll">${content}</div>
		</section>
	`;
}

function renderPuntoDataList(items, renderer, emptyMessage) {
	if (!items || !items.length) {
		return renderPuntoEmptyState(emptyMessage);
	}
	return items.map(renderer).join('');
}

function renderPuntoEmployeeList(items) {
	return renderPuntoDataList(items || [], function (item) {
		const statusTone = (item.estado || '').toLowerCase() === 'activo' ? 'positive' : 'neutral';
		const urgencyTone = item.tiene_novedad ? 'warning' : (item.signal === 'limited' || item.signal === 'attention' ? 'attention' : 'stable');
		return `
			<div class="punto360-data-row punto360-data-row-linkable punto360-person-row">
				<div>
					<a href="#" onclick="navigateToPersonaFromPunto('${item.empleado}'); return false;">${item.nombre || item.empleado || 'Sin nombre'}</a>
					<div class="punto360-row-meta">${item.cargo || 'Sin cargo'}${item.novedades_activas ? ' · ' + item.novedades_activas + ' novedad(es)' : ' · Sin novedades activas'}</div>
				</div>
				<div class="punto360-person-signals">
					<span class="punto360-pill punto360-pill-${statusTone}">${item.estado || 'Sin estado'}</span>
					<span class="punto360-pill punto360-pill-${urgencyTone}">${item.tiene_novedad ? 'Urgencia' : 'Continuidad'}</span>
					<span class="punto360-pill punto360-pill-signal-${item.signal || 'stable'}">${item.signal_label || 'Estable'}</span>
				</div>
			</div>
		`;
	}, 'Sin personas vinculadas a este punto.');
}

function buildPuntoOperationalStatus(info, data, empleados) {
	const faltantes = info.faltantes || 0;
	const novedades = (data.novedades || []).length;
	const riesgos = (data.disciplinarios || []).length + (data.sst || []).length + (data.alertas_sst || []).length;
	const continuidad = (data.no_disponibles || []).length;
	const pressure = faltantes + novedades + riesgos + continuidad;

	if (pressure >= 8) {
		return {
			tone: 'critical',
			label: 'Presión alta',
			summary: `Operación exigida con ${pressure} frentes activos`,
			urgency: `${novedades + riesgos} frentes para atender hoy`,
			continuity: `${continuidad || 0} ausencia(s) impactan cobertura`,
			followUp: 'Riesgo operativo sostenido',
			openPressure: pressure
		};
	}

	if (pressure >= 4) {
		return {
			tone: 'attention',
			label: 'Seguimiento reforzado',
			summary: `Hay ${pressure} señales que requieren coordinación`,
			urgency: `${novedades + riesgos} alertas/casos con lectura cercana`,
			continuity: continuidad ? `${continuidad} baja(s) afectan continuidad` : 'Cobertura estable por ahora',
			followUp: 'Operación controlada con pendientes',
			openPressure: pressure
		};
	}

	return {
		tone: 'positive',
		label: 'Operación estable',
		summary: `Tablero con presión controlada para ${empleados.length} persona(s)`,
		urgency: novedades ? `${novedades} novedad(es) para revisar` : 'Sin urgencias abiertas',
		continuity: continuidad ? `${continuidad} ausencia(s) monitoreadas` : 'Continuidad sin afectación visible',
		followUp: riesgos ? `${riesgos} seguimiento(s) abiertos` : 'Seguimiento bajo control',
		openPressure: pressure
	};
}

function renderPuntoArchiveItem(label, value) {
	return `
		<div class="punto360-archive-item">
			<span>${label}</span>
			<strong>${value}</strong>
		</div>
	`;
}

function renderPuntoEmptyState(message) {
	return `<div class="punto360-empty-state">${message}</div>`;
}

function renderPuntoQuickActions() {
	return `
		<button class="btn btn-sm btn-default punto-action-btn" data-action-key="novedad_sst">Registrar novedad SST</button>
		<button class="btn btn-sm btn-default punto-action-btn" data-action-key="caso">Abrir caso</button>
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
			let d = new frappe.ui.Dialog({
				title: 'Abrir caso operativo',
				fields: [{
					label: 'Tipo de caso',
					fieldname: 'tipo',
					fieldtype: 'Select',
					options: 'Disciplinario\nSST',
					reqd: 1
				}],
				primary_action_label: 'Continuar',
				primary_action: function (values) {
					let doctype = values.tipo === 'Disciplinario' ? 'Caso Disciplinario' : 'Caso SST';
					frappe.new_doc(doctype, { pdv: pdvId });
					d.hide();
				}
			});
			d.show();
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

function formatPuntoUserDate(value) {
	return value ? frappe.datetime.str_to_user(value) : '-';
}

function injectPunto360ScrollStyles() {
	if (document.getElementById('punto-360-scroll-styles')) return;
	const style = document.createElement('style');
	style.id = 'punto-360-scroll-styles';
	style.innerHTML = `
		.punto360-table-scroll {
			max-height: 420px;
			overflow-y: auto;
			overflow-x: hidden;
		}
	`;
	document.head.appendChild(style);
}
