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
from hubgh.hubgh.payroll.adapters import (
	_detect,
	clonk,
	fincomercio,
	fongiga,
	libranza_compensar,
	libranza_davivienda,
	manual,
	payflow,
)
from hubgh.hubgh.payroll.enrichment import build_runtime_context, compute_period_window, enrich
from hubgh.hubgh.payroll.export import build_single_sheet


SOURCE_PARSERS = {
	"clonk": clonk,
	"payflow": payflow,
	"fincomercio": fincomercio,
	"fongiga": fongiga,
	"libranza_davivienda": libranza_davivienda,
	"libranza_compensar": libranza_compensar,
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

	resolved_name = file_name or (file_url.rsplit("/", 1)[-1] if file_url else "")
	lowered = (resolved_name or "").lower()
	# openpyxl no soporta el formato .xls legacy. Pedimos resave a .xlsx
	# antes de subir para no romper el flujo más adelante.
	if lowered.endswith(".xls") and not lowered.endswith(".xlsx"):
		frappe.throw(
			_(
				"El archivo {0} está en formato .xls antiguo. Abrílo y guardalo como "
				".xlsx (Archivo → Guardar como → Libro de Excel) antes de subirlo."
			).format(resolved_name)
		)

	doc = frappe.get_doc(
		{
			"doctype": "Payroll Run File",
			"run": run_name,
			"file_url": file_url,
			"file_name": resolved_name,
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
		# El title del Error Log no puede pasar de 140 chars, así que lo
		# acotamos a algo legible.
		short = (resolved_name or "archivo")[:60]
		frappe.log_error(
			message=f"Detection failed for {file_url}: {exc}",
			title=f"PayrollRunFile detect failed: {short}",
		)
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
	# Excluir las novedades en estado `error` y `pending` del export — sólo
	# llegan al Excel las que el pipeline pudo enriquecer/computar (computed
	# o skipped). Las en error siguen visibles en Payroll Novedad para que
	# el operador las pueda revisar.
	novedades_docs = frappe.get_all(
		"Payroll Novedad",
		filters={
			"run": run_name,
			# `partial` se incluye: trae cantidad real (horas/días) aunque
			# el importe quede en 0 mientras el empleado se crea. El
			# operador ve la fila en la prenómina con la cantidad y puede
			# ajustar manualmente si quiere.
			"calc_status": ["in", ["computed", "partial", "skipped"]],
		},
		fields=[
			"name", "documento_identidad", "empleado", "contrato",
			"tipo_jornada_snapshot", "salario_mensual_snapshot",
			"tipo_novedad", "jornada_aplicable",
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

@frappe.whitelist()
def list_runs(limit: int = 20) -> list[dict]:
	"""Lista los Payroll Run más recientes para el selector del workspace."""
	return frappe.get_all(
		"Payroll Run",
		fields=["name", "period_year", "period_month", "status", "started_at", "closed_at"],
		order_by="creation desc",
		limit_page_length=int(limit or 20),
	)


@frappe.whitelist()
def get_run_summary(run_name: str) -> dict:
	"""Devuelve el header data + resumen de archivos + conteos."""
	if not frappe.db.exists("Payroll Run", run_name):
		frappe.throw(_("Payroll Run no existe: {0}").format(run_name))
	run = frappe.get_doc("Payroll Run", run_name)
	files = frappe.get_all(
		"Payroll Run File",
		filters={"run": run_name},
		fields=[
			"name", "file_url", "file_name", "detected_source",
			"detected_period_year", "detected_period_month",
			"parse_status", "parse_log",
		],
		order_by="creation asc",
	)
	novedades_count = frappe.db.count("Payroll Novedad", {"run": run_name})
	by_status = frappe.db.sql(
		"""
		SELECT calc_status, COUNT(*) AS qty
		FROM `tabPayroll Novedad`
		WHERE run = %s
		GROUP BY calc_status
		""",
		(run_name,),
		as_dict=True,
	)
	summary = {}
	try:
		summary = json.loads(run.summary_json or "{}")
	except Exception:
		summary = {}
	run_dict = run.as_dict(no_default_fields=True)
	run_dict["name"] = run.name  # as_dict(no_default_fields=True) lo excluye en algunas versiones
	return {
		"run": run_dict,
		"files": files,
		"counts": {
			"novedades": novedades_count,
			"by_status": {row["calc_status"]: row["qty"] for row in by_status},
		},
		"summary": summary,
		"valid_sources": [s.id for s in catalogs.SOURCES],
	}


@frappe.whitelist()
def get_run_consolidated(run_name: str, jornada: str = "", search: str = "") -> dict:
	"""Vista consolidada por empleado para revisión previa al export.

	Devuelve `{employees: [...], totals: {...}}` donde cada employee es:
	  {
	    cedula, nombre, jornada, cargo, sucursal, salario,
	    horas: {HD: {qty, amt}, HN: {qty, amt}, ...},
	    dias: {DESCANSO: qty, VACACIONES: qty, ...},
	    descuentos: {LIBRANZA_FINCOMERCIO: amt, ...},
	    auxilio_transporte, total_devengado, total_descontado, neto,
	    novedad_count, has_partial,
	  }

	Es la misma agregación que el export, pero JSON-friendly y filtrable.
	"""
	if not frappe.db.exists("Payroll Run", run_name):
		frappe.throw(_("Payroll Run no existe: {0}").format(run_name))

	from hubgh.hubgh.payroll.compute import auxilio_transporte
	from hubgh.hubgh.payroll.compute.literal import DESCUENTO_TYPES

	# Una sola query con join al empleado para los nombres limpios.
	rows = frappe.db.sql(
		"""
		SELECT n.documento_identidad, n.empleado, n.tipo_jornada_snapshot,
			n.salario_mensual_snapshot, n.tipo_novedad, n.unidad,
			n.computed_amount, n.computed_quantity, n.cantidad,
			n.calc_status, n.raw_payload
		FROM `tabPayroll Novedad` n
		WHERE n.run = %s
			AND n.calc_status IN ('computed', 'partial', 'skipped')
		""",
		(run_name,),
		as_dict=True,
	)

	by_emp: dict[str, dict] = {}
	for r in rows:
		key = r.get("empleado") or r.get("documento_identidad") or "SIN_DOC"
		try:
			payload = json.loads(r.get("raw_payload") or "{}")
		except Exception:
			payload = {}
		bucket = by_emp.setdefault(
			key,
			{
				"cedula": r.get("documento_identidad") or "",
				"nombre": "",
				"jornada": "",
				"cargo": "",
				"sucursal": "",
				"salario": 0.0,
				"horas": {},
				"dias": {},
				"descuentos": {},
				"otros_pagos": {},
				"total_devengado": 0.0,
				"total_descontado": 0.0,
				"novedad_count": 0,
				"has_partial": False,
			},
		)
		# First-non-empty para identificación.
		if not bucket["nombre"] and payload.get("empleado_nombre"):
			bucket["nombre"] = payload["empleado_nombre"]
		if not bucket["jornada"] and r.get("tipo_jornada_snapshot"):
			bucket["jornada"] = r["tipo_jornada_snapshot"]
		if not bucket["cargo"] and payload.get("cargo"):
			bucket["cargo"] = payload["cargo"]
		if not bucket["sucursal"]:
			bucket["sucursal"] = payload.get("sucursal") or payload.get("sede") or ""
		if not bucket["salario"] and r.get("salario_mensual_snapshot"):
			bucket["salario"] = float(r["salario_mensual_snapshot"])

		tipo = r.get("tipo_novedad") or "OTRO"
		amount = float(r.get("computed_amount") or 0)
		qty = float(r.get("computed_quantity") or r.get("cantidad") or 0)
		bucket["novedad_count"] += 1
		if r.get("calc_status") == "partial":
			bucket["has_partial"] = True

		if r.get("unidad") == "horas":
			h = bucket["horas"].setdefault(tipo, {"qty": 0.0, "amt": 0.0})
			h["qty"] += qty
			h["amt"] += amount
			bucket["total_devengado"] += amount
		elif r.get("unidad") == "dias":
			bucket["dias"][tipo] = bucket["dias"].get(tipo, 0.0) + qty
			# Los importes de días suman a devengado salvo descuento por ausencia.
			if tipo == "AUSENCIA_INJUSTIFICADA":
				bucket["total_descontado"] += amount
			else:
				bucket["total_devengado"] += amount
		else:  # cop / unidades
			if tipo in DESCUENTO_TYPES:
				bucket["descuentos"][tipo] = bucket["descuentos"].get(tipo, 0.0) + amount
				bucket["total_descontado"] += amount
			else:
				bucket["otros_pagos"][tipo] = bucket["otros_pagos"].get(tipo, 0.0) + amount
				bucket["total_devengado"] += amount

	# Auxilio transporte + neto. params globales una sola vez.
	from hubgh.hubgh.payroll.enrichment import build_runtime_context

	ctx = build_runtime_context()
	NO_REM = ("LICENCIA_NO_REMUNERADA", "SUSPENSION_CONTRATO", "AUSENCIA_INJUSTIFICADA")
	for emp in by_emp.values():
		dias_no_rem = sum(emp["dias"].get(t, 0.0) for t in NO_REM)
		emp["auxilio_transporte"] = auxilio_transporte.compute_for_period(
			emp["salario"], ctx.params, dias_no_remunerados=dias_no_rem
		)
		emp["neto"] = round(
			emp["total_devengado"] + emp["auxilio_transporte"] + emp["total_descontado"], 2
		)
		emp["total_devengado"] = round(emp["total_devengado"], 2)
		emp["total_descontado"] = round(emp["total_descontado"], 2)

	# Filtros opcionales.
	def _matches(emp: dict) -> bool:
		if jornada in {"Tiempo Completo", "Tiempo Parcial"} and emp["jornada"] != jornada:
			return False
		if search:
			needle = search.lower()
			hay = (
				needle in (emp["nombre"] or "").lower()
				or needle in (emp["cedula"] or "").lower()
				or needle in (emp["cargo"] or "").lower()
				or needle in (emp["sucursal"] or "").lower()
			)
			if not hay:
				return False
		return True

	employees = sorted(
		(e for e in by_emp.values() if _matches(e)),
		key=lambda e: (e["sucursal"], e["nombre"], e["cedula"]),
	)
	totals = {
		"empleados": len(employees),
		"total_devengado": round(sum(e["total_devengado"] for e in employees), 2),
		"total_descontado": round(sum(e["total_descontado"] for e in employees), 2),
		"total_neto": round(sum(e["neto"] for e in employees), 2),
		"total_aux_transporte": round(sum(e["auxilio_transporte"] for e in employees), 2),
		"empleados_partial": sum(1 for e in employees if e["has_partial"]),
	}
	return {"employees": employees, "totals": totals}


@frappe.whitelist()
def get_employee_detail(run_name: str, documento: str) -> dict:
	"""Detalle por empleado para el modal de revisión.

	Devuelve `{empleado, totales, novedades}` con TODAS las novedades del
	empleado en el run, ordenadas por unidad y tipo, cada una con sus
	fechas, cantidad, importe, calc_status, notas y un resumen del raw
	payload original (para auditoría visible en el modal).
	"""
	if not frappe.db.exists("Payroll Run", run_name):
		frappe.throw(_("Payroll Run no existe: {0}").format(run_name))
	if not documento:
		frappe.throw(_("Documento no especificado."))

	rows = frappe.db.sql(
		"""
		SELECT n.name, n.tipo_novedad, n.unidad, n.cantidad, n.valor,
			n.computed_quantity, n.computed_amount, n.calc_status,
			n.calc_notes, n.fecha_desde, n.fecha_hasta,
			n.tipo_jornada_snapshot, n.salario_mensual_snapshot,
			n.empleado, n.contrato, n.documento_identidad,
			n.raw_payload, f.detected_source, f.file_name
		FROM `tabPayroll Novedad` n
		LEFT JOIN `tabPayroll Run File` f ON f.name = n.source_file
		WHERE n.run = %s AND n.documento_identidad = %s
		ORDER BY FIELD(n.unidad, 'horas', 'dias', 'cop', 'unidades'),
			n.tipo_novedad, n.fecha_desde
		""",
		(run_name, documento),
		as_dict=True,
	)
	if not rows:
		frappe.throw(_("Sin novedades para documento '{0}' en este Run.").format(documento))

	# Identidad: first-non-empty desde raw_payload.
	empleado_meta = {
		"cedula": documento,
		"nombre": "",
		"jornada": "",
		"cargo": "",
		"sucursal": "",
		"salario": 0.0,
		"empleado_link": rows[0].get("empleado") or None,
		"contrato_link": rows[0].get("contrato") or None,
	}
	for r in rows:
		try:
			payload = json.loads(r.get("raw_payload") or "{}")
		except Exception:
			payload = {}
		if not empleado_meta["nombre"]:
			empleado_meta["nombre"] = payload.get("empleado_nombre") or ""
		if not empleado_meta["jornada"] and r.get("tipo_jornada_snapshot"):
			empleado_meta["jornada"] = r["tipo_jornada_snapshot"]
		if not empleado_meta["cargo"] and payload.get("cargo"):
			empleado_meta["cargo"] = payload["cargo"]
		if not empleado_meta["sucursal"]:
			empleado_meta["sucursal"] = payload.get("sucursal") or payload.get("sede") or ""
		if not empleado_meta["salario"] and r.get("salario_mensual_snapshot"):
			empleado_meta["salario"] = float(r["salario_mensual_snapshot"])

	# Totales.
	from hubgh.hubgh.payroll.compute import auxilio_transporte
	from hubgh.hubgh.payroll.compute.literal import DESCUENTO_TYPES
	from hubgh.hubgh.payroll.enrichment import build_runtime_context

	total_dev = 0.0
	total_desc = 0.0
	dias_no_rem = 0.0
	for r in rows:
		amt = float(r.get("computed_amount") or 0)
		t = r.get("tipo_novedad") or ""
		u = r.get("unidad")
		if t in DESCUENTO_TYPES or t == "AUSENCIA_INJUSTIFICADA":
			total_desc += amt
		else:
			total_dev += amt
		if t in {"LICENCIA_NO_REMUNERADA", "SUSPENSION_CONTRATO", "AUSENCIA_INJUSTIFICADA"}:
			dias_no_rem += float(r.get("computed_quantity") or r.get("cantidad") or 0)

	ctx = build_runtime_context()
	aux_t = auxilio_transporte.compute_for_period(
		empleado_meta["salario"], ctx.params, dias_no_remunerados=dias_no_rem
	)

	novedades_clean = []
	for r in rows:
		try:
			payload = json.loads(r.get("raw_payload") or "{}")
		except Exception:
			payload = {}
		novedades_clean.append({
			"name": r.get("name"),
			"tipo_novedad": r.get("tipo_novedad"),
			"unidad": r.get("unidad"),
			"cantidad": r.get("cantidad"),
			"valor": r.get("valor"),
			"computed_quantity": r.get("computed_quantity"),
			"computed_amount": r.get("computed_amount"),
			"calc_status": r.get("calc_status"),
			"calc_notes": r.get("calc_notes"),
			"fecha_desde": r.get("fecha_desde"),
			"fecha_hasta": r.get("fecha_hasta"),
			"source": r.get("detected_source"),
			"source_file": r.get("file_name"),
			"raw_summary": payload.get("concepto_clonk")
				or payload.get("concepto_fincomercio")
				or payload.get("concepto_fongiga")
				or payload.get("campo")
				or "",
		})

	return {
		"empleado": empleado_meta,
		"totales": {
			"total_devengado": round(total_dev, 2),
			"total_descontado": round(total_desc, 2),
			"auxilio_transporte": aux_t,
			"neto": round(total_dev + aux_t + total_desc, 2),
			"novedad_count": len(rows),
		},
		"novedades": novedades_clean,
	}


@frappe.whitelist()
def list_novedades(run_name: str, limit: int = 500, jornada: str = "", tipo: str = "") -> list[dict]:
	"""Lista paginada de novedades para la tabla de revisión."""
	filters: dict = {"run": run_name}
	if jornada in {"Tiempo Completo", "Tiempo Parcial"}:
		filters["tipo_jornada_snapshot"] = jornada
	if tipo:
		filters["tipo_novedad"] = tipo
	rows = frappe.get_all(
		"Payroll Novedad",
		filters=filters,
		fields=[
			"name", "empleado", "documento_identidad", "tipo_jornada_snapshot",
			"tipo_novedad", "unidad", "valor", "cantidad", "fecha_desde",
			"fecha_hasta", "calc_status", "computed_amount",
			"computed_quantity", "calc_notes", "manual_override",
		],
		order_by="documento_identidad asc, tipo_novedad asc",
		limit_page_length=int(limit or 500),
	)
	# Enriquecer con nombre del empleado.
	emp_names = {r.get("empleado") for r in rows if r.get("empleado")}
	if emp_names:
		emp_meta = {
			r["name"]: r
			for r in frappe.get_all(
				"Ficha Empleado",
				filters={"name": ["in", list(emp_names)]},
				fields=["name", "nombres", "apellidos"],
				limit_page_length=0,
			)
		}
		for row in rows:
			meta = emp_meta.get(row.get("empleado"), {})
			row["empleado_label"] = (
				f"{meta.get('nombres', '')} {meta.get('apellidos', '')}".strip()
			) or row.get("empleado") or row.get("documento_identidad")
	return rows


@frappe.whitelist()
def update_detected_source(run_file_name: str, detected_source: str) -> dict:
	"""Permite al operador corregir manualmente la fuente detectada."""
	valid = {s.id for s in catalogs.SOURCES}
	if detected_source not in valid:
		frappe.throw(_("Fuente '{0}' no es válida.").format(detected_source))
	frappe.db.set_value(
		"Payroll Run File", run_file_name, "detected_source", detected_source
	)
	return {"ok": True, "name": run_file_name, "detected_source": detected_source}


@frappe.whitelist()
def delete_run_file(run_file_name: str) -> dict:
	"""Elimina un archivo del Run (sólo si el Run no está exported)."""
	doc = frappe.get_doc("Payroll Run File", run_file_name)
	run = frappe.get_doc("Payroll Run", doc.run)
	if run.status == "exported":
		frappe.throw(_("No se puede eliminar archivos de un Run ya exportado."))
	frappe.delete_doc("Payroll Run File", run_file_name, force=1)
	return {"ok": True}


@frappe.whitelist(allow_guest=False)
def list_manual_templates() -> list[dict]:
	"""Lista las plantillas manuales disponibles para que la UI las muestre."""
	from hubgh.hubgh.payroll.manual_templates import list_templates

	return list_templates()


@frappe.whitelist(allow_guest=False)
def download_manual_template(template_id: str) -> None:
	"""Genera el xlsx de la plantilla y lo entrega como descarga directa."""
	from hubgh.hubgh.payroll.manual_templates import TEMPLATES, build_template

	spec = TEMPLATES.get(template_id)
	if not spec:
		frappe.throw(_("Template '{0}' no existe.").format(template_id))
	blob = build_template(template_id)
	frappe.response.filename = f"plantilla_{template_id}.xlsx"
	frappe.response.filecontent = blob
	frappe.response.type = "binary"
	frappe.response["Content-Type"] = (
		"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
	)


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
			"salario_mensual_snapshot": enriched.salario_mensual,
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
		self.salario_mensual = float(doc_dict.get("salario_mensual_snapshot") or 0.0)
		try:
			self.raw_payload = json.loads(doc_dict.get("raw_payload") or "{}")
		except Exception:
			self.raw_payload = {}
