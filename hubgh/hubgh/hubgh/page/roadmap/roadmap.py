
import frappe
from frappe import _
from datetime import datetime, timedelta

@frappe.whitelist()
def get_roadmap_data(pdv_filter=None, empleado_filter=None, days_ahead=30):
    """
    Obtiene datos para la vista de roadmap
    
    Args:
        pdv_filter: Filtrar por Punto de Venta (opcional)
        empleado_filter: Filtrar por Empleado (opcional)
        days_ahead: Días hacia adelante para mostrar eventos (default: 30)
    """
    today = datetime.now().date()
    future_date = today + timedelta(days=int(days_ahead))
    
    roadmap_items = []
    
    # Filtros base
    base_filters = {}
    if pdv_filter:
        base_filters["pdv"] = pdv_filter
    
    # 1. NOVEDADES LABORALES (con fechas futuras o activas)
    # Incluir novedades que:
    # - Tienen fecha_fin en el futuro, O
    # - Están activas y fecha_inicio está en el rango, O
    # - Están activas sin fecha_fin
    novedades_filters = {
        "estado": "Abierto",
        "categoria_novedad": "SST",
    }
    
    if empleado_filter:
        novedades_filters["empleado"] = empleado_filter
    elif pdv_filter:
        # Obtener empleados del PDV
        empleados_pdv = [e.name for e in frappe.get_all("Ficha Empleado", 
            filters={"pdv": pdv_filter}, fields=["name"])]
        if empleados_pdv:
            novedades_filters["empleado"] = ["in", empleados_pdv]
        else:
            novedades_filters["empleado"] = None  # No hay empleados
    
    novedades = frappe.get_all("Novedad SST",
        filters=novedades_filters,
        fields=["name", "empleado", "tipo_novedad", "fecha_inicio", "fecha_fin", 
                "descripcion", "estado"]
    )
    
    # Filtrar novedades que están en el rango de fechas
    novedades_filtered = []
    for nov in novedades:
        fecha_referencia = nov.fecha_fin or nov.fecha_inicio
        if fecha_referencia:
            if isinstance(fecha_referencia, str):
                fecha_ref = datetime.strptime(fecha_referencia, "%Y-%m-%d").date()
            else:
                fecha_ref = fecha_referencia
            # Incluir si está en el rango futuro
            if today <= fecha_ref <= future_date:
                novedades_filtered.append(nov)
    
    for nov in novedades_filtered:
        # Obtener información del empleado
        empleado_name = nov.empleado if isinstance(nov.empleado, str) else None
        if not empleado_name and hasattr(nov, 'empleado') and nov.empleado:
            empleado_name = nov.empleado
            
        # Obtener datos del empleado si es un string (nombre del DocType)
        emp_nombres = ""
        emp_apellidos = ""
        emp_pdv = None
        if empleado_name:
            try:
                emp_doc = frappe.get_doc("Ficha Empleado", empleado_name)
                emp_nombres = emp_doc.nombres or ""
                emp_apellidos = emp_doc.apellidos or ""
                emp_pdv = emp_doc.pdv
            except:
                # Si no se puede obtener el doc, intentar con get_value
                emp_nombres = frappe.db.get_value("Ficha Empleado", empleado_name, "nombres") or ""
                emp_apellidos = frappe.db.get_value("Ficha Empleado", empleado_name, "apellidos") or ""
                emp_pdv = frappe.db.get_value("Ficha Empleado", empleado_name, "pdv")
        
        pdv_nombre = frappe.db.get_value("Punto de Venta", emp_pdv, "nombre_pdv") if emp_pdv else ""
        roadmap_items.append({
            "date": nov.fecha_fin or nov.fecha_inicio,
            "title": f"{nov.tipo_novedad} - {emp_nombres} {emp_apellidos}".strip(),
            "description": f"{nov.descripcion or ''} | PDV: {pdv_nombre}",
            "type": "Novedad",
            "doctype": "Novedad SST",
            "docname": nov.name,
            "category": "novedad",
            "icon": "📢",
            "color": get_novedad_color(nov.tipo_novedad),
            "status": nov.estado,
            "employee": empleado_name,
            "pdv": emp_pdv
        })
    
    # 2. CASOS DISCIPLINARIOS ABIERTOS (con próximas fechas importantes)
    disciplinarios_filters = {
        "estado": ["in", ["Abierto", "En Proceso"]]
    }
    
    if empleado_filter:
        disciplinarios_filters["empleado"] = empleado_filter
    elif pdv_filter:
        empleados_pdv = [e.name for e in frappe.get_all("Ficha Empleado",
            filters={"pdv": pdv_filter}, fields=["name"])]
        if empleados_pdv:
            disciplinarios_filters["empleado"] = ["in", empleados_pdv]
        else:
            disciplinarios_filters["empleado"] = None
    
    disciplinarios = frappe.get_all("Caso Disciplinario",
        filters=disciplinarios_filters,
        fields=["name", "empleado", "fecha_incidente", "tipo_falta",
                "descripcion", "estado", "empleado.nombres", "empleado.apellidos",
                "empleado.pdv"]
    )
    
    for disc in disciplinarios:
        # Obtener información del empleado
        empleado_name = disc.empleado if isinstance(disc.empleado, str) else None
        if not empleado_name and hasattr(disc, 'empleado') and disc.empleado:
            empleado_name = disc.empleado
            
        emp_nombres = ""
        emp_apellidos = ""
        emp_pdv = None
        if empleado_name:
            emp_nombres = frappe.db.get_value("Ficha Empleado", empleado_name, "nombres") or ""
            emp_apellidos = frappe.db.get_value("Ficha Empleado", empleado_name, "apellidos") or ""
            emp_pdv = frappe.db.get_value("Ficha Empleado", empleado_name, "pdv")
        
        pdv_nombre = frappe.db.get_value("Punto de Venta", emp_pdv, "nombre_pdv") if emp_pdv else ""
        # Si la fecha es futura o dentro del rango, agregar
        if disc.fecha_incidente:
            if isinstance(disc.fecha_incidente, str):
                fecha_inc = datetime.strptime(disc.fecha_incidente, "%Y-%m-%d").date()
            else:
                fecha_inc = disc.fecha_incidente
        else:
            fecha_inc = today
        if fecha_inc <= future_date:
            roadmap_items.append({
                "date": disc.fecha_incidente,
                "title": f"Falta {disc.tipo_falta} - {emp_nombres} {emp_apellidos}".strip(),
                "description": f"{disc.descripcion or ''} | PDV: {pdv_nombre}",
                "type": "Caso Disciplinario",
                "doctype": "Caso Disciplinario",
                "docname": disc.name,
                "category": "disciplinario",
                "icon": "⚠️",
                "color": "red" if disc.tipo_falta in ["Grave", "Gravísima"] else "orange",
                "status": disc.estado,
                "employee": empleado_name,
                "pdv": emp_pdv
            })
    
    # Ordenar items por fecha
    roadmap_items.sort(key=lambda x: x["date"] or "9999-12-31")
    
    # Agrupar por fecha para la vista
    grouped_by_date = {}
    for item in roadmap_items:
        date_str = str(item["date"]) if item["date"] else "Sin fecha"
        if date_str not in grouped_by_date:
            grouped_by_date[date_str] = []
        grouped_by_date[date_str].append(item)
    
    return {
        "items": roadmap_items,
        "grouped_by_date": grouped_by_date,
        "total_items": len(roadmap_items),
        "date_range": {
            "start": today.strftime("%Y-%m-%d"),
            "end": future_date.strftime("%Y-%m-%d")
        }
    }

def get_novedad_color(tipo_novedad):
    """Retorna el color según el tipo de novedad"""
    colors = {
        "Vacaciones": "green",
        "Incapacidad": "orange",
        "Incapacidad por enfermedad general": "orange",
        "Licencia": "blue",
        "Accidente": "purple",
        "Recomendación Médica": "teal",
        "Aforado": "indigo",
        "Abandono": "red",
        "Renuncia": "red"
    }
    return colors.get(tipo_novedad, "gray")
