const CENTRO_DATOS_SUPPORTED = ["Documentos Empleado", "Ficha Empleado", "Actualización Empleado", "Punto de Venta", "Novedad SST", "Estado SST Empleado", "User"];
const OPERATIONAL_PERSON_IDENTITY_TRAY_ROUTE = 'operational_person_identity_tray';

frappe.pages['centro_de_datos'].on_page_load = function (wrapper) {
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: 'Centro de Datos',
        single_column: true
    });

    if (page.clear_breadcrumbs) {
        page.clear_breadcrumbs();
    }
    if (page.add_breadcrumb_item) {
        page.add_breadcrumb_item("Inicio", function () {
            frappe.set_route('app');
        });
    }

    page.add_inner_button('⬅ Volver', function () {
        frappe.set_route('app');
    });

	$(wrapper).find('.page-content').html(`
		<div class="row" style="padding: 20px;">
			<div class="col-md-12">
				<p class="text-muted small" style="margin-bottom: 16px;">Catálogo canónico de cargas críticas: ${CENTRO_DATOS_SUPPORTED.join(', ')}</p>
			</div>
			${render_card("Documental · Subir documentos masivos", "Documentos Empleado", "template_documentos_masivos_manifest.csv", "folder-open", {
				description: "ZIP con manifest CSV + archivos PDF/JPG/PNG para carpeta documental del empleado.",
				extraLinks: [
					{ href: "/assets/hubgh/templates/template_documentos_masivos_instrucciones.csv", label: "Ver estructura ZIP" }
				]
			})}
			${render_card("Empleados", "Ficha Empleado", "template_empleados.csv", "users")}
			${render_card("Actualización Empleados", "Actualización Empleado", "template_actualizacion_empleados.csv", "refresh")}
			${render_card("Puntos de Venta", "Punto de Venta", "template_puntos.csv", "map-pin")}
			${render_card("Novedades", "Novedad SST", "template_novedades.csv", "calendar")}
			${render_card("Estados SST empleados", "Estado SST Empleado", "template_estados_sst_empleados.csv", "heartbeat", {
				description: "Alta/actualización masiva de novedades SST con estado, alertas y opciones de accidente/incapacidad.",
				extraLinks: [
					{ href: "/assets/hubgh/templates/template_estados_sst_opciones.csv", label: "Valores permitidos SST" }
				]
			})}
            ${render_card("Usuarios Sistema", "User", "template_usuarios.csv", "lock")}
			${render_report_card()}
        </div>
    `);

	render_operational_person_identity_cta(wrapper);

    // Bind Events
	$(wrapper).on('click', '.btn-upload', function () {
		let doctype = $(this).data('doctype');
		new frappe.ui.FileUploader({
			on_success: (file) => {
				frappe.call({
					method: "hubgh.hubgh.page.centro_de_datos.centro_de_datos.start_upload_data",
					args: {
						doctype: doctype,
						file_url: file.file_url,
						chunk_size: 50
					},
					freeze: true,
					freeze_message: "Encolando carga masiva...",
					callback: (r) => {
						let data = r.message;
						const supported = (data && data.supported_doctypes) || CENTRO_DATOS_SUPPORTED;
						if (!supported.includes(doctype)) {
							frappe.msgprint({
								title: "Carga no permitida",
								message: `Tipo de carga no soportado para Centro de Datos. Permitidos: ${supported.join(', ')}`,
								indicator: 'red'
							});
							return;
						}
						frappe.show_alert({message: `Carga ${doctype} encolada.`, indicator: 'blue'});
						watchImportJob(data.import_id, doctype);
					}
				});
			}
		});
	});

	$(wrapper).on('click', '.btn-download-report', function () {
		window.open('/api/method/hubgh.hubgh.page.centro_de_datos.centro_de_datos.download_employee_master_report');
	});
}

function formatImportErrors(errors) {
	if (!errors || !errors.length) {
		return '<p class="text-muted">Sin errores reportados.</p>';
	}
	return `<ul style="padding-left: 18px;">${errors.slice(0, 20).map(err => `<li>Fila ${err.row}: ${frappe.utils.escape_html(err.message || '')}</li>`).join('')}</ul>`;
}

function renderImportSummary(status) {
	const counts = status.counts || {};
	return `
		<div>
			<p><strong>Estado:</strong> ${status.status}</p>
			<p><strong>Progreso:</strong> ${status.progress || 0}% (${status.processed_rows || 0}/${status.total_rows || 0})</p>
			<p><strong>Creados:</strong> ${counts.created || 0} &nbsp; <strong>Actualizados:</strong> ${counts.updated || 0} &nbsp; <strong>Omitidos:</strong> ${counts.skipped || 0} &nbsp; <strong>Errores:</strong> ${counts.errors || 0}</p>
			<p class="text-muted">${status.message || ''}</p>
			${formatImportErrors(status.errors || [])}
		</div>
	`;
}

function showImportStatusDialog(status, doctype) {
	frappe.msgprint({
		title: `Carga masiva: ${doctype}`,
		message: renderImportSummary(status),
		indicator: status.status === 'completed' ? (status.counts && status.counts.errors ? 'orange' : 'green') : 'blue',
		wide: true
	});
}

