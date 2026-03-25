
frappe.pages['roadmap'].on_page_load = function (wrapper) {
    console.log("Roadmap Page Loaded");
    var page = frappe.ui.make_app_page({
        parent: wrapper,
        title: '🗺️ Roadmap del Equipo',
        single_column: true
    });

    // Filtros
    let $filters = $(`
        <div class="row mb-4" style="background: #f8f9fa; padding: 15px; border-radius: 5px;">
            <div class="col-md-4">
                <div class="form-group">
                    <label>Punto de Venta</label>
                    <select class="form-control" id="filter-pdv" style="width: 100%;">
                        <option value="">Todos los Puntos</option>
                    </select>
                </div>
            </div>
            <div class="col-md-4">
                <div class="form-group">
                    <label>Empleado</label>
                    <select class="form-control" id="filter-empleado" style="width: 100%;">
                        <option value="">Todos los Empleados</option>
                    </select>
                </div>
            </div>
            <div class="col-md-3">
                <div class="form-group">
                    <label>Días hacia adelante</label>
                    <select class="form-control" id="filter-days" style="width: 100%;">
                        <option value="7">7 días</option>
                        <option value="15">15 días</option>
                        <option value="30" selected>30 días</option>
                        <option value="60">60 días</option>
                        <option value="90">90 días</option>
                    </select>
                </div>
            </div>
            <div class="col-md-1">
                <div class="form-group">
                    <label>&nbsp;</label>
                    <button class="btn btn-primary btn-block" id="btn-refresh">
                        <i class="fa fa-refresh"></i>
                    </button>
                </div>
            </div>
        </div>
    `);
    
    $(page.body).append($filters);

    // Inicializar filtros
    initializeFilters(page);

    // Botón de actualizar
    $('#btn-refresh').on('click', function() {
        render_roadmap(page);
    });

    // Cambios en filtros
    $('#filter-pdv, #filter-empleado, #filter-days').on('change', function() {
        render_roadmap(page);
    });

    // Cargar datos iniciales
    render_roadmap(page);
}

function initializeFilters(page) {
    // Cargar Puntos de Venta
    frappe.call({
        method: "frappe.client.get_list",
        args: {
            doctype: "Punto de Venta",
            fields: ["name", "nombre_pdv"],
            order_by: "nombre_pdv asc"
        },
        callback: function(r) {
            if (r.message) {
                r.message.forEach(function(pdv) {
                    $('#filter-pdv').append(`<option value="${pdv.name}">${pdv.nombre_pdv}</option>`);
                });
            }
        }
    });

    // Cargar Empleados
    frappe.call({
        method: "frappe.client.get_list",
        args: {
            doctype: "Ficha Empleado",
            fields: ["name", "nombres", "apellidos"],
            order_by: "nombres asc"
        },
        callback: function(r) {
            if (r.message) {
                r.message.forEach(function(emp) {
                    $('#filter-empleado').append(`<option value="${emp.name}">${emp.nombres} ${emp.apellidos}</option>`);
                });
            }
        }
    });
}

