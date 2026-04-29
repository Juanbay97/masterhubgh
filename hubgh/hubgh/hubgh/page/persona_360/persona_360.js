
frappe.pages['persona_360'].on_page_load = function (wrapper) {
	injectPersona360Styles();
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Persona 360 - Vista integral',
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

	decoratePersona360Toolbar(page);
	getPersona360Mount(page);

	$(page.body).off('click', '.emp-card').on('click', '.emp-card', function () {
		const empId = $(this).data('emp');
		if (!empId) return;
		page.fields_dict.empleado.set_value(empId);
	});

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
};

function render_overview(page) {
	clear_contextual_action_buttons(page);
	frappe.call({
		method: 'hubgh.hubgh.page.persona_360.persona_360.get_all_personas_overview',
		callback: function (r) {
			if (!r.message) return;

			const personas = r.message;
			const filterText = (page._emp_filter || '').toLowerCase();
			const filtered = personas.filter(function (persona) {
				const nombre = (persona.full_name || '').toLowerCase();
				const cedula = (persona.cedula || '').toLowerCase();
				const punto = (persona.pdv_nombre || '').toLowerCase();
				return !filterText || nombre.includes(filterText) || cedula.includes(filterText) || punto.includes(filterText);
			});

			renderPersona360Content(page, `
				<div class="persona360-shell persona360-overview-shell">
					<section class="persona360-hero persona360-hero-overview">
						<div class="persona360-hero-copy">
							<div class="persona360-eyebrow">People Ops / Vista general</div>
							<h2>Panorama de identidad y seguimiento</h2>
						<p>La búsqueda queda fija arriba y el listado resume identidad, punto, señales de bienestar y actividad reciente con capas mínimas sobre el canvas base.</p>
						</div>
						<div class="persona360-hero-aside">
							<div class="persona360-aside-label">Personas visibles</div>
							<div class="persona360-aside-value">${filtered.length}</div>
							<div class="persona360-aside-meta">${filterText ? 'Filtrado activo' : 'Listado completo'}</div>
						</div>
					</section>
					<section class="persona360-list-grid">
						${filtered.map(renderPersonaOverviewCard).join('') || renderPersonaEmptyState('Sin resultados para la búsqueda actual.')}
					</section>
				</div>
			`);
		}
	});
}

