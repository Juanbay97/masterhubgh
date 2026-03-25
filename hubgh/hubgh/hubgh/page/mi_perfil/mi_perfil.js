frappe.pages['mi_perfil'].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Mi Perfil',
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

	const state = {
		area: 'Todos'
	};

	render_page_shell(page, state);
	load_all(page, state);
};

function render_page_shell(page, state) {
	const $container = $(page.main || page.body);
	$container.empty();

	$container.append(`
		<div class="mi-perfil-page" style="padding: 12px 16px 24px; background: #f7fafc; min-height: calc(100vh - 120px);">
			<div class="mi-perfil-cover" style="background: linear-gradient(130deg,#0f172a,#1e3a8a); border-radius: 14px; color: #fff; padding: 16px; margin-bottom: 16px; box-shadow: 0 8px 24px rgba(15,23,42,.18);">
				<div class="d-flex justify-content-between align-items-start flex-wrap" style="gap: 16px;">
					<div class="d-flex align-items-center" style="gap: 14px;">
						<div id="mi-perfil-avatar" style="width:64px;height:64px;border-radius:50%;background:#ffffff1a;display:flex;align-items:center;justify-content:center;font-size:24px;font-weight:700;border:1px solid #ffffff33;">
							👤
						</div>
						<div>
							<div id="mi-perfil-nombre" style="font-size: 24px; font-weight: 700; line-height: 1.1;">Mi Perfil</div>
							<div id="mi-perfil-cargo" style="opacity:.9;">Cargo</div>
							<div id="mi-perfil-punto" style="opacity:.9; font-size: 12px;">Punto</div>
						</div>
					</div>
					<img src="/assets/hubgh/images/logo-home-blanco.png" alt="HubGH" style="height:34px; opacity:.9;" onerror="this.style.display='none'" />
				</div>
				<div id="mi-perfil-chips" style="margin-top: 12px; display: flex; flex-wrap: wrap; gap: 8px;"></div>
				<div style="margin-top: 14px; display: flex; flex-wrap: wrap; gap: 8px;">
					<button class="btn btn-sm btn-light" id="btn-vacaciones">Solicitar vacaciones</button>
					<button class="btn btn-sm btn-outline-light" id="btn-lms">Abrir LMS</button>
					<button class="btn btn-sm btn-outline-light" id="btn-politicas">Ver políticas</button>
				</div>
			</div>

			<div class="row">
				<div class="col-lg-3 col-md-12" id="mi-perfil-left"></div>
				<div class="col-lg-6 col-md-12" id="mi-perfil-center"></div>
				<div class="col-lg-3 col-md-12" id="mi-perfil-right"></div>
			</div>
		</div>
	`);

	bind_actions(page, state);
	render_left_column([], null);
	render_center_column(state, [], []);
	render_right_column(null);
}

function bind_actions(page, state) {
	$(page.main || page.body).off('click', '#btn-vacaciones').on('click', '#btn-vacaciones', function () {
		frappe.msgprint('Módulo de solicitudes no configurado para este entorno.');
	});

	$(page.main || page.body).off('click', '#btn-lms').on('click', '#btn-lms', function () {
		frappe.msgprint('LMS no integrado para este usuario.');
	});

	$(page.main || page.body).off('click', '#btn-politicas').on('click', '#btn-politicas', function () {
		open_policies_dialog();
	});

	$(page.main || page.body).off('click', '.mp-area-tab').on('click', '.mp-area-tab', function () {
		state.area = $(this).data('area') || 'Todos';
		load_feed(state);
	});
}

function load_all(page, state) {
	frappe.call({
		method: 'hubgh.api.my_profile.get_summary',
		callback: function (r) {
			const summary = r.message || {};
			render_cover(summary);
			render_left_column(summary.quick_links || [], summary);
		}
	});

	frappe.call({
		method: 'hubgh.api.my_profile.get_time_summary',
		callback: function (r) {
			render_right_column(r.message || {});
		}
	});

	load_feed(state);
}

function load_feed(state) {
	const args = { limit: 10 };
	if (state.area && state.area !== 'Todos') {
		args.area = state.area;
	}

	frappe.call({
		method: 'hubgh.api.feed.get_posts',
		args: args,
		callback: function (r) {
			render_center_column(state, r.message || [], []);
		}
	});
}

