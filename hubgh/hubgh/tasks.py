import frappe
from frappe.utils import getdate, nowdate

from hubgh.hubgh.bienestar_automation import (
	generate_ingreso_followups_for_active_employees,
	mark_bienestar_followups_overdue,
)
from hubgh.hubgh.disciplinary_case_service import process_closed_disciplinary_cases
from hubgh.hubgh.employee_retirement_service import process_pending_employee_retirements


def revertir_novedades_expiradas():
    today = getdate(nowdate())

    novedades = frappe.get_all(
        "Novedad SST",
        filters={
            "impacta_estado": 1,
            "estado": ["in", ["Abierta", "Abierto", "En seguimiento"]],
            "fecha_fin": ["<", today],
        },
        fields=["name", "empleado", "estado_destino"],
    )

    for nov in novedades:
        if not nov.empleado:
            continue

        if nov.estado_destino == "Retirado":
            continue

        frappe.db.set_value("Ficha Empleado", nov.empleado, "estado", "Activo")


def dispatch_sst_alertas_diarias():
    today = getdate(nowdate())
    alertas = frappe.get_all(
        "SST Alerta",
        filters={
            "estado": ["in", ["Pendiente", "Reprogramada"]],
            "fecha_programada": ["<=", today],
        },
        fields=["name", "asignado_a", "mensaje", "fecha_programada", "referencia_todo"],
    )

    for alerta in alertas:
        if alerta.referencia_todo and frappe.db.exists("ToDo", alerta.referencia_todo):
            frappe.db.set_value("SST Alerta", alerta.name, "estado", "Enviada")
            frappe.db.set_value("SST Alerta", alerta.name, "ultima_notificacion", today)
            continue

        if not alerta.asignado_a:
            continue

        todo = frappe.get_doc(
            {
                "doctype": "ToDo",
                "allocated_to": alerta.asignado_a,
                "description": alerta.mensaje or f"Alerta SST pendiente ({alerta.name})",
                "date": alerta.fecha_programada,
                "reference_type": "SST Alerta",
                "reference_name": alerta.name,
            }
        )
        todo.insert(ignore_permissions=True)
        frappe.db.set_value(
            "SST Alerta",
            alerta.name,
            {
                "referencia_todo": todo.name,
                "estado": "Enviada",
                "ultima_notificacion": today,
            },
        )


def bienestar_generar_seguimientos_ingreso_diarios():
	"""Workstream 2: deterministic generation of 5/10/30/45 follow-ups."""
	return generate_ingreso_followups_for_active_employees()


def bienestar_marcar_vencidos_diario():
    """Workstream 2: mark overdue follow-ups without touching closed/cancelled ones."""
    return mark_bienestar_followups_overdue()


def procesar_retiros_empleados_programados():
	return process_pending_employee_retirements()


def procesar_casos_disciplinarios_rrll():
	return process_closed_disciplinary_cases()