function render_persona(page) {
	let empId = page.fields_dict.empleado.get_value();
	if (!empId) return;

	frappe.call({
		method: 'hubgh.hubgh.page.persona_360.persona_360.get_persona_stats',
		args: { employee_id: empId },
		callback: function (r) {
			if (!r.message) return;

			const data = r.message;
			const info = data.info || {};
			const timeline = data.timeline || [];
			const sst = data.sst_cards || {};
			const contextualActions = data.contextual_actions || {};
			const documentaryContext = data.documentary_context || {};
			const payrollBlock = data.payroll_block || {};
			const statusTone = getPersonaStatusTone(info.estado);
			const storyline = buildPersonaStoryline(info, timeline, sst);

			clear_contextual_action_buttons(page);

			renderPersona360Content(page, `
				<div class="persona360-shell persona360-detail-shell">
					<section class="persona360-hero persona360-hero-detail persona360-editorial-hero persona360-state-${statusTone}">
						<div class="persona360-editorial-id">
							<div class="persona360-eyebrow">Persona 360 / Editorial</div>
							<div class="persona360-identity-row">
								<div class="persona360-avatar">${getPersonaInitials(info)}</div>
								<div>
									<h2>${info.nombres || ''} ${info.apellidos || ''}</h2>
									<p>${info.cargo || 'Sin cargo'} · ${info.pdv_nombre || 'Sin punto asignado'}</p>
								</div>
							</div>
							<div class="persona360-meta-strip persona360-meta-strip-editorial">
								<span class="persona360-state persona360-state-${statusTone}">${info.estado || 'Sin estado'}</span>
								<span>Ingreso ${formatPersonaUserDate(info.fecha_ingreso)}</span>
								<span>Documento ${info.cedula || '-'}</span>
								<span>${info.email || 'Sin correo registrado'}</span>
							</div>
						</div>
						<div class="persona360-storyboard">
							<div class="persona360-story-step persona360-story-step-current">
								<div class="persona360-panel-label">Cómo está</div>
								<h3>${storyline.current.title}</h3>
								<p>${storyline.current.body}</p>
							</div>
							<div class="persona360-story-grid">
								<div class="persona360-story-step">
									<div class="persona360-panel-label">Qué le pasó</div>
									<strong>${storyline.history.title}</strong>
									<p>${storyline.history.body}</p>
								</div>
								<div class="persona360-story-step persona360-story-step-action">
									<div class="persona360-panel-label">Qué hacer</div>
									<strong>${storyline.next.title}</strong>
									<p>${storyline.next.body}</p>
									<div class="persona360-inline-actions persona360-action-list">
										${render_contextual_actions_panel(contextualActions)}
									</div>
								</div>
							</div>
						</div>
					</section>

					<div class="row persona360-detail-grid">
						<div class="col-md-8">
							<section class="persona360-panel persona360-timeline-panel persona360-timeline-panel-featured">
								<div class="persona360-panel-head persona360-panel-head-featured">
									<div>
										<div class="persona360-panel-label">Qué le pasó</div>
										<h3>Timeline protagonista</h3>
									</div>
									<div class="persona360-panel-caption">Secuencia cronológica para entender hechos, bienestar y seguimiento antes de decidir el próximo paso.</div>
								</div>
								<div class="persona360-timeline-summary-strip">
									<div>
										<span>Eventos ${timeline.length}</span>
										<strong>${storyline.history.title}</strong>
									</div>
									<div>
										<span>Lectura actual</span>
										<strong>${storyline.current.title}</strong>
									</div>
									<div>
										<span>Próximo foco</span>
										<strong>${storyline.next.title}</strong>
									</div>
								</div>
								<div class="persona360-timeline-scroll persona360-timeline-list persona360-timeline-list-featured">
									${timeline.length ? timeline.map(renderPersonaTimelineItem).join('') : renderPersonaEmptyState('No hay eventos registrados para esta persona.')}
								</div>
							</section>
						</div>

						<div class="col-md-4 persona360-editorial-sidebar">
							<section class="persona360-panel persona360-profile-panel persona360-profile-panel-editorial">
								<div class="persona360-panel-head persona360-panel-head-tight persona360-panel-head-stack">
									<div>
										<div class="persona360-panel-label">Quién es</div>
										<h3>Identidad y archivo</h3>
									</div>
									<div class="persona360-panel-caption">La ficha editorial complementa el timeline con contexto estable y lectura administrativa.</div>
								</div>
								<div class="persona360-profile-name">${info.nombres || ''} ${info.apellidos || ''}</div>
								<div class="persona360-profile-role">${info.cargo || 'Sin cargo registrado'}</div>
								<div class="persona360-archive-list persona360-archive-list-editorial">
									${renderPersonaArchiveItem('Punto base', info.pdv_nombre || 'Sin punto')}
									${renderPersonaArchiveItem('Documento', info.cedula || '-')}
									${renderPersonaArchiveItem('Ingreso', formatPersonaUserDate(info.fecha_ingreso))}
									${renderPersonaArchiveItem('Correo', info.email || '-')}
								</div>
							</section>

							${renderPersonaDocumentHub(documentaryContext)}

							<section class="persona360-kpi-band persona360-kpi-band-support">
								${renderPersonaKpiCard('AT activos', sst.at_activos || 0, 'Casos en curso vinculados a SST')}
								${renderPersonaKpiCard('Incapacidades activas', sst.incapacidades_activas || 0, 'Personas fuera de disponibilidad')}
								${renderPersonaKpiCard('Casos en radar', sst.casos_radar || 0, 'Seguimientos que requieren lectura cercana')}
								${renderPersonaKpiCard('Alertas pendientes', sst.alertas_pendientes || 0, 'Pendientes por resolver o documentar')}
							</section>

							${renderPersonaPayrollBlock(payrollBlock)}
						</div>
					</div>
				</div>
			`);

			bind_contextual_action_panel(getPersona360Mount(page), contextualActions, empId);
		}
	});
}

