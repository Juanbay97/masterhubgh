# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
Patch idempotente: carga los 6 fixtures iniciales de Causal Terminacion.

Causales:
  renuncia         — Renuncia voluntaria
  abandono_cargo   — Abandono de cargo
  justa_causa      — Terminacion con justa causa (requiere carta + caso disciplinario)
  periodo_prueba   — Terminacion en periodo de prueba (requiere carta)
  mutuo_acuerdo    — Mutuo acuerdo
  otros            — Otros

Pattern igual al de load_initial_motivo_traslado_fixture.
"""

import frappe


CAUSALES = [
    {
        "name": "renuncia",
        "codigo": "renuncia",
        "nombre": "Renuncia voluntaria",
        "requiere_carta_automatica": 0,
        "requiere_caso_disciplinario": 0,
        "requiere_periodo_prueba_check": 0,
        "plantilla_carta_template_name": "",
        "activo": 1,
    },
    {
        "name": "abandono_cargo",
        "codigo": "abandono_cargo",
        "nombre": "Abandono de cargo",
        "requiere_carta_automatica": 0,
        "requiere_caso_disciplinario": 0,
        "requiere_periodo_prueba_check": 0,
        "plantilla_carta_template_name": "",
        "activo": 1,
    },
    {
        "name": "justa_causa",
        "codigo": "justa_causa",
        "nombre": "Terminación con justa causa",
        "requiere_carta_automatica": 1,
        "requiere_caso_disciplinario": 1,
        "requiere_periodo_prueba_check": 0,
        "plantilla_carta_template_name": "carta_terminacion_justa_causa",
        "activo": 1,
    },
    {
        "name": "periodo_prueba",
        "codigo": "periodo_prueba",
        "nombre": "Terminación en periodo de prueba",
        "requiere_carta_automatica": 1,
        "requiere_caso_disciplinario": 0,
        "requiere_periodo_prueba_check": 1,
        "plantilla_carta_template_name": "carta_terminacion_periodo_prueba",
        "activo": 1,
    },
    {
        "name": "mutuo_acuerdo",
        "codigo": "mutuo_acuerdo",
        "nombre": "Mutuo acuerdo",
        "requiere_carta_automatica": 0,
        "requiere_caso_disciplinario": 0,
        "requiere_periodo_prueba_check": 0,
        "plantilla_carta_template_name": "",
        "activo": 1,
    },
    {
        "name": "otros",
        "codigo": "otros",
        "nombre": "Otros",
        "requiere_carta_automatica": 0,
        "requiere_caso_disciplinario": 0,
        "requiere_periodo_prueba_check": 0,
        "plantilla_carta_template_name": "",
        "activo": 1,
    },
]


def execute():
    """Carga las 6 causales iniciales de Terminacion Contrato. Idempotente."""
    for causal in CAUSALES:
        if frappe.db.exists("Causal Terminacion", causal["name"]):
            continue
        try:
            doc_data = {"doctype": "Causal Terminacion"}
            doc_data.update(causal)
            frappe.get_doc(doc_data).insert(ignore_permissions=True)
            frappe.logger("hubgh.patches").info(
                f"load_initial_causal_terminacion_fixture: created '{causal['name']}'"
            )
        except Exception as exc:
            frappe.log_error(
                message=str(exc),
                title=f"load_initial_causal_terminacion_fixture: fallo en {causal['name']}",
            )

    frappe.db.commit()
