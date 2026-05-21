# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
bandeja_traslados_pdv.py — Thin controllers para la Bandeja Traslados PDV.

Arquitectura: cada método es un delegador de ~5 líneas hacia traslado_service.
Patrón idéntico a bandeja_casos_disciplinarios.py.
Import path: hubgh.hubgh.page.bandeja_traslados_pdv.bandeja_traslados_pdv
"""

import frappe

from hubgh.hubgh.services import traslado_service


@frappe.whitelist()
def get_traslado_flow_context():
    return traslado_service.get_flow_context(user=frappe.session.user)


@frappe.whitelist()
def get_traslados_tray(filters=None):
    parsed = frappe.parse_json(filters) if filters else {}
    return traslado_service.get_tray(filters=parsed)


@frappe.whitelist()
def create_traslado_action(empleado, pdv_destino, fecha_aplicacion, motivo, justificacion, cargo_destino=None):
    return traslado_service.create_traslado(
        empleado=empleado,
        pdv_destino=pdv_destino,
        fecha_aplicacion=fecha_aplicacion,
        motivo=motivo,
        justificacion=justificacion,
        cargo_destino=cargo_destino,
    )


@frappe.whitelist()
def apply_traslado_action(traslado_name):
    return traslado_service.apply_traslado(traslado_name)


@frappe.whitelist()
def cancel_traslado_action(traslado_name, motivo):
    return traslado_service.cancel_traslado(traslado_name, motivo)


__all__ = [
    "get_traslado_flow_context",
    "get_traslados_tray",
    "create_traslado_action",
    "apply_traslado_action",
    "cancel_traslado_action",
]
