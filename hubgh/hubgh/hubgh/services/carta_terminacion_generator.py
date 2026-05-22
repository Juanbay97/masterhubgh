# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
carta_terminacion_generator.py — Generación de carta de terminación en PDF.

ADR-2 (design §2): Carta generada via Email Template (editable por RRLL sin redeploy).
ADR-3: Cita Examen Egreso es DocType separado — no relación con este módulo.

Flujo generar_carta:
1. Obtener Causal Terminacion → verificar requiere_carta_automatica.
2. Si no requiere → retornar None.
3. Obtener Email Template por plantilla_carta_template_name.
4. Construir context con datos del empleado/TC.
5. Renderizar Jinja (template.response) → HTML string.
6. Convertir a PDF bytes via frappe.utils.pdf.get_pdf.
7. Crear File DocType adjunto a la TC.
8. db_set carta_terminacion = file_url en el doc.
9. Retornar file_url.

Import path: hubgh.hubgh.services.carta_terminacion_generator
"""

from __future__ import annotations

import frappe
from frappe.utils.jinja import render_template
from frappe.utils.pdf import get_pdf


# ---------------------------------------------------------------------------
# Pública
# ---------------------------------------------------------------------------

def generar_carta(terminacion_doc) -> str | None:
    """
    Genera la carta de terminación en PDF y la adjunta al documento TC.

    Args:
        terminacion_doc: Instancia del DocType 'Terminacion Contrato'.

    Returns:
        URL del archivo PDF adjunto, o None si la causal no requiere carta.

    Behavior on failure:
        Si el template no existe o falla el render/PDF, loguea via frappe.log_error
        y retorna None. La TC NO se aborta.
    """
    try:
        causal = frappe.get_doc("Causal Terminacion", terminacion_doc.causal)
    except Exception as exc:
        frappe.log_error(
            message=str(exc),
            title=f"generar_carta: Causal no encontrada para TC {terminacion_doc.name}",
        )
        return None

    if not causal.requiere_carta_automatica:
        return None

    try:
        template = frappe.get_doc("Email Template", causal.plantilla_carta_template_name)
    except Exception as exc:
        frappe.log_error(
            message=str(exc),
            title=f"generar_carta: Template no encontrado '{causal.plantilla_carta_template_name}' para TC {terminacion_doc.name}",
        )
        return None

    try:
        context = _build_carta_context(terminacion_doc, causal)
        html = render_template(template.response or "", context)
        pdf_bytes = get_pdf(html)

        file_doc = frappe.get_doc({
            "doctype": "File",
            "file_name": f"carta_terminacion_{terminacion_doc.name}.pdf",
            "attached_to_doctype": "Terminacion Contrato",
            "attached_to_name": terminacion_doc.name,
            "content": pdf_bytes,
            "is_private": 1,
        })
        file_doc.insert(ignore_permissions=True)

        terminacion_doc.db_set("carta_terminacion", file_doc.file_url)
        return file_doc.file_url

    except Exception as exc:
        frappe.log_error(
            message=str(exc),
            title=f"generar_carta: Error al generar PDF para TC {terminacion_doc.name}",
        )
        return None


# ---------------------------------------------------------------------------
# Privados
# ---------------------------------------------------------------------------

def _build_carta_context(terminacion_doc, causal) -> dict:
    """
    Construye el contexto Jinja para renderizar la carta.

    Context vars (per design §10):
        empleado, cargo_al_terminar, fecha_terminacion_efectiva,
        causal_descripcion, justificacion, fecha_ultimo_dia, base_legal
    """
    emp_fields = frappe.db.get_value(
        "Ficha Empleado",
        terminacion_doc.empleado,
        ["nombres", "apellidos", "cedula", "email"],
        as_dict=True,
    ) or {}

    return {
        "empleado": terminacion_doc.empleado,
        "empleado_nombre": f"{emp_fields.get('nombres', '')} {emp_fields.get('apellidos', '')}".strip(),
        "empleado_cedula": emp_fields.get("cedula", ""),
        "cargo_al_terminar": getattr(terminacion_doc, "cargo_al_terminar", ""),
        "fecha_terminacion_efectiva": str(getattr(terminacion_doc, "fecha_terminacion_efectiva", "") or ""),
        "fecha_ultimo_dia": str(getattr(terminacion_doc, "fecha_ultimo_dia", "") or ""),
        "causal_descripcion": getattr(causal, "nombre", causal.plantilla_carta_template_name or ""),
        "justificacion": getattr(terminacion_doc, "justificacion", ""),
        "base_legal": getattr(causal, "base_legal", ""),
        "tc_name": terminacion_doc.name,
    }