function render_cover(summary) {
	const profile = summary.profile || {};
	const fullName = profile.nombre || frappe.session.user_fullname || 'Colaborador';
	const initials = fullName
		.split(' ')
		.filter(Boolean)
		.slice(0, 2)
		.map((s) => s[0])
		.join('') || '👤';

	$('#mi-perfil-avatar').text(initials.toUpperCase());
	$('#mi-perfil-nombre').text(fullName);
	$('#mi-perfil-cargo').text(profile.cargo || 'Colaborador HubGH');
	$('#mi-perfil-punto').text(profile.punto || 'Punto por definir');

	const chips = summary.chips || [];
	$('#mi-perfil-chips').html(
		chips.map((chip) => {
			const color = chip.color || '#0ea5e9';
			return `<span style="background:${color};color:#fff;border-radius:999px;padding:4px 10px;font-size:11px;font-weight:600;">${frappe.utils.escape_html(chip.label || '')}</span>`;
		}).join('')
	);
}

function render_left_column(quickLinks, summary) {
	const profile = (summary && summary.profile) || {};
	const emptyState = (summary && summary.empty_state) || {};
	const about = profile.sobre_mi || emptyState.message || 'Perfil interno sin información adicional.';

	$('#mi-perfil-left').html(`
		<div style="display:grid;gap:12px;">
			<div class="card" style="border:none;border-radius:12px;">
				<div class="card-body">
					<h6 style="font-weight:700;">Sobre mí</h6>
					<p class="text-muted" style="margin:0;font-size:13px;line-height:1.5;">${frappe.utils.escape_html(about)}</p>
				</div>
			</div>
			<div class="card" style="border:none;border-radius:12px;">
				<div class="card-body">
					<h6 style="font-weight:700;">Accesos rápidos</h6>
					<div style="display:grid;gap:8px;margin-top:8px;">
						${(quickLinks || []).map(link => `
							<a href="${frappe.utils.escape_html(link.url || '#')}" class="btn btn-sm btn-light text-left" style="justify-content:flex-start;">
								${frappe.utils.escape_html(link.icon || '🔗')} ${frappe.utils.escape_html(link.label || 'Enlace')}
							</a>
						`).join('') || '<div class="text-muted small">Sin accesos configurados</div>'}
					</div>
				</div>
			</div>
		</div>
	`);
}

function render_center_column(state, posts, solicitudes) {
	const tabs = ['Todos', 'Operación', 'Talento', 'Bienestar'];

	$('#mi-perfil-center').html(`
		<div style="display:grid;gap:12px;">
			<div class="card" style="border:none;border-radius:12px;">
				<div class="card-body">
					<div class="d-flex justify-content-between align-items-center flex-wrap" style="gap:8px;">
						<h6 style="font-weight:700;margin:0;">Feed interno</h6>
						<div style="display:flex;gap:6px;flex-wrap:wrap;">
							${tabs.map(area => `
								<button class="btn btn-xs ${state.area === area ? 'btn-primary' : 'btn-default'} mp-area-tab" data-area="${area}">${area}</button>
							`).join('')}
						</div>
					</div>
					<div style="display:grid;gap:10px;margin-top:10px;">
						${(posts || []).map(p => `
							<div style="border:1px solid #e2e8f0;border-radius:10px;padding:10px;background:#fff;">
								<div class="d-flex justify-content-between align-items-center">
									<strong>${frappe.utils.escape_html(p.titulo || 'Comunicado')}</strong>
									<small class="text-muted">${p.area ? frappe.utils.escape_html(p.area) : 'General'}</small>
								</div>
								<div class="text-muted small" style="margin-top:4px;">${frappe.utils.escape_html(p.cuerpo_corto || '')}</div>
								<div class="text-muted" style="font-size:11px;margin-top:6px;">${p.fecha_publicacion ? frappe.datetime.str_to_user(p.fecha_publicacion) : ''}</div>
							</div>
						`).join('')}
					</div>
				</div>
			</div>

			<div class="card" style="border:none;border-radius:12px;">
				<div class="card-body">
					<h6 style="font-weight:700;">Solicitudes recientes</h6>
					<div style="margin-top:8px;display:grid;gap:8px;">
						${(solicitudes || []).map(s => `
							<div style="border-left:3px solid ${s.color};padding:8px 10px;background:#f8fafc;border-radius:8px;">
								<div class="d-flex justify-content-between"><strong>${frappe.utils.escape_html(s.titulo)}</strong><small class="text-muted">${frappe.utils.escape_html(s.fecha)}</small></div>
								<div class="small text-muted">${frappe.utils.escape_html(s.estado)}</div>
							</div>
						`).join('') || '<div class="text-muted small">Sin solicitudes recientes.</div>'}
					</div>
				</div>
			</div>
		</div>
	`);
}