function decoratePersona360Toolbar(page) {
	if (page._persona_toolbar_ready) return;
	page._persona_toolbar_ready = true;

	const empleadoField = page.fields_dict.empleado && page.fields_dict.empleado.wrapper;
	const buscarField = page.fields_dict.empleado_buscar && page.fields_dict.empleado_buscar.wrapper;

	$(empleadoField).addClass('persona360-toolbar-field persona360-toolbar-field-link');
	$(buscarField).addClass('persona360-toolbar-field persona360-toolbar-field-search');
	$(buscarField).attr('data-persona360-search', 'true');
}

function getPersona360Mount(page) {
	const base = page.main || page.body;
	let $mount = $(base).children('.persona360-render-root');
	if (!$mount.length) {
		$mount = $('<div class="persona360-render-root"></div>');
		$(base).append($mount);
	}
	return $mount;
}

function renderPersona360Content(page, html) {
	const $mount = getPersona360Mount(page);
	$mount.empty().append(html);
}

function renderPersonaOverviewCard(persona) {
	return `
		<article class="emp-card persona360-overview-card" data-emp="${persona.name}">
			<div class="persona360-card-topline">
				<div class="persona360-card-kicker">Persona</div>
				<div class="persona360-card-status">${persona.pdv_nombre || 'Sin punto'}</div>
			</div>
			<h3>${persona.full_name || 'Sin nombre'}</h3>
			<p>${persona.cargo || 'Sin cargo registrado'}</p>
			<div class="persona360-archive-list persona360-archive-list-compact">
				${renderPersonaArchiveItem('Documento', persona.cedula || '-')}
				${renderPersonaArchiveItem('Novedades', persona.novedades || 0)}
				${renderPersonaArchiveItem('Bienestar', persona.feedback_count || 0)}
			</div>
			${persona.feedback_last ? `<div class="persona360-quote">“${persona.feedback_last}”</div>` : '<div class="persona360-quote persona360-quote-empty">Sin comentario reciente.</div>'}
		</article>
	`;
}

function renderPersonaKpiCard(label, value, meta) {
	return `
		<div class="persona360-kpi-card">
			<div class="persona360-kpi-label">${label}</div>
			<div class="persona360-kpi-value">${value}</div>
			<div class="persona360-kpi-meta">${meta}</div>
		</div>
	`;
}

function buildPersonaStoryline(info, timeline, sst) {
	const latestEvent = timeline && timeline.length ? timeline[0] : null;
	const alerts = (sst.alertas_pendientes || 0) + (sst.casos_radar || 0);
	const incapacidades = sst.incapacidades_activas || 0;
	const nextAction = alerts > 0 ? 'Priorizar seguimiento' : 'Mantener continuidad';

	return {
		current: {
			title: info.estado || 'Sin estado definido',
			body: incapacidades
				? `Hay ${incapacidades} incapacidad(es) activa(s) que condicionan la disponibilidad actual.`
				: alerts
					? `No hay incapacidad activa, pero sí ${alerts} señal(es) que piden lectura cercana.`
					: 'La ficha no muestra bloqueos críticos inmediatos en SST ni alertas abiertas.'
		},
		history: {
			title: latestEvent ? (latestEvent.title || 'Último evento registrado') : 'Sin eventos cronológicos',
			body: latestEvent
				? `${formatPersonaUserDate(latestEvent.date)} · ${latestEvent.desc || 'Hay un antecedente reciente para revisar en detalle.'}`
				: 'Todavía no hay hitos visibles en el timeline de esta persona.'
		},
		next: {
			title: quickDecisionTitle(nextAction, alerts, timeline),
			body: alerts
				? 'Abrí el frente documental o el caso asociado y definí responsable, evidencia y fecha de seguimiento.'
				: timeline && timeline.length
					? 'Usá el timeline como fuente principal para decidir si hace falta documentar, escalar o simplemente monitorear.'
					: 'La siguiente acción útil es consolidar contexto documental o registrar el primer hito de seguimiento.'
		}
	};
}

function quickDecisionTitle(baseTitle, alerts, timeline) {
	if (alerts > 0) return baseTitle;
	if (timeline && timeline.length) return 'Leer secuencia completa';
	return 'Completar contexto base';
}

