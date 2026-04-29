"""Orquestador de un Payroll Run.

Funciones públicas (whitelistadas vía hooks de los DocTypes y vía
endpoints del workspace en Fase E):

  create_run(year, month) → str (run_name)
  attach_file(run_name, file_url, file_name?) → str (run_file_name)
  process_run(run_name) → dict
  export_run(run_name) → str (file_url del Excel)
  get_global_param(key) → float
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import frappe
from frappe import _
from frappe.utils import now_datetime

from hubgh.hubgh.payroll import catalogs, compute
from hubgh.hubgh.payroll.adapters import _detect, clonk, manual
from hubgh.hubgh.payroll.enrichment import build_runtime_context, compute_period_window, enrich
from hubgh.hubgh.payroll.export import build_single_sheet


SOURCE_PARSERS = {
	"clonk": clonk,
	"manual_internal": manual,
}


# ──────────────────────────────────────────────────────────────────────
# CRUD del Run
# ──────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def create_run(period_year: int, period_month: int) -> str:
	year = int(period_year)
	month = int(period_month)
	if year < 2020 or year > 2099:
		frappe.throw(_("Año fuera de rango razonable."))
	if month < 1 or month > 12:
		frappe.throw(_("Mes fuera de rango (1-12)."))
	doc = frappe.get_doc(
		{
			"doctype": "Payroll Run",
			"period_year": year,
			"period_month": month,
			"status": "draft",
			"jornada_filter": "all",
		}
	)
	doc.insert(ignore_permissions=False)
	return doc.name


@frappe.whitelist()
def attach_file(run_name: str, file_url: str, file_name: str | None = None) -> str:
	if not frappe.db.exists("Payroll Run", run_name):
		frappe.throw(_("Payroll Run no existe: {0}").format(run_name))
	doc = frappe.get_doc(
		{
			"doctype": "Payroll Run File",
			"run": run_name,
			"file_url": file_url,
			"file_name": file_name or (file_url.rsplit("/", 1)[-1] if file_url else ""),
			"detected_source": "unknown",
			"parse_status": "pending",
		}
	)
	doc.insert(ignore_permissions=False)
	# Detección barata desde la metadata del archivo.
	try:
		meta = _detect.file_meta_from_path(_resolve_local_path(file_url))
		doc.detected_source = _detect.detect_source(meta)
		doc.save(ignore_permissions=False)
	except Exception as exc:
		# No bloquear el upload por la detección; queda en "unknown".
		frappe.log_error(f"Detection failed for {file_url}: {exc}", "PayrollRunFile.detection")
	return doc.name


# ──────────────────────────────────────────────────────────────────────
# process_run: parse + enrich + compute + persist Payroll Novedad
# ──────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def process_run(run_name: str) -> dict[str, Any]:
	run = frappe.get_doc("Payroll Run", run_name)
	run.status = "ingesting"
	run.save(ignore_permissions=False)

	ctx = build_runtime_context()
	files = frappe.get_all(
		"Payroll Run File",
		filters={"run": run_name},
		fields=["name", "file_url", "detected_source", "parse_status"],
	)

	# Borra novedades previas del run (idempotente).
	frappe.db.delete("Payroll Novedad", {"run": run_name})

	totals: dict[str, int] = {"files": 0, "novedades": 0, "errors": 0, "skipped": 0}
	per_source: dict[str, int] = {}

	for f in files:
		source = (f.get("detected_source") or "unknown").strip()
		parser = SOURCE_PARSERS.get(source)
		if parser is None:
			_mark_file_status(f["name"], "error", {"error": f"Sin parser para fuente '{source}'."})
			totals["errors"] += 1
			continue

		try:
			workbook = clonk.open_workbook(_resolve_local_path(f["file_url"]))
			canonicas = list(parser.parse(workbook))
			period = parser.detect_period(workbook)
		except Exception as exc:  # noqa: BLE001
			_mark_file_status(f["name"], "error", {"error": str(exc)})
			totals["errors"] += 1
			continue

		# Periodo según jornada del Run lógico. Cada novedad luego usa la
		# ventana correcta cuando entre al pipeline (TC vs TP).
		period_start_tc, period_end_tc = compute_period_window(
			run.period_year, run.period_month, "Tiempo Completo"
		)
		period_start_tp, period_end_tp = compute_period_window(
			run.period_year, run.period_month, "Tiempo Parcial"
		)

		count_file = 0
		for canonica in canonicas:
			# Probar primero ventana TC; si el contrato no calza, probar TP.
			enriched = enrich(canonica, period_start_tc, period_end_tc, ctx)
			if enriched.calc_status == "error" and enriched.empleado:
				retry = enrich(canonica, period_start_tp, period_end_tp, ctx)
				if retry.calc_status != "error":
					enriched = retry
			# Cómputo
			compute.compute_novedad(enriched, ctx.params)
			# Persistir
			_persist_novedad(run_name, f["name"], enriched)
			count_file += 1
			if enriched.calc_status == "error":
				totals["errors"] += 1
			elif enriched.calc_status == "skipped":
				totals["skipped"] += 1

		_mark_file_status(
			f["name"],
			"ok",
			{
				"detected_period": list(period) if period else None,
				"count": count_file,
			},
		)
		totals["files"] += 1
		totals["novedades"] += count_file
		per_source[source] = per_source.get(source, 0) + count_file

	run.status = "parsed" if totals["files"] > 0 else "failed"
	run.summary_json = json.dumps({"totals": totals, "per_source": per_source}, ensure_ascii=False)
	run.save(ignore_permissions=False)
	return {"run": run_name, "totals": totals, "per_source": per_source}


# ──────────────────────────────────────────────────────────────────────
# export_run: genera el Excel single-sheet
# ──────────────────────────────────────────────────────────────────────

@frappe.whitelist()
def export_run(run_name: str) -> str:
	run = frappe.get_doc("Payroll Run", run_name)
	if run.status not in {"parsed", "reviewing", "exported"}:
		frappe.throw(_("El Run debe estar parseado/en revisión para exportar (estado actual: {0})").format(run.status))

	ctx = build_runtime_context()
	novedades_docs = frappe.get_all(
		"Payroll Novedad",
		filters={"run": run_name},
		fields=[
			"name", "documento_identidad", "empleado", "contrato",
			"tipo_jornada_snapshot", "tipo_novedad", "jornada_aplicable",
			"unidad", "valor", "cantidad", "fecha_desde", "fecha_hasta",
			"calc_status", "computed_amount", "computed_quantity",
			"raw_payload",
		],
		limit_page_length=0,
	)

	# Convertir a una shape compatible con build_single_sheet.
	novs = [_NovedadView(d, _employee_meta_cache=ctx) for d in novedades_docs]
	period_label = f"{run.period_year}-{int(run.period_month):02d}"
	xlsx_bytes = build_single_sheet(
		novs,
		ctx.params,
		employees_meta=_load_employees_meta(novedades_docs),
		period_label=period_label,
	)

	# Persistir como File de Frappe y attach al Run.
	file_doc = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": f"prenomina_{period_label}_{run.name}.xlsx",
			"is_private": 1,
			"content": xlsx_bytes,
			"attached_to_doctype": "Payroll Run",
			"attached_to_name": run.name,
		}
	).insert(ignore_permissions=False)

	run.export_file = file_doc.file_url
	run.status = "exported"
	run.closed_at = now_datetime()
	run.save(ignore_permissions=False)
	return file_doc.file_url


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

def get_global_param(key: str) -> float:
	if frappe.db.exists("DocType", "Payroll Parametros Globales"):
		try:
			doc = frappe.get_single("Payroll Parametros Globales")
			value = doc.get(key)
			if value is not None:
				return float(value)
		except Exception:
			pass
	return float(catalogs.PARAMETROS_GLOBALES_DEFAULTS.get(key, 0.0))


def _resolve_local_path(file_url: str) -> str:
	if not file_url:
		raise ValueError("file_url vacío")
	from frappe.utils.file_manager import get_file_path  # type: ignore

	return get_file_path(file_url)


def _mark_file_status(file_name: str, status: str, log: dict | None = None) -> None:
	updates = {"parse_status": status, "parsed_at": now_datetime()}
	if log is not None:
		updates["parse_log"] = json.dumps(log, ensure_ascii=False)
	frappe.db.set_value("Payroll Run File", file_name, updates, update_modified=False)


def _persist_novedad(run_name: str, source_file_name: str, enriched) -> None:
	doc = frappe.get_doc(
		{
			"doctype": "Payroll Novedad",
			"run": run_name,
			"source_file": source_file_name,
			"empleado": enriched.empleado,
			"documento_identidad": enriched.documento_identidad,
			"contrato": enriched.contrato,
			"tipo_jornada_snapshot": enriched.tipo_jornada_snapshot,
			"tipo_novedad": enriched.tipo_novedad,
			"jornada_aplicable": enriched.jornada_aplicable,
			"unidad": enriched.unidad,
			"valor": enriched.valor,
			"cantidad": enriched.cantidad,
			"fecha_desde": enriched.fecha_desde,
			"fecha_hasta": enriched.fecha_hasta,
			"calc_status": enriched.calc_status,
			"computed_amount": enriched.computed_amount,
			"computed_quantity": enriched.computed_quantity,
			"calc_notes": enriched.calc_notes,
			"raw_payload": json.dumps(enriched.raw_payload, ensure_ascii=False, default=str),
		}
	)
	doc.insert(ignore_permissions=True)


def _load_employees_meta(novedades_docs: list[dict]) -> dict[str, dict]:
	"""Trae nombres/apellidos/cedula de los empleados referenciados por
	las novedades para que el export muestre datos legibles.
	"""
	emp_names = {d.get("empleado") for d in novedades_docs if d.get("empleado")}
	if not emp_names:
		return {}
	rows = frappe.get_all(
		"Ficha Empleado",
		filters={"name": ["in", list(emp_names)]},
		fields=["name", "nombres", "apellidos", "cedula"],
		limit_page_length=0,
	)
	return {r["name"]: r for r in rows}


class _NovedadView:
	"""Adapta los dicts de `frappe.get_all` al shape esperado por el export.

	El export usa los atributos de `EnrichedNovedad`. Acá replicamos el
	contrato sin acoplar el módulo export a Frappe.
	"""

	def __init__(self, doc_dict: dict, _employee_meta_cache=None):
		self.documento_identidad = doc_dict.get("documento_identidad") or ""
		self.empleado = doc_dict.get("empleado")
		self.contrato = doc_dict.get("contrato")
		self.tipo_jornada_snapshot = doc_dict.get("tipo_jornada_snapshot") or ""
		self.tipo_novedad = doc_dict.get("tipo_novedad") or ""
		self.jornada_aplicable = doc_dict.get("jornada_aplicable") or ""
		self.unidad = doc_dict.get("unidad") or ""
		self.valor = doc_dict.get("valor")
		self.cantidad = doc_dict.get("cantidad")
		self.fecha_desde = doc_dict.get("fecha_desde")
		self.fecha_hasta = doc_dict.get("fecha_hasta")
		self.calc_status = doc_dict.get("calc_status") or ""
		self.computed_amount = doc_dict.get("computed_amount") or 0.0
		self.computed_quantity = doc_dict.get("computed_quantity") or 0.0
		self.salario_mensual = 0.0  # no se persiste; el export usa total_devengado
		try:
			self.raw_payload = json.loads(doc_dict.get("raw_payload") or "{}")
		except Exception:
			self.raw_payload = {}
