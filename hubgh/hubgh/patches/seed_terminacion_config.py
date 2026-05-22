# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
Patch idempotente: seed de Configuracion Terminacion (Single).

Crea o actualiza el registro Single con 7 areas de suscriptores:
- sistemas       (activo=1, role placeholder: System Manager)
- rrll_dotacion  (activo=1, role placeholder: HR Labor Relations)
- operacion      (activo=1, role placeholder: HR Labor Relations)
- sst            (activo=1, role placeholder: HR SST)
- compensacion   (activo=1, role placeholder: HR Labor Relations)
- jefe_pdv       (activo=1, role placeholder: Jefe_PDV — resolucion dinamica en runtime)
- nomina         (activo=0, fuera del MVP segun plan padre §9)

Los roles aqui son placeholders. El equipo ajusta los destinatarios reales post-deploy
directamente en la pantalla de Configuracion Terminacion.

Idempotente: si el Single ya existe con las areas correctas, no crea duplicados.
"""

import frappe


# Definicion de las 7 areas seed
SEED_AREAS = [
    {
        "area": "sistemas",
        "role": "System Manager",  # placeholder — ajustar a GH-IT post deploy
        "user": None,
        "email_fijo": None,
        "activo": 1,
    },
    {
        "area": "rrll_dotacion",
        "role": "HR Labor Relations",  # placeholder
        "user": None,
        "email_fijo": None,
        "activo": 1,
    },
    {
        "area": "operacion",
        "role": "HR Labor Relations",  # placeholder
        "user": None,
        "email_fijo": None,
        "activo": 1,
    },
    {
        "area": "sst",
        "role": "HR Labor Relations",  # placeholder — ajustar a HR SST post deploy si existe
        "user": None,
        "email_fijo": None,
        "activo": 1,
    },
    {
        "area": "compensacion",
        "role": "HR Labor Relations",  # placeholder
        "user": None,
        "email_fijo": None,
        "activo": 1,
    },
    {
        "area": "jefe_pdv",
        "role": "Jefe_PDV",  # resolucion dinamica en runtime via resolve_jefe_pdv
        "user": None,
        "email_fijo": None,
        "activo": 1,
    },
    {
        "area": "nomina",
        "role": "HR Labor Relations",  # placeholder, fuera del MVP
        "user": None,
        "email_fijo": None,
        "activo": 0,  # inactivo — no participa en MVP
    },
]


def execute():
    """Seed idempotente del Single Configuracion Terminacion."""
    doc = frappe.get_single("Configuracion Terminacion")

    # Determinar que areas ya existen para no duplicar
    areas_existentes = {row.area for row in (doc.suscriptores_por_area or [])}

    changed = False
    for seed in SEED_AREAS:
        if seed["area"] in areas_existentes:
            # Area ya existe — no duplicar
            continue

        row_data = {
            "doctype": "Terminacion Suscriptor Area",
            "area": seed["area"],
            "activo": seed["activo"],
        }
        if seed.get("role"):
            row_data["role"] = seed["role"]
        if seed.get("user"):
            row_data["user"] = seed["user"]
        if seed.get("email_fijo"):
            row_data["email_fijo"] = seed["email_fijo"]

        doc.append("suscriptores_por_area", row_data)
        changed = True

    if changed:
        doc.save(ignore_permissions=True)
        frappe.logger("hubgh.patches").info(
            f"seed_terminacion_config: agregadas {sum(1 for s in SEED_AREAS if s['area'] not in areas_existentes)} areas"
        )
    else:
        frappe.logger("hubgh.patches").info("seed_terminacion_config: nada que agregar (ya seed)")

    frappe.db.commit()
