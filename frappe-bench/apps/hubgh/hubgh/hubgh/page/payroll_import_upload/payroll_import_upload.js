frappe.pages['payroll_import_upload'].on_page_load = function(wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __('Nómina - Cargar novedades'),
		single_column: true,
	});

	const targetRoute = '/payroll_import_upload';
	const fallbackRoute = '/app/payroll-import-batch';
	let redirectHandled = false;

	const renderInfo = (message, isFallback = false) => {
		const ctaHtml = isFallback
			? `
				<div class="payroll-upload-fallback-actions mt-3">
					<a class="btn btn-primary" href="${fallbackRoute}">${__('Ver lotes cargados')}</a>
					<a class="btn btn-default" href="${targetRoute}">${__('Reintentar cargador web')}</a>
				</div>
			`
			: '';

		page.main.html(`
			<div class="payroll-import-upload-redirect p-4">
				<div class="payroll-upload-hero mb-3">
					<div>
						<div class="payroll-upload-kickers"><span>${__('Nómina')}</span><span>${__('Cargar novedades')}</span></div>
						<h3 class="payroll-upload-title">${__('Entrada rápida para cargar, validar y seguir el flujo')}</h3>
						<p class="payroll-upload-copy">${__('Este acceso mantiene el recorrido corto: cargar archivo, validar el lote, revisar novedades y cerrar la aprobación final sin cambiar APIs ni rutas.')}</p>
					</div>
					<div class="payroll-upload-hero-actions">
						<a class="btn btn-primary" href="${targetRoute}">${__('Abrir cargador web')}</a>
						<a class="btn btn-default" href="${fallbackRoute}">${__('Ver lotes cargados')}</a>
					</div>
				</div>

				<div class="alert ${isFallback ? 'alert-warning' : 'alert-info'} mb-4">
					<strong>${message}</strong>
					<div class="mt-2">${isFallback
						? __('No pudimos abrir el cargador web. Te llevamos al listado de lotes como alternativa segura.')
						: __('Si no abre automáticamente, usá el botón principal o esperá unos segundos.')}</div>
				</div>

				<div class="payroll-upload-grid mb-4">
					<div class="payroll-upload-card">
						<div class="payroll-upload-card-title">${__('1. Subir archivo')}</div>
						<div class="text-muted">${__('Usá el archivo original tal como llega desde la fuente para evitar diferencias operativas.')}</div>
					</div>
					<div class="payroll-upload-card">
						<div class="payroll-upload-card-title">${__('2. Validar el lote')}</div>
						<div class="text-muted">${__('Revisá la vista previa, los errores detectados y el estado final antes de avanzar.')}</div>
					</div>
					<div class="payroll-upload-card">
						<div class="payroll-upload-card-title">${__('3. Seguir el flujo')}</div>
						<div class="text-muted">${__('Abrí revisión inicial y después la aprobación final cuando el lote quede procesado.')}</div>
					</div>
				</div>

				<div class="payroll-upload-links">
					<a class="btn btn-default" href="/app/payroll_tc_tray">${__('Abrir revisión inicial')}</a>
					<a class="btn btn-default" href="/app/payroll_tp_tray">${__('Abrir aprobación final')}</a>
				</div>
				${ctaHtml}
			</div>
		`);
	};

	const goToFallback = () => {
		if (redirectHandled) {
			return;
		}

		redirectHandled = true;
		renderInfo(__('No se pudo abrir el cargador web.'), true);
		window.setTimeout(() => {
			window.location.href = fallbackRoute;
		}, 900);
	};

	const tryOpenUploader = async () => {
		if (redirectHandled) {
			return;
		}

		renderInfo(__('Redirigiendo al cargador web de nómina...'));

		try {
			const response = await window.fetch(targetRoute, {
				method: 'GET',
				credentials: 'same-origin',
				headers: {
					'X-Requested-With': 'XMLHttpRequest',
				},
			});

			if (response.ok) {
				redirectHandled = true;
				window.location.href = targetRoute;
				return;
			}
		} catch (error) {
			// Fall through to fallback route.
		}

		goToFallback();
	};

	page.set_primary_action(__('Abrir cargador'), () => {
		redirectHandled = false;
		void tryOpenUploader();
	});

	page.add_action_item(__('Ver lotes cargados'), () => {
		frappe.set_route('List', 'Payroll Import Batch');
	});

	renderInfo(__('Redirigiendo al cargador web de nómina...'));
	window.setTimeout(() => {
		void tryOpenUploader();
	}, 250);
};
