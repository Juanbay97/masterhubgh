"""Renombra filas legacy de los catálogos SIESA (EPS, CCF, AFP, Cesantías) a NIT oficial.

Patch v3 sobre catálogos. Necesario porque `_upsert_reference_row` previamente
no podía cambiar `code` en doctypes con `autoname=field:code` — el save no
renombra. Como resultado quedaron filas como `EPS_SURA`, `ALIANSALUD_EPS`,
`COMPENSAR_EPS`, `FAMISANAR_EPS` con enabled=1, mientras los NITs oficiales
(800088702, 830113831, 860066942, 830003564) nunca llegaron a crearse.

Con la nueva lógica en `_upsert_reference_row` (usa `frappe.rename_doc` cuando
detecta autoname=field:code), correr `ensure_official_*_catalog` repuntará
correctamente.
"""

import frappe

from hubgh.hubgh.siesa_reference_matrix import (
	ensure_official_afp_catalog,
	ensure_official_ccf_catalog,
	ensure_official_cesantias_catalog,
	ensure_official_eps_catalog,
)


def execute():
	if frappe.db.exists("DocType", "Entidad EPS Siesa"):
		ensure_official_eps_catalog(strict_disable_others=True)
	if frappe.db.exists("DocType", "Entidad AFP Siesa"):
		ensure_official_afp_catalog(strict_disable_others=True)
	if frappe.db.exists("DocType", "Entidad Cesantias Siesa"):
		ensure_official_cesantias_catalog(strict_disable_others=True)
	if frappe.db.exists("DocType", "Entidad CCF Siesa"):
		ensure_official_ccf_catalog(strict_disable_others=True)
	frappe.db.commit()
