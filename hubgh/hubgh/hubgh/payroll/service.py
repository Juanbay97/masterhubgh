"""Orquestador de un Payroll Run (Fase A skeleton).

Las funciones aquí cierran el contrato público que el `payroll_workspace` y
los hooks de los DocTypes consumen. La implementación real de detect /
parse / compute / export se va llenando en Fases B–D.
"""

from __future__ import annotations

from typing import Any

import frappe
from frappe import _

from hubgh.hubgh.payroll import catalogs


def create_run(period_year: int, period_month: int) -> str:
	"""Crea un Payroll Run en estado draft. Devuelve el name."""
	if period_year < 2020 or period_year > 2099:
		frappe.throw(_("Año fuera de rango razonable."))
	if period_month < 1 or period_month > 12:
		frappe.throw(_("Mes fuera de rango (1-12)."))
	doc = frappe.get_doc(
		{
			"doctype": "Payroll Run",
			"period_year": period_year,
			"period_month": period_month,
			"status": "draft",
			"jornada_filter": "all",
		}
	)
	doc.insert(ignore_permissions=False)
	return doc.name


def attach_file(run_name: str, file_url: str, file_name: str | None = None) -> str:
	"""Crea un Payroll Run File asociado al run. Devuelve el name del file row.

	La detección de fuente y periodo se ejecuta de forma diferida en
	`process_run`, no aquí.
	"""
	if not frappe.db.exists("Payroll Run", run_name):
		frappe.throw(_("Payroll Run no existe: {0}").format(run_name))
	doc = frappe.get_doc(
		{
			"doctype": "Payroll Run File",
			"run": run_name,
			"file_url": file_url,
			"file_name": file_name or file_url.rsplit("/", 1)[-1],
			"detected_source": "unknown",
			"parse_status": "pending",
		}
	)
	doc.insert(ignore_permissions=False)
	return doc.name


def process_run(run_name: str) -> dict[str, Any]:
	"""Corre el pipeline completo del run: detect → parse → enrich → compute.

	Fase A devuelve un payload vacío. La lógica real entra en Fase B+.
	"""
	if not frappe.db.exists("Payroll Run", run_name):
		frappe.throw(_("Payroll Run no existe: {0}").format(run_name))
	return {
		"run": run_name,
		"status": "not_implemented",
		"message": "El pipeline de procesamiento se entrega en la Fase B.",
	}


def export_run(run_name: str) -> str:
	"""Genera el Excel single-sheet del run y lo deja attached al doc.

	Fase A devuelve un placeholder. La generación real entra en Fase D.
	"""
	if not frappe.db.exists("Payroll Run", run_name):
		frappe.throw(_("Payroll Run no existe: {0}").format(run_name))
	frappe.throw(_("La generación de prenómina entra en la Fase D del rewrite."))


def get_global_param(key: str) -> float:
	"""Retorna el valor de un parámetro global (DocType Single + defaults)."""
	if frappe.db.exists("DocType", "Payroll Parametros Globales"):
		doc = frappe.get_single("Payroll Parametros Globales")
		value = doc.get(key)
		if value is not None:
			return float(value)
	return float(catalogs.PARAMETROS_GLOBALES_DEFAULTS.get(key, 0.0))