function render_roadmap(page) {
    let pdv_filter = $('#filter-pdv').val() || null;
    let empleado_filter = $('#filter-empleado').val() || null;
    let days_ahead = $('#filter-days').val() || 30;

    frappe.call({
        method: "hubgh.hubgh.page.roadmap.roadmap.get_roadmap_data",
        args: {
            pdv_filter: pdv_filter,
            empleado_filter: empleado_filter,
            days_ahead: days_ahead
        },
        callback: function(r) {
            if (r.message) {
                console.log("Roadmap Data Received:", r.message);
                let data = r.message;
                let $container = $(page.body).find('.roadmap-container');
                
                if ($container.length === 0) {
                    $container = $('<div class="roadmap-container"></div>');
                    $(page.body).append($container);
                } else {
                    $container.empty();
                }

                // Header Stats
                $container.append(`
                    <div class="row mb-4">
                        <div class="col-md-12">
                            <div class="dashboard-card-stat" style="padding: 20px; background: white; border-radius: 5px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                                <h4>📊 Resumen del Roadmap</h4>
                                <p class="text-muted mb-0">
                                    <strong>Total de eventos:</strong> ${data.total_items} | 
                                    <strong>Período:</strong> ${frappe.datetime.str_to_user(data.date_range.start)} - ${frappe.datetime.str_to_user(data.date_range.end)}
                                </p>
                            </div>
                        </div>
                    </div>
                `);

                if (data.items.length === 0) {
                    $container.append(`
                        <div class="alert alert-info">
                            <h5>No hay eventos en el período seleccionado</h5>
                            <p>Intenta cambiar los filtros o aumentar el rango de días.</p>
                        </div>
                    `);
                    return;
                }

                // Vista de Timeline por Fecha
                let html = `<div class="roadmap-timeline">`;
                
                // Agrupar por fecha
                let grouped = data.grouped_by_date;
                let dates = Object.keys(grouped).sort();
                
                dates.forEach(function(date_str) {
                    let items = grouped[date_str];
                    let date_obj = new Date(date_str);
                    let date_formatted = frappe.datetime.str_to_user(date_str);
                    
                    html += `
                        <div class="timeline-date-group mb-4" style="border-left: 4px solid #007bff; padding-left: 20px; margin-left: 10px;">
                            <h5 class="mb-3" style="color: #007bff; font-weight: bold;">
                                📅 ${date_formatted} 
                                <span class="badge badge-secondary">${items.length} evento${items.length > 1 ? 's' : ''}</span>
                            </h5>
                            <div class="row">
                    `;
                    
                    items.forEach(function(item) {
                        let color_class = getColorClass(item.color);
                        html += `
                            <div class="col-md-6 mb-3">
                                <div class="roadmap-card ${color_class}" style="
                                    border-left: 4px solid ${getColorHex(item.color)};
                                    padding: 15px;
                                    background: white;
                                    border-radius: 5px;
                                    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
                                    transition: transform 0.2s;
                                " onmouseover="this.style.transform='translateY(-2px)'" onmouseout="this.style.transform='translateY(0)'">
                                    <div style="display: flex; align-items: start;">
                                        <span style="font-size: 24px; margin-right: 10px;">${item.icon}</span>
                                        <div style="flex: 1;">
                                            <h6 style="margin: 0 0 5px 0; font-weight: bold;">${item.title}</h6>
                                            <p class="text-muted small mb-2" style="margin: 0;">${item.description}</p>
                                            <div style="display: flex; gap: 10px; flex-wrap: wrap;">
                                                <span class="badge badge-secondary">${item.type}</span>
                                                <span class="badge ${getStatusBadgeClass(item.status)}">${item.status}</span>
                                                ${item.pdv ? `<a href="#" onclick="frappe.set_route('punto_360', {pdv: '${item.pdv}'}); return false;" class="badge badge-info">PDV</a>` : ''}
                                                ${item.employee ? `<a href="#" onclick="frappe.set_route('persona_360', {empleado: '${item.employee}'}); return false;" class="badge badge-primary">Empleado</a>` : ''}
                                            </div>
                                            <div class="mt-2">
                                                <a href="/app/${getDocTypeSlug(item.doctype)}/${item.docname}" class="btn btn-sm btn-link p-0" style="font-size: 12px;">
                                                    Ver Detalle →
                                                </a>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        `;
                    });
                    
                    html += `</div></div>`;
                });
                
                html += `</div>`;
                $container.append(html);
            }
        }
    });
}

function getColorClass(color_name) {
    const classes = {
        "blue": "border-primary",
        "red": "border-danger",
        "orange": "border-warning",
        "purple": "border-info",
        "green": "border-success",
        "gray": "border-secondary"
    };
    return classes[color_name] || "border-secondary";
}

function getColorHex(color_name) {
    const colors = {
        "blue": "#007bff",
        "red": "#dc3545",
        "orange": "#fd7e14",
        "purple": "#6f42c1",
        "green": "#28a745",
        "gray": "#6c757d"
    };
    return colors[color_name] || "#6c757d";
}

function getStatusBadgeClass(status) {
    if (!status) return "badge-secondary";
    const status_lower = status.toLowerCase();
    if (status_lower.includes("abierto") || status_lower.includes("en proceso")) {
        return "badge-warning";
    } else if (status_lower.includes("cerrado")) {
        return "badge-success";
    }
    return "badge-secondary";
}

function getDocTypeSlug(doctype) {
    const slugs = {
        "Novedad SST": "novedad-sst",
        "Caso Disciplinario": "caso-disciplinario",
        "Caso SST": "caso-sst"
    };
    return slugs[doctype] || doctype.toLowerCase().replace(/\s+/g, "-");
}
