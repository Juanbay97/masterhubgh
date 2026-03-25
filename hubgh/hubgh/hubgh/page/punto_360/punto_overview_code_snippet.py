@frappe.whitelist()
def get_all_puntos_overview():
    # Return a summary list of all PDVs visible to the user
    puntos = frappe.get_all("Punto de Venta", fields=["name", "nombre_pdv", "zona", "planta_autorizada"])
    
    summary_list = []
    for p in puntos:
        # Check permission per doc if needed, but get_all usually respects perm depends on config.
        # Ideally we assume if they can see the doc, they can see the card.
        if not frappe.has_permission("Punto de Venta", "read", p.name):
            continue

        headcount = frappe.db.count("Ficha Empleado", {"pdv": p.name, "estado": "Activo"})
        novedades = frappe.db.count("Novedad SST", {
            "estado": "Abierto",
            "empleado": ["in", [e.name for e in frappe.get_all("Ficha Empleado", filters={"pdv": p.name})]]
        })
        
        summary_list.append({
            "name": p.name,
            "title": p.nombre_pdv,
            "zona": p.zona,
            "headcount": f"{headcount}/{p.planta_autorizada}",
            "novedades": novedades
        })
        
    return summary_list
