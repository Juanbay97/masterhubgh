const OPERATIONAL_PERSON_IDENTITY_CATEGORIES = [
	{
		key: 'employees_without_user',
		label: 'Empleados sin user',
		copy: 'Casos seguros 1:1 para revisar antes de habilitar reconciliacion.',
		emptyTitle: 'No hay empleados sin user en el snapshot actual.',
	},
	{
		key: 'users_without_employee',
		label: 'Users sin empleado',
		copy: 'Users internos que no encuentran Ficha Empleado canonica.',
		emptyTitle: 'No hay users sin empleado en el snapshot actual.',
	},
	{
		key: 'conflicts',
		label: 'Conflictos',
		copy: 'Coincidencias ambiguas o datos historicos que requieren criterio humano.',
		emptyTitle: 'No hay conflictos visibles en este snapshot.',
	},
	{
		key: 'pending',
		label: 'Pendientes',
		copy: 'Casos bloqueados por datos incompletos o email/documento invalido.',
		emptyTitle: 'No hay pendientes visibles en este snapshot.',
	},
	{
		key: 'fallback_only',
		label: 'Fallback only',
		copy: 'Matches por email fallback que siguen necesitando normalizacion.',
		emptyTitle: 'No hay matches fallback-only en este snapshot.',
	},
	{
		key: 'already_canonical',
		label: 'Ya canonicos',
		copy: 'Relaciones ya resueltas que sirven como linea base del barrido.',
		emptyTitle: 'No hay relaciones canonicas visibles en este corte.',
	},
];

const OPERATIONAL_PERSON_IDENTITY_PAGE_SIZE = 20;

frappe.pages['operational_person_identity_tray'].on_page_load = function(wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Identidad persona - bandeja operativa',
		single_column: true,
	});

	wrapper.operationalPersonIdentityTray = new OperationalPersonIdentityTray(wrapper, page);
};

class OperationalPersonIdentityTray {
	constructor(wrapper, page) {
		this.wrapper = $(wrapper);
		this.page = page;
		this.context = null;
		this.snapshot = null;
		this.currentCategory = 'employees_without_user';
		this.searchTerm = '';
		this.offsetByCategory = {};

		this.makeFilters();
		this.makeActions();
		this.renderLoading('Validando acceso a la bandeja...');
		this.loadContext();
	}

	makeFilters() {
		this.page.add_field({
			fieldname: 'snapshot_search',
			label: __('Buscar'),
			fieldtype: 'Data',
			change: () => {
				this.searchTerm = this.getFieldValue('snapshot_search') || '';
				this.offsetByCategory[this.currentCategory] = 0;
				this.refresh();
			},
		});
	}

	makeActions() {
		this.page.set_primary_action(__('Actualizar snapshot'), () => this.refresh());
		this.page.add_inner_button(__('Volver a Centro de Datos'), () => {
			frappe.set_route('app', 'centro_de_datos');
		});
	}

	getFieldValue(fieldname) {
		const field = this.page.fields_dict && this.page.fields_dict[fieldname];
		return field && typeof field.get_value === 'function' ? field.get_value() : null;
	}

	loadContext() {
		frappe.call({
			method: 'hubgh.hubgh.page.operational_person_identity_tray.operational_person_identity_tray.get_tray_context',
			callback: (response) => {
				this.context = response.message || {};
				if (!this.context.can_view) {
					this.renderUnauthorized();
					return;
				}
				this.refresh();
			},
			error: () => {
				this.renderError('No pudimos validar el acceso a la bandeja.');
			},
		});
	}

	refresh() {
		if (!this.context || !this.context.can_view) {
			return;
		}

		this.renderLoading('Actualizando snapshot operativo...');
		frappe.call({
			method: 'hubgh.hubgh.page.operational_person_identity_tray.operational_person_identity_tray.get_snapshot',
			args: {
				filters: JSON.stringify({
					category: this.currentCategory,
					search: this.searchTerm,
					limit: OPERATIONAL_PERSON_IDENTITY_PAGE_SIZE,
					offset: this.offsetByCategory[this.currentCategory] || 0,
				}),
			},
			callback: (response) => {
				this.snapshot = response.message || {};
				this.render();
			},
			error: (error) => {
				const message = error && error.message ? error.message : 'No pudimos cargar el snapshot.';
				this.renderError(message);
			},
		});
	}

