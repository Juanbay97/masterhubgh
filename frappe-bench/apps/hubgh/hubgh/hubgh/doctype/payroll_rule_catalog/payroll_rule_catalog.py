import frappe
from frappe.model.document import Document


class PayrollRuleCatalog(Document):
    def validate(self):
        self.codigo_regla = str(self.codigo_regla or "").strip().upper()
        if not self.codigo_regla:
            frappe.throw("Código de regla es obligatorio.")

        self.nombre_regla = str(self.nombre_regla or "").strip()
        if not self.nombre_regla:
            frappe.throw("Nombre de regla es obligatorio.")

        allowed_types = {
            "home12_fijo",
            "home12_proporcional",
            "auxilio_dominical",
            "tope_descuento",
            "sanitas_premium",
            "gafas_convenio",
            "bonificacion_perdida",
            "prestamo_empresa",
            "libranza",
            "dotacion_pendiente",
            "incapacidad_legal",
            "general",
        }
        if self.tipo_regla not in allowed_types:
            frappe.throw(
                f"Tipo de regla '{self.tipo_regla}' no reconocido. "
                f"Valores: {', '.join(sorted(allowed_types))}."
            )

        if self.parametros:
            try:
                import json as _json
                _json.loads(self.parametros)
            except Exception as exc:
                frappe.throw(f"Parámetros inválidos como JSON: {exc}")

        if self.activa not in (0, 1):
            self.activa = 1
