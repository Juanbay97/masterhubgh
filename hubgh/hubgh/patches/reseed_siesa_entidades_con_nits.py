"""Reseed catálogos SIESA con los códigos oficiales que SIESA espera.

- EPS / AFP / Cesantías / CCF: code = NIT real (no códigos cortos
  sintéticos viejos como `210101`, `230301`, `001`).
- Banco Siesa: code = código ACH; codigo_bancolombia = código
  Bancolombia interno; codigo_ach + ultimos_dos_digitos completos.

Repunta Link fields existentes (Contrato, Candidato, Datos Contratacion,
Ficha Empleado) hacia los nuevos registros.

Tipo Cotizante Siesa NO se toca (el export aplica `lstrip('0')` para
mandar `1` en vez de `01`).
"""

import frappe

from hubgh.hubgh.siesa_reference_matrix import (
	ensure_banco_reference_catalog,
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
	if frappe.db.exists("DocType", "Banco Siesa"):
		ensure_banco_reference_catalog()
	frappe.db.commit()
