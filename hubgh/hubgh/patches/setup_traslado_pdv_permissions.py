"""
Patch idempotente: reaplica los permisos de Traslado PDV y Motivo Traslado.

Razón: el JSON inicial del DocType venía con un array `permissions[]` denso
que dejaba a Jefe_PDV y Empleado con write/create/delete=1 (incorrecto).
La fuente canónica de permisos vive en setup_gh_permissions.setup_traslado_pdv_permissions.
Este patch:

1. Borra todas las DocPerm filas no canónicas de Traslado PDV y Motivo Traslado.
2. Re-aplica los permisos correctos vía setup_traslado_pdv_permissions().

Idempotente: se puede correr múltiples veces sin daño.
"""

import frappe

from hubgh.setup_gh_permissions import setup_traslado_pdv_permissions


def execute():
    # 1. Limpiar DocPerm huérfanas dejando solo System Manager (default).
    for doctype in ("Traslado PDV", "Motivo Traslado"):
        if not frappe.db.exists("DocType", doctype):
            continue
        frappe.db.delete(
            "DocPerm",
            {
                "parent": doctype,
                "role": ("not in", ["System Manager"]),
            },
        )
        frappe.clear_cache(doctype=doctype)

    # 2. Re-aplicar la matriz canónica vía ensure_docperm.
    setup_traslado_pdv_permissions()

    frappe.db.commit()
