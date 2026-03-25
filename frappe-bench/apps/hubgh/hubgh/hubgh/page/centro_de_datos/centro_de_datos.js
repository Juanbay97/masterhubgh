const CENTRO_DATOS_SUPPORTED = ["Ficha Empleado", "Punto de Venta", "Novedad SST", "User"];

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
			${render_card("Empleados", "Ficha Empleado", "template_empleados.csv", "users")}
			${render_card("Puntos de Venta", "Punto de Venta", "template_puntos.csv", "map-pin")}
			${render_card("Novedades", "Novedad SST", "template_novedades.csv", "calendar")}
            ${render_card("Usuarios Sistema", "User", "template_usuarios.csv", "lock")}
        </div>
    `);

    // Bind Events
    $(wrapper).on('click', '.btn-upload', function () {
        let doctype = $(this).data('doctype');
        new frappe.ui.FileUploader({
            on_success: (file) => {
                frappe.call({
                    method: "hubgh.hubgh.page.centro_de_datos.centro_de_datos.upload_data",
                    args: {
                        doctype: doctype,
                        file_url: file.file_url
                    },
                    freeze: true,
                    freeze_message: "Procesando archivo...",
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
						if (data.errors.length > 0) {
							frappe.msgprint({
								title: `Importación Parcial: ${data.success} exitosos`,
                                message: data.errors.join("<br>"),
                                indicator: 'orange'
                            });
                        } else {
                            frappe.msgprint({
                                title: "Éxito",
                                message: `Se importaron ${data.success} registros correctamente.`,
                                indicator: 'green'
                            });
                        }
                    }
                });
            }
        });
    });
}

function render_card(title, doctype, template, icon) {
    return `
        <div class="col-md-3">
            <div class="frappe-card" style="border: 1px solid #d1d8dd; border-radius: 8px; padding: 20px; text-align: center; margin-bottom: 20px; background: white; box-shadow: 0 2px 5px rgba(0,0,0,0.05);">
                <div class="icon" style="font-size: 24px; color: var(--primary); margin-bottom: 10px;">
                    <i class="fa fa-${icon}"></i>
                </div>
                <h4>${title}</h4>
                <p class="text-muted small">Carga masiva de ${title.toLowerCase()}</p>
                
                <hr>
                
                <div class="actions" style="display: flex; flex-direction: column; gap: 10px;">
                    <a href="/assets/hubgh/templates/${template}" download class="btn btn-default btn-sm btn-block">
                        <i class="fa fa-download"></i> Descargar Plantilla
                    </a>
                    <button class="btn btn-primary btn-sm btn-block btn-upload" data-doctype="${doctype}">
                        <i class="fa fa-upload"></i> Subir Archivo
                    </button>
                </div>
            </div>
        </div>
    `;
}
