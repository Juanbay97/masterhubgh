import csv

import frappe
from frappe.utils import getdate


def import_real_data(puntos_path: str, empleados_path: str) -> None:
    _reset_data()
    _import_puntos(puntos_path)
    _import_empleados(empleados_path)
    frappe.db.commit()


def _reset_data() -> None:
    frappe.db.sql("DELETE FROM `tabNovedad SST`")
    frappe.db.sql("DELETE FROM `tabFicha Empleado`")
    frappe.db.sql("DELETE FROM `tabPunto de Venta`")


def _import_puntos(puntos_path: str) -> None:
    allowed_zonas = {"Norte", "Sur", "Oriente", "Occidente", "Centro"}
    with open(puntos_path, "r", encoding="latin-1", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        for index, row in enumerate(reader, start=1):
            nombre = (row.get("nombre_pdv") or "").strip()
            zona_raw = (row.get("zona") or "").strip()
            zona = zona_raw if zona_raw in allowed_zonas else "Centro"
            planta = (row.get("planta_autorizada") or "0").strip()

            if not nombre:
                continue

            doc = frappe.new_doc("Punto de Venta")
            doc.codigo = f"PDV-{index:04d}"
            doc.nombre_pdv = nombre
            doc.zona = zona
            doc.planta_autorizada = int(planta) if planta else 0
            doc.insert(ignore_permissions=True)


def _import_empleados(empleados_path: str) -> None:
    pdv_lookup = _build_pdv_lookup()
    with open(empleados_path, "r", encoding="latin-1", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        for row in reader:
            cedula = (row.get("cedula") or "").strip()
            if not cedula:
                continue

            pdv_nombre = (row.get("pdv (nombre)") or "").strip()
            pdv_name = _find_pdv_name(pdv_nombre, pdv_lookup)
            if not pdv_name:
                continue

            doc = frappe.new_doc("Ficha Empleado")
            doc.nombres = (row.get("nombres") or "").strip()
            doc.apellidos = (row.get("apellidos") or "").strip()
            doc.cedula = cedula
            doc.cargo = (row.get("cargo") or "").strip()
            doc.email = (row.get("email") or "").strip()
            doc.fecha_ingreso = getdate((row.get("fecha_ingreso") or "").strip()) if row.get("fecha_ingreso") else None
            if pdv_name:
                doc.pdv = pdv_name
            doc.insert(ignore_permissions=True)


def _build_pdv_lookup() -> dict:
    lookup = {}
    for row in frappe.get_all("Punto de Venta", fields=["name", "nombre_pdv"]):
        key = _normalize_pdv_name(row.get("nombre_pdv"))
        if key:
            lookup[key] = row.get("name")
    return lookup


def _normalize_pdv_name(nombre: str) -> str:
    return (nombre or "").strip().upper().replace("  ", " ")


def _find_pdv_name(pdv_nombre: str, lookup: dict) -> str | None:
    if not pdv_nombre:
        return None

    normalized = _normalize_pdv_name(pdv_nombre)
    if normalized in lookup:
        return lookup[normalized]

    if normalized.startswith("DOMICILIOS "):
        parts = normalized.split(" ")
        if len(parts) >= 2 and parts[1].isdigit():
            padded = f"DOMICILIOS {int(parts[1]):02d}"
            if padded in lookup:
                return lookup[padded]

    for key, value in lookup.items():
        if key in normalized or normalized in key:
            return value

    return None
