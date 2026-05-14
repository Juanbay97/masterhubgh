"""Re-ejecuta la limpieza de catálogos CCF y EPS y repunta registros legacy.

Necesario porque:
  - `normalize_ccf_catalog` y `reseed_siesa_entidades_con_nits` ya corrieron, pero
    quedaron Contratos/Datos Contratacion con códigos legacy (ej. "0102") que
    fueron creados o re-importados después.
  - `ensure_official_eps_catalog` antes usaba `fallback_code=None`, por lo que
    registros EPS legacy NO se repuntaban. Ahora usa `fallback_code="999999999"`
    (SIN EPS) y este patch los re-procesa.
"""

import frappe

from hubgh.hubgh.siesa_reference_matrix import (
	ensure_official_ccf_catalog,
	ensure_official_eps_catalog,
)


def execute():
	if frappe.db.exists("DocType", "Entidad CCF Siesa"):
		ensure_official_ccf_catalog(strict_disable_others=True)
	if frappe.db.exists("DocType", "Entidad EPS Siesa"):
		ensure_official_eps_catalog(strict_disable_others=True)
	frappe.db.commit()
