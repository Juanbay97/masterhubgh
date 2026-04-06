import frappe
from frappe.model.document import Document


class PayrollNovedadType(Document):
    def validate(self):
        self.codigo = str(self.codigo or "").strip().upper()
        if not self.codigo:
            frappe.throw("Código del tipo de novedad es obligatorio.")

        self.novedad_type = str(self.novedad_type or "").strip()
        if not self.novedad_type:
            frappe.throw("Nombre del tipo de novedad es obligatorio.")

        # Normalizar dimensión de sensibilidad
        self.sensitivity = str(self.sensitivity or "operational").strip().lower()
        allowed_sensitivity = {
            "operational",
            "documental",
            "disciplinary",
            "clinical",
            "sst_clinical",
        }
        if self.sensitivity not in allowed_sensitivity:
            frappe.throw(
                f"Sensibilidad '{self.sensitivity}' no soportada. "
                f"Valores válidos: {', '.join(sorted(allowed_sensitivity))}."
            )

        # Normalizar estado
        self.status = str(self.status or "Draft").strip()
        allowed_status = {"Draft", "Active", "Deprecated"}
        if self.status not in allowed_status:
            frappe.throw(
                f"Estado '{self.status}' no válido. Valores: {', '.join(sorted(allowed_status))}."
            )
