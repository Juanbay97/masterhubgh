import frappe

from hubgh.hubgh.contratacion_service import get_or_create_datos_contratacion
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
	if not candidate:
		return None
	datos = get_or_create_datos_contratacion(candidate)
	return datos.name if datos else None

