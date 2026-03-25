import frappe

from hubgh.hubgh.contratacion_service import siesa_candidates
from hubgh.hubgh.siesa_export import exportar_conector_contratos, exportar_conector_empleados


__all__ = [
	"siesa_candidates",
	"exportar_conector_empleados",
	"exportar_conector_contratos",
]


@frappe.whitelist()
def get_datos_contratacion_for_candidate(candidate):
	"""Get Datos Contratacion linked to a candidate."""
	datos_name = frappe.db.get_value("Datos Contratacion", {"candidato": candidate}, "name")
	return datos_name