	render() {
		const snapshot = this.snapshot || {};
		const rowsByCategory = snapshot.rows_by_category || {};
		const activeBucket = rowsByCategory[this.currentCategory] || { rows: [], total: 0, offset: 0, limit: OPERATIONAL_PERSON_IDENTITY_PAGE_SIZE, has_more: false };
		const traceability = snapshot.traceability || {};
		const activeMeta = this.getCategoryMeta(this.currentCategory);
		const tableRows = activeBucket.rows || [];
		const generatedAt = snapshot.generated_at ? frappe.datetime.str_to_user(snapshot.generated_at) : 'Sin snapshot';

		const html = `
			<div class="opi-shell">
				<div class="opi-hero">
					<div>
						<div class="opi-kickers"><span>Centro de Datos</span><span>Identidad persona</span></div>
						<h3 class="opi-title">Snapshot operativo del vinculo Ficha Empleado <-> User</h3>
						<p class="opi-copy">La vista consume el snapshot canonico del backend. No reclasifica identidades en frontend y deja visible que casos estan listos, bloqueados o en conflicto.</p>
					</div>
					<div class="opi-hero-side">
						<div class="opi-stamp">Snapshot: <strong>${generatedAt}</strong></div>
						<div class="opi-stamp">Barrido: ${traceability.total_rows_after_dedupe || 0} casos deduplicados</div>
						<div class="opi-run-shell ${this.context.can_execute ? 'can-execute' : 'read-only'}">
							<button class="btn btn-sm btn-danger opi-run-shell-btn" ${this.context.can_execute ? '' : 'disabled'}>${this.context.can_execute ? 'Ejecutar run manual' : 'Run manual no disponible'}</button>
							<p class="text-muted small mb-0">${this.getManualRunCopy()}</p>
						</div>
					</div>
				</div>

				<div class="row opi-kpi-grid">
					${this.renderKpiCard('Empleados sin user', this.getKpiValue('employees_without_user'), 'Casos employee-driven sin User canonico')}
					${this.renderKpiCard('Users sin empleado', this.getKpiValue('users_without_employee'), 'Users internos huerfanos en el snapshot')}
					${this.renderKpiCard('Conflictos', this.getKpiValue('conflicts'), 'Coincidencias ambiguas que NO se autocorrigen')}
					${this.renderKpiCard('Pendientes', this.getKpiValue('pending'), 'Casos sin datos suficientes para cerrar 1:1')}
					${this.renderKpiCard('Fallback only', this.getKpiValue('fallback_only'), 'Matches por email fallback que requieren criterio')}
					${this.renderKpiCard('Accionables', this.getKpiValue('actionable_safe'), 'Suma de empleados sin user + users sin empleado')}
				</div>

				<div class="opi-context-row">
					<div class="opi-context-card">
						<h5>Lectura actual</h5>
						<p class="text-muted mb-0">Empleado scan: ${traceability.employee_rows_scanned || 0} | User scan: ${traceability.user_rows_scanned || 0} | Users excluidos: ${traceability.excluded_users || 0}</p>
					</div>
					<div class="opi-context-card">
						<h5>Categoria activa</h5>
						<p class="text-muted mb-1"><strong>${activeMeta.label}</strong></p>
						<p class="text-muted mb-0">${activeMeta.copy}</p>
					</div>
				</div>

				<div class="opi-category-row">
					${OPERATIONAL_PERSON_IDENTITY_CATEGORIES.map((category) => this.renderCategoryButton(category, rowsByCategory[category.key] || {})).join('')}
				</div>

				<div class="opi-table-shell">
					<div class="opi-table-head">
						<div>
							<div class="opi-table-title">${activeMeta.label}</div>
							<div class="opi-table-copy">${activeMeta.copy}</div>
						</div>
						<div class="opi-table-meta">Mostrando ${tableRows.length} de ${activeBucket.total || 0}</div>
					</div>
					${tableRows.length ? this.renderTable(tableRows) : this.renderEmptyState(activeMeta)}
					${this.renderPager(activeBucket)}
				</div>
			</div>
		`;

		this.page.main.html(html);
		this.bindEvents(activeBucket);
	}

	renderKpiCard(label, value, copy) {
		return `
			<div class="col-md-4">
				<div class="card opi-kpi-card">
					<div class="card-body">
						<div class="opi-kpi-value">${value}</div>
						<div class="opi-kpi-label">${label}</div>
						<div class="text-muted small">${copy}</div>
					</div>
				</div>
			</div>
		`;
	}