function render_right_column(timeSummary) {
	const kpi = timeSummary || {};
	const emptyState = kpi.empty_state || {};
	$('#mi-perfil-right').html(`
		<div style="display:grid;gap:12px;">
			<div class="card" style="border:none;border-radius:12px;">
				<div class="card-body">
					<h6 style="font-weight:700;">Tiempo trabajado</h6>
					${kpi.empty ? `<div class="small text-muted" style="margin-top:8px;">${frappe.utils.escape_html(emptyState.message || 'Sin datos de tiempo disponibles.')}</div>` : ''}
					<div class="small text-muted" style="display:grid;gap:6px;margin-top:8px;">
						<div>Programadas: <strong>${fmt_num(kpi.programadas)}</strong> h</div>
						<div>Trabajadas: <strong>${fmt_num(kpi.trabajadas)}</strong> h</div>
						<div>Extra: <strong>${fmt_num(kpi.extra)}</strong> h</div>
						<div>Nocturnas: <strong>${fmt_num(kpi.nocturnas)}</strong> h</div>
						<div>Llegadas tarde: <strong>${fmt_num(kpi.llegadas_tarde, 0)}</strong></div>
						<div>Ausencias: <strong>${fmt_num(kpi.ausencias, 0)}</strong></div>
					</div>
				</div>
			</div>

			<div class="card" style="border:none;border-radius:12px;">
				<div class="card-body">
					<h6 style="font-weight:700;">Notificaciones</h6>
					<ul class="small text-muted" style="padding-left: 16px; margin:8px 0 0;">
						<li>Recuerda validar tu documentación semanal.</li>
						<li>Tu perfil de seguridad está al día.</li>
						<li>Novedades internas publicadas hoy.</li>
					</ul>
				</div>
			</div>

			<div class="card" style="border:none;border-radius:12px;">
				<div class="card-body">
					<h6 style="font-weight:700;">Próximos cursos</h6>
					<div class="small text-muted" style="display:grid;gap:8px;margin-top:8px;">
						<div>✅ Inducción corporativa (completado)</div>
						<div>🕒 Buenas prácticas operativas (pendiente)</div>
						<div>🕒 Seguridad y autocuidado (pendiente)</div>
					</div>
				</div>
			</div>
		</div>
	`);
}

function open_policies_dialog() {
	frappe.call({
		method: 'hubgh.api.policies.search',
		args: { query: null, filters: { vigente: 1 } },
		callback: function (r) {
			const rows = r.message || [];
			const html = rows.length
				? `<div style="display:grid;gap:8px;max-height:360px;overflow:auto;">${rows.map(row => `
					<div style="border:1px solid #e2e8f0;border-radius:10px;padding:10px;">
						<div><strong>${frappe.utils.escape_html(row.titulo || '')}</strong></div>
						<div class="small text-muted">${frappe.utils.escape_html(row.categoria || 'General')} · v${frappe.utils.escape_html(row.version || '1.0')}</div>
						${row.archivo ? `<a class="small" href="${frappe.utils.escape_html(row.archivo)}" target="_blank">Abrir documento</a>` : ''}
					</div>
				`).join('')}</div>`
				: '<div class="text-muted small">Sin políticas disponibles para este usuario.</div>';

			frappe.msgprint({
				title: 'Políticas vigentes',
				message: html,
				wide: true
			});
		}
	});
}

function fmt_num(value, decimals) {
	const d = decimals === undefined ? 1 : decimals;
	const n = Number(value || 0);
	return n.toFixed(d);
}
