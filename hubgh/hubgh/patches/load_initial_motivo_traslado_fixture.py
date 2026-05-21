# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
Patch idempotente: carga registros iniciales de Motivo Traslado desde el fixture JSON.

Ejecuta post_model_sync. Itera el fixture y crea cada registro si no existe.
Un fallo en un registro individual se loguea y no aborta el resto.
"""

import json
import os
import frappe


def execute():
    fixture_path = os.path.join(
        os.path.dirname(__file__),
        "..",
        "hubgh",
        "fixtures",
        "motivo_traslado.json",
    )
    fixture_path = os.path.normpath(fixture_path)

    if not os.path.exists(fixture_path):
        frappe.log_error(
            message=f"Fixture no encontrado: {fixture_path}",
            title="load_initial_motivo_traslado_fixture: fixture missing",
        )
        return

    with open(fixture_path, encoding="utf-8") as f:
        registros = json.load(f)

    for registro in registros:
        name = registro.get("name") or registro.get("codigo")
        if not name:
            continue
        try:
            if frappe.db.exists("Motivo Traslado", name):
                continue
            doc = frappe.get_doc({
                "doctype": "Motivo Traslado",
                "name": name,
                "codigo": registro.get("codigo", name),
                "label": registro.get("label", name),
                "requiere_cambio_cargo": registro.get("requiere_cambio_cargo", 0),
                "activo": registro.get("activo", 1),
                "descripcion": registro.get("descripcion", ""),
            })
            doc.insert(ignore_permissions=True)
        except Exception as exc:
            frappe.log_error(
                message=str(exc),
                title=f"load_initial_motivo_traslado_fixture: fallo en {name}",
            )

    frappe.db.commit()
