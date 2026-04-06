import frappe
from frappe.model.document import Document


class PayrollSourceCatalog(Document):
    def validate(self):
        self.nombre_fuente = str(self.nombre_fuente or "").strip()
        if not self.nombre_fuente:
            frappe.throw("Nombre de la fuente es obligatorio.")

        self.tipo_fuente = str(self.tipo_fuente or "").strip()
        if not self.tipo_fuente:
            frappe.throw("Tipo de fuente es obligatorio.")

        allowed_types = {
            "clonk",
            "payflow",
            "fincomercio",
            "fondo_empleados",
            "libranzas",
            "siesa",
            "gh_novedad",
            "novedad_laboral",
            "bienestar",
            "sst",
            "rrll",
            "seleccion",
            "manual",
        }
        if self.tipo_fuente not in allowed_types:
            frappe.throw(
                f"Tipo de fuente '{self.tipo_fuente}' no reconocido. "
                f"Valores válidos: {', '.join(sorted(allowed_types))}."
            )

        # Validar JSON de mapeo de columnas si existe
        if self.mapeo_columnas:
            try:
                import json as _json

                _json.loads(self.mapeo_columnas)
            except Exception as exc:
                frappe.throw(f"Mapeo de columnas inválido como JSON: {exc}")

        self.status = str(self.status or "Active").strip()
        if self.status not in {"Draft", "Active", "Deprecated"}:
            frappe.throw("Estado debe ser Draft, Active o Deprecated.")