function renderPersonaPayrollBlock(payrollBlock) {
	if (!payrollBlock || !Object.keys(payrollBlock).length) {
		return '';
	}

	const vacation = payrollBlock.vacation_balance || {};
	const incapacidades = payrollBlock.active_incapacidades || {};
	const deductions = payrollBlock.pending_deductions || {};
	const noveltySummary = payrollBlock.novelty_summary || {};

	return `
		<section class="persona360-panel persona360-payroll-panel">
			<div class="persona360-panel-head persona360-panel-head-tight">
				<div>
					<div class="persona360-panel-label">Nómina y disponibilidad</div>
					<h3>Lectura administrativa</h3>
				</div>
			</div>
			<div class="persona360-payroll-grid">
				${renderPersonaKpiCard('Vacaciones', vacation.days_remaining || 0, vacation.calculation_note || 'Saldo disponible')}
				${renderPersonaKpiCard('Incapacidades', incapacidades.total_estimated || 0, incapacidades.note || 'Impacto activo')}
				${renderPersonaKpiCard('Deducciones', '$' + ((deductions.total_amount || 0).toLocaleString()), (deductions.total_items || 0) + ' ítems pendientes')}
				${renderPersonaKpiCard('Tipos de novedad', Object.keys(noveltySummary).length, 'Últimos 12 meses')}
			</div>
			${Object.keys(noveltySummary).length ? `
				<div class="persona360-mini-grid">
					${Object.entries(noveltySummary).map(function (entry) {
						const type = entry[0];
						const summary = entry[1] || {};
						return `
							<div class="persona360-mini-card">
								<div class="persona360-mini-title">${type}</div>
								<div class="persona360-mini-meta">${summary.count || 0} eventos${summary.total_quantity ? ' · ' + summary.total_quantity + ' total' : ''}</div>
								<div class="persona360-mini-meta">${summary.last_date ? 'Último ' + formatPersonaUserDate(summary.last_date) : 'Sin fecha reciente'}</div>
							</div>
						`;
					}).join('')}
				</div>
			` : ''}
		</section>
	`;
}

function renderPersonaDocumentHub(documentaryContext) {
	if (!documentaryContext || !documentaryContext.title) {
		return '';
	}

	const action = documentaryContext.action || {};
	const canOpen = !!(documentaryContext.available && action.visible);

	return `
		<section class="persona360-panel persona360-document-panel">
			<div class="persona360-panel-head persona360-panel-head-tight persona360-panel-head-stack">
				<div>
					<div class="persona360-panel-label">Carpeta documental</div>
					<h3>${documentaryContext.title}</h3>
				</div>
				<div class="persona360-panel-caption">${documentaryContext.description || ''}</div>
			</div>
			<div class="persona360-document-rail">
				<div class="persona360-document-copy">
					<strong>Conexión documental explícita</strong>
					<span>La carpeta queda integrada como parte de la lectura editorial de la persona, no escondida como acción secundaria.</span>
				</div>
				${canOpen ? `<button class="btn btn-sm btn-default persona-action-btn persona-action-btn-primary" data-action-key="${action.key || documentaryContext.preferred_action_key || 'view_documents'}">Abrir carpeta documental</button>` : '<div class="persona360-empty-inline">Sin acceso documental para este perfil.</div>'}
			</div>
		</section>
	`;
}

function renderPersonaArchiveItem(label, value) {
	return `
		<div class="persona360-archive-item">
			<span>${label}</span>
			<strong>${value}</strong>
		</div>
	`;
}

function renderPersonaTimelineItem(event) {
	return `
		<article class="persona360-timeline-item">
			<div class="persona360-timeline-rail-wrap">
				<div class="persona360-timeline-dot" style="background:${mapColor(event.color)}"></div>
				<div class="persona360-timeline-rail" style="background:${mapColor(event.color)}"></div>
			</div>
			<div class="persona360-timeline-body">
				<div class="persona360-timeline-date">${formatPersonaUserDate(event.date)}</div>
				<h4>${event.title || 'Evento'}</h4>
				<p>${event.desc || 'Sin descripción.'}</p>
				${event.ref ? `<a href="/app/${getDocTypeFromEvent(event)}/${event.ref}">Abrir detalle</a>` : ''}
			</div>
		</article>
	`;
}