function watchImportJob(importId, doctype) {
	if (!importId) {
		frappe.msgprint({title: 'Carga masiva', message: 'No recibimos el identificador de la carga.', indicator: 'red'});
		return;
	}

	const poll = () => {
		frappe.call({
			method: 'hubgh.hubgh.page.centro_de_datos.centro_de_datos.get_upload_status',
			args: { import_id: importId },
			callback: (response) => {
				const status = response.message || {};
				if (status.status === 'completed' || status.status === 'failed') {
					showImportStatusDialog(status, doctype);
					return;
				}
				frappe.show_alert({message: `${doctype}: ${status.message || 'Procesando...'}`, indicator: 'blue'}, 5);
				setTimeout(poll, 2500);
			}
		});
	};

	poll();
}

function render_operational_person_identity_cta(wrapper) {
	frappe.call({
		method: 'hubgh.hubgh.page.operational_person_identity_tray.operational_person_identity_tray.get_tray_context',
		callback: function(response) {
			const context = response.message || {};
			if (!context.can_view) {
				return;
			}

			$(wrapper).find('.page-content .row').append(render_operational_person_identity_card(context));
			$(wrapper).find('.btn-open-operational-person-identity-tray').on('click', function() {
				frappe.set_route('app', OPERATIONAL_PERSON_IDENTITY_TRAY_ROUTE);
			});
		}
	});
}

function render_operational_person_identity_card(context) {
	const badge = context.can_execute ? 'Lectura + shell de run' : 'Solo lectura';
	return `
		<div class="col-md-3">
			<div class="frappe-card" style="border: 1px solid #d1d8dd; border-radius: 8px; padding: 20px; text-align: center; margin-bottom: 20px; background: linear-gradient(180deg, #ffffff 0%, #f5f7fa 100%); box-shadow: 0 2px 5px rgba(0,0,0,0.05);">
				<div class="icon" style="font-size: 24px; color: #1f4b99; margin-bottom: 10px;">
					<i class="fa fa-random"></i>
				</div>
				<h4>Identidad Persona</h4>
				<p class="text-muted small">Bandeja operativa para snapshot canonico de Ficha Empleado <-> User.</p>
				<p class="text-muted small" style="margin-bottom: 14px;"><strong>${badge}</strong></p>
				<hr>
				<div class="actions" style="display: flex; flex-direction: column; gap: 10px;">
					<button class="btn btn-default btn-sm btn-block btn-open-operational-person-identity-tray">
						<i class="fa fa-external-link"></i> Abrir bandeja
					</button>
				</div>
			</div>
		</div>
	`;
}

function render_report_card() {
	return `
		<div class="col-md-3">
			<div class="frappe-card" style="border: 1px solid #d1d8dd; border-radius: 8px; padding: 20px; text-align: center; margin-bottom: 20px; background: white; box-shadow: 0 2px 5px rgba(0,0,0,0.05);">
				<div class="icon" style="font-size: 24px; color: var(--primary); margin-bottom: 10px;">
					<i class="fa fa-file-excel-o"></i>
				</div>
				<h4>Reporte Empleados</h4>
				<p class="text-muted small">Descargá Excel con cédula, punto, estado, user y resumen de novedades.</p>
				<hr>
				<div class="actions" style="display: flex; flex-direction: column; gap: 10px;">
					<button class="btn btn-default btn-sm btn-block btn-download-report">
						<i class="fa fa-download"></i> Descargar reporte
					</button>
				</div>
			</div>
		</div>
	`;
}

function render_card(title, doctype, template, icon, options = {}) {
	const description = options.description || `Carga masiva de ${title.toLowerCase()}`;
	const extraLinks = (options.extraLinks || []).map((link) => `
		<a href="${link.href}" download class="btn btn-default btn-sm btn-block">
			<i class="fa fa-book"></i> ${link.label}
		</a>
	`).join("");
    return `
        <div class="col-md-3">
            <div class="frappe-card" style="border: 1px solid #d1d8dd; border-radius: 8px; padding: 20px; text-align: center; margin-bottom: 20px; background: white; box-shadow: 0 2px 5px rgba(0,0,0,0.05);">
                <div class="icon" style="font-size: 24px; color: var(--primary); margin-bottom: 10px;">
                    <i class="fa fa-${icon}"></i>
                </div>
                <h4>${title}</h4>
                <p class="text-muted small">${description}</p>
                
                <hr>
                
                <div class="actions" style="display: flex; flex-direction: column; gap: 10px;">
                    <a href="/assets/hubgh/templates/${template}" download class="btn btn-default btn-sm btn-block">
                        <i class="fa fa-download"></i> Descargar Plantilla
                    </a>
					${extraLinks}
                    <button class="btn btn-primary btn-sm btn-block btn-upload" data-doctype="${doctype}">
                        <i class="fa fa-upload"></i> Subir Archivo
                    </button>
                </div>
            </div>
        </div>
    `;
}