	renderCategoryButton(category, bucket) {
		const total = bucket.total || this.getKpiValue(category.key);
		const activeClass = this.currentCategory === category.key ? 'active' : '';
		return `
			<button class="btn btn-default opi-category-btn ${activeClass}" data-category="${category.key}">
				<span>${category.label}</span>
				<strong>${total}</strong>
			</button>
		`;
	}

	renderTable(rows) {
		return `
			<div class="opi-table-scroll">
				<table class="table table-striped table-bordered opi-table">
					<thead>
						<tr>
							<th>Empleado</th>
							<th>User</th>
							<th>Documento</th>
							<th>Email</th>
							<th>Motivo</th>
							<th>Origen</th>
							<th>Warnings</th>
						</tr>
					</thead>
					<tbody>
						${rows.map((row) => `
							<tr>
								<td>${this.renderIdentityCell(row.employee, row.stable_key)}</td>
								<td>${this.renderIdentityCell(row.user, row.source)}</td>
								<td>${frappe.utils.escape_html(row.document || '-')}</td>
								<td>${frappe.utils.escape_html(row.email || '-')}</td>
								<td>${frappe.utils.escape_html(row.reason || this.humanizeReason(row))}</td>
								<td>${frappe.utils.escape_html((row.scan_sources || []).join(', ') || row.source || '-')}</td>
								<td>${frappe.utils.escape_html((row.warnings || []).join(', ') || '-')}</td>
							</tr>
						`).join('')}
					</tbody>
				</table>
			</div>
		`;
	}

	renderIdentityCell(primaryValue, secondaryValue) {
		const main = frappe.utils.escape_html(primaryValue || '-');
		const meta = frappe.utils.escape_html(secondaryValue || 'sin referencia');
		return `<div class="opi-identity-main">${main}</div><div class="opi-identity-meta">${meta}</div>`;
	}

	renderEmptyState(category) {
		return `
			<div class="opi-empty-state text-center text-muted">
				<h5>${category.emptyTitle}</h5>
				<p class="mb-2">${category.copy}</p>
				<p class="mb-0">Proximo paso: actualiza el snapshot o cambia la busqueda para revisar otra categoria.</p>
			</div>
		`;
	}

	renderPager(bucket) {
		const offset = bucket.offset || 0;
		const limit = bucket.limit || OPERATIONAL_PERSON_IDENTITY_PAGE_SIZE;
		const hasPrevious = offset > 0;
		const hasMore = !!bucket.has_more;
		return `
			<div class="opi-pager">
				<button class="btn btn-sm btn-default opi-page-prev" ${hasPrevious ? '' : 'disabled'}>Anterior</button>
				<span class="text-muted">Offset ${offset} | Limite ${limit}</span>
				<button class="btn btn-sm btn-default opi-page-next" ${hasMore ? '' : 'disabled'}>Siguiente</button>
			</div>
		`;
	}

	renderLoading(message) {
		this.page.main.html(`<div class="text-muted p-4">${message}</div>`);
	}

	renderUnauthorized() {
		this.page.main.html(`
			<div class="card opi-empty-state">
				<div class="card-body text-center p-5">
					<h4>No tenes acceso a la bandeja operativa</h4>
					<p class="text-muted mb-0">La vista y el snapshot de identidad persona solo se entregan a roles autorizados.</p>
				</div>
			</div>
		`);
	}

	renderError(message) {
		this.page.main.html(`
			<div class="alert alert-warning mt-3">
				<strong>Snapshot no disponible.</strong> ${frappe.utils.escape_html(message || 'Error inesperado.')}
			</div>
		`);
	}

	bindEvents(activeBucket) {
		this.wrapper.find('.opi-category-btn').on('click', (event) => {
			const category = $(event.currentTarget).data('category');
			this.currentCategory = category;
			this.offsetByCategory[category] = 0;
			this.refresh();
		});

		this.wrapper.find('.opi-page-prev').on('click', () => {
			const nextOffset = Math.max((activeBucket.offset || 0) - (activeBucket.limit || OPERATIONAL_PERSON_IDENTITY_PAGE_SIZE), 0);
			this.offsetByCategory[this.currentCategory] = nextOffset;
			this.refresh();
		});

		this.wrapper.find('.opi-page-next').on('click', () => {
			const nextOffset = (activeBucket.offset || 0) + (activeBucket.limit || OPERATIONAL_PERSON_IDENTITY_PAGE_SIZE);
			this.offsetByCategory[this.currentCategory] = nextOffset;
			this.refresh();
		});

		this.wrapper.find('.opi-run-shell-btn').on('click', () => {
			if (!this.context.can_execute) {
				frappe.msgprint({
					title: 'Run manual no disponible',
					message: this.getManualRunCopy(),
					indicator: 'orange',
				});
				return;
			}

			this.promptManualRun();
		});
	}

