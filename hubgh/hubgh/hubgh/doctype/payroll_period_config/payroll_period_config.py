import frappe
from frappe.model.document import Document


class PayrollPeriodConfig(Document):
    def validate(self):
        self.nombre_periodo = str(self.nombre_periodo or "").strip()
        if not self.nombre_periodo:
            frappe.throw("Nombre del período es obligatorio.")

        if self.fecha_corte_inicio and self.fecha_corte_fin:
            if self.fecha_corte_inicio >= self.fecha_corte_fin:
                frappe.throw("Fecha de corte inicio debe ser menor que fecha de corte fin.")

        if self.ano and self.mes:
            if not (1 <= int(self.mes) <= 12):
                frappe.throw("Mes debe estar entre 1 y 12.")

        if self.status not in ("Draft", "Active", "Closed"):
            self.status = "Draft"