function renderPersonaEmptyState(message) {
	return `<div class="persona360-empty-state">${message}</div>`;
}

function clear_contextual_action_buttons(page) {
	page._persona_action_buttons = page._persona_action_buttons || [];
	page._persona_action_buttons.forEach(function (btn) {
		if (btn && btn.remove) btn.remove();
	});
	page._persona_action_buttons = [];
}

function render_contextual_action_buttons(page, contextual_actions, emp_id) {
	clear_contextual_action_buttons(page);

	const actions = (contextual_actions.quick_actions || []).filter(function (action) {
		return action && action.visible;
	});

	actions.forEach(function (action) {
		const btn = page.add_inner_button(action.label, function () {
			executePersonaAction(action, emp_id);
		});
		page._persona_action_buttons.push(btn);
	});
}

function render_contextual_actions_panel(contextual_actions) {
	const actions = (contextual_actions.quick_actions || []).filter(function (action) {
		return action && action.visible;
	});
	if (!actions.length) {
		return '<div class="persona360-empty-inline">No hay acciones directas para este perfil.</div>';
	}

	return actions.map(function (action) {
		return `<button class="btn btn-sm btn-default persona-action-btn" data-action-key="${action.key || ''}">${action.label}</button>`;
	}).join('');
}

function bind_contextual_action_panel($container, contextual_actions, emp_id) {
	const actions = (contextual_actions.quick_actions || []).filter(function (action) {
		return action && action.visible;
	});
	const actionMap = {};
	actions.forEach(function (action) {
		actionMap[action.key] = action;
	});

	$container.off('click', '.persona-action-btn').on('click', '.persona-action-btn', function () {
		const action = actionMap[$(this).data('action-key')];
		if (!action) return;
		executePersonaAction(action, emp_id);
	});
}

function executePersonaAction(action, emp_id) {
	if (action.key === 'view_documents') {
		frappe.route_options = { persona: emp_id };
		frappe.set_route('query-report', 'Person Documents');
		return;
	}

	if (action.doctype) {
		const prefill = Object.assign({}, action.prefill || {}, { empleado: emp_id });
		frappe.new_doc(action.doctype, prefill);
	}
}

function getPersonaStatusTone(status) {
	return {
		Activo: 'positive',
		Inactivo: 'critical',
		Vacaciones: 'cool',
		Incapacitado: 'attention',
		Licencia: 'attention',
		Suspensión: 'attention',
		'Separación del Cargo': 'attention',
		'Recomendación Médica': 'attention',
		Embarazo: 'attention',
		Retirado: 'critical'
	}[status] || 'neutral';
}

function getPersonaInitials(info) {
	const nombres = (info.nombres || '').trim();
	const apellidos = (info.apellidos || '').trim();
	return ((nombres[0] || '') + (apellidos[0] || '')).toUpperCase() || 'NA';
}

function formatPersonaUserDate(value) {
	return value ? frappe.datetime.str_to_user(value) : '-';
}

function mapColor(color_name) {
	const colors = {
		blue: '#64748b',
		red: '#3f3f46',
		orange: '#6b7280',
		purple: '#52525b',
		green: '#18181b'
	};
	return colors[color_name] || '#a1a1aa';
}

function getDocTypeFromEvent(event) {
	const type = event && event.type;
	const module = event && event.module;

	if (module === 'Bienestar Seguimiento Ingreso') return 'bienestar-seguimiento-ingreso';
	if (module === 'Bienestar Evaluacion Periodo Prueba') return 'bienestar-evaluacion-periodo-prueba';
	if (module === 'Bienestar Alerta') return 'bienestar-alerta';
	if (module === 'Bienestar Compromiso') return 'bienestar-compromiso';
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
		.persona360-employee-list-scroll,
		.persona360-timeline-scroll {
			overflow-y: auto;
			overflow-x: hidden;
		}
		.persona360-employee-list-scroll { max-height: 720px; }
		.persona360-timeline-scroll { max-height: 680px; padding-right: 6px; }
	`;
	document.head.appendChild(style);
}