	getManualRunCopy() {
		if (this.context && this.context.can_execute) {
			return 'Accion write-capable habilitada desde backend. Requiere confirmacion explicita y respeta el guard server-side.';
		}
		if (this.context && this.context.manual_run_mode === 'disabled') {
			return 'Vista solo lectura. El run manual esta apagado por feature flag server-side.';
		}
		return 'Vista solo lectura. La ejecucion manual sigue reservada a roles autorizados.';
	}

	getSnapshotId() {
		return ((this.snapshot || {}).generated_at || '').trim();
	}

	getManualConfirmationText(snapshotId) {
		const template = ((this.context || {}).manual_confirmation_template || 'MANUAL:{snapshot_id}').trim();
		return template.replace('{snapshot_id}', snapshotId);
	}

	promptManualRun() {
		const snapshotId = this.getSnapshotId();
		if (!snapshotId) {
			frappe.msgprint({
				title: 'Snapshot requerido',
				message: 'Actualiza el snapshot antes de ejecutar la reconciliacion manual.',
				indicator: 'orange',
			});
			return;
		}

		const confirmText = this.getManualConfirmationText(snapshotId);
		frappe.confirm(
			`Vas a ejecutar la reconciliacion manual sobre el snapshot ${frappe.utils.escape_html(snapshotId)}. Esta accion puede crear o enlazar users.`,
			() => {
				frappe.prompt([
					{
						fieldname: 'confirm_text',
						fieldtype: 'Data',
						label: 'Escribi la confirmacion exacta',
						reqd: 1,
						description: `Repeti exactamente: ${confirmText}`,
					},
				], (values) => {
					this.runManualReconciliation(snapshotId, values.confirm_text || '');
				}, 'Confirmar run manual', 'Ejecutar');
			}
		);
	}

	runManualReconciliation(snapshotId, confirmText) {
		frappe.call({
			method: 'hubgh.hubgh.page.operational_person_identity_tray.operational_person_identity_tray.run_manual_reconciliation',
			args: {
				snapshot_id: snapshotId,
				confirm_text: confirmText,
			},
			freeze: true,
			freeze_message: 'Ejecutando reconciliacion manual...',
			callback: (response) => {
				const result = response.message || {};
				if (result.status === 'rejected_active_run') {
					const activeRun = result.active_run || {};
					frappe.msgprint({
						title: 'Run ya activo',
						message: `Ya existe una ejecucion activa iniciada por ${activeRun.started_by || 'otro operador'}.`,
						indicator: 'orange',
					});
					return;
				}

				const counts = ((result.report || {}).counts || {});
				frappe.msgprint({
					title: 'Run manual completado',
					message: `Mutaciones: ${counts.mutations_applied || 0} | Users creados: ${counts.users_created || 0} | Enlaces completados: ${counts.links_completed || 0} | Saltados: ${counts.skipped_rows || 0}`,
					indicator: 'green',
				});
				this.refresh();
			},
			error: (error) => {
				const message = error && error.message ? error.message : 'No pudimos ejecutar la reconciliacion manual.';
				frappe.msgprint({
					title: 'Run manual no ejecutado',
					message,
					indicator: 'red',
				});
			},
		});
	}

	getKpiValue(key) {
		return ((this.snapshot || {}).kpis || {})[key] || 0;
	}

	getCategoryMeta(key) {
		return OPERATIONAL_PERSON_IDENTITY_CATEGORIES.find((category) => category.key === key) || OPERATIONAL_PERSON_IDENTITY_CATEGORIES[0];
	}

	humanizeReason(row) {
		if (row.conflict) {
			return 'Conflicto canonico';
		}
		if (row.pending) {
			return 'Pendiente por datos incompletos';
		}
		if (row.fallback) {
			return 'Match fallback por email';
		}
		return 'Snapshot canonico';
	}
}
