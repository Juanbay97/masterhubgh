"""Enrichment del pipeline payroll.

Toma una `NovedadCanonica` (la sale del adapter) y le agrega:
- empleado (name de Ficha Empleado).
- contrato (name de Contrato activo a la fecha del periodo).
- tipo_jornada_snapshot (canonicalizado, inmutable post-procesamiento).
- jornada_aplicable_resuelta (TC/TP/both según el tipo + jornada).
- valor_hora_base (para tipos en horas).
- calc_status (`pending` si todo OK; `skipped` si el tipo no aplica al
  contrato; `error` si falta empleado o contrato).
- calc_notes (motivo del skip/error).

Diseño testeable: las llamadas a Frappe entran por un `EnrichmentContext`
inyectable. En runtime se construye uno con `frappe.db`; en tests se
construye uno con stubs en memoria.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Callable

from hubgh.hubgh.jornada_utils import (
	TIPO_JORNADA_FULL_TIME,
	TIPO_JORNADA_PART_TIME,
	normalize_tipo_jornada,
)
from hubgh.hubgh.payroll import catalogs
from hubgh.hubgh.payroll.adapters import NovedadCanonica


# ──────────────────────────────────────────────────────────────────────
# Estructuras de datos
# ──────────────────────────────────────────────────────────────────────

@dataclass
class EmployeeRecord:
	name: str
	cedula: str
	tipo_jornada: str = ""        # campo Ficha Empleado.tipo_jornada
	estado: str = "Activo"


@dataclass
class ContractRecord:
	name: str
	empleado: str
	numero_documento: str = ""
	tipo_jornada: str = ""        # canonicalizado luego
	tipo_contrato: str = ""
	estado_contrato: str = "Activo"
	fecha_ingreso: date | None = None
	fecha_fin_contrato: date | None = None
	salario: float = 0.0
	horas_trabajadas_mes: float = 0.0


@dataclass
class GlobalParams:
	hora_tp_fija: float = 9530.0
	auxilio_transporte: float = 249095.0
	jornada_induccion_tp_horas: float = 7.33
	divisor_hora_tc: float = 240.0
	salario_minimo_mensual: float = 1_750_905.0  # SMMLV 2026


@dataclass
class EnrichmentContext:
	"""Resolvers inyectables y parámetros globales.

	Los resolvers reciben el periodo (ya calculado por el caller) para
	que puedan elegir el contrato vigente al cierre y devolver None si
	el empleado o el contrato no existen.
	"""

	resolve_employee: Callable[[str], EmployeeRecord | None]
	resolve_contract: Callable[[str, date, date], ContractRecord | None]
	params: GlobalParams = field(default_factory=GlobalParams)


@dataclass
class EnrichedNovedad:
	"""Resultado del enrichment: lo que se persiste en Payroll Novedad."""

	# Identidad
	documento_identidad: str
	empleado: str | None
	contrato: str | None
	tipo_jornada_snapshot: str  # "Tiempo Completo" | "Tiempo Parcial" | ""
	# Novedad
	tipo_novedad: str
	jornada_aplicable: str  # del catálogo
	unidad: str
	valor: float | None
	cantidad: float | None
	fecha_desde: str | None
	fecha_hasta: str | None
	# Cálculo
	calc_status: str        # pending | computed | skipped | error
	calc_notes: str
	valor_hora_base: float | None  # útil para tipos en horas
	salario_mensual: float = 0.0   # para tipos en días: valor_día = salario/30
	# Computed (lo llena el módulo compute, no enrich):
	computed_amount: float | None = None
	computed_quantity: float | None = None
	# Auditoría
	raw_payload: dict = field(default_factory=dict)


# ──────────────────────────────────────────────────────────────────────
# API pública
# ──────────────────────────────────────────────────────────────────────

def enrich(
	novedad: NovedadCanonica,
	period_start: date,
	period_end: date,
	ctx: EnrichmentContext,
) -> EnrichedNovedad:
	"""Pipeline de enrichment para una novedad canónica.

	`period_start` y `period_end` los provee el caller (servicio) leyendo
	`PERIODO_CORTE_TC` o `PERIODO_CORTE_TP` y el periodo lógico del Run.
	"""
	type_spec = catalogs.NOVEDAD_TYPES_BY_ID.get(novedad.tipo_novedad)
	jornada_aplicable = type_spec.jornada_aplicable if type_spec else catalogs.JORNADA_BOTH

	# 1) Empleado
	emp = ctx.resolve_employee(novedad.documento_identidad)
	if emp is None:
		return _build_error(
			novedad,
			jornada_aplicable,
			f"Empleado no encontrado por documento '{novedad.documento_identidad}'.",
		)

	# 2) Contrato vigente al periodo
	contrato = ctx.resolve_contract(emp.name, period_start, period_end)
	if contrato is None:
		return _build_error(
			novedad,
			jornada_aplicable,
			f"Sin contrato activo para empleado '{emp.name}' en el periodo "
			f"{period_start.isoformat()} a {period_end.isoformat()}.",
			empleado=emp.name,
		)

	# 3) Snapshot de jornada (canonicalizada)
	jornada_snapshot = normalize_tipo_jornada(contrato.tipo_jornada) or normalize_tipo_jornada(
		emp.tipo_jornada
	)
	if not jornada_snapshot:
		return _build_error(
			novedad,
			jornada_aplicable,
			f"Jornada del contrato '{contrato.name}' no canonicaliza a TC ni TP "
			f"(valor crudo: '{contrato.tipo_jornada or emp.tipo_jornada}').",
			empleado=emp.name,
			contrato=contrato.name,
		)

	# 4) Aplicabilidad
	if not _is_applicable(jornada_aplicable, jornada_snapshot):
		return _build_skipped(
			novedad,
			jornada_aplicable,
			jornada_snapshot,
			emp.name,
			contrato.name,
			f"Tipo '{novedad.tipo_novedad}' aplica a '{jornada_aplicable}' "
			f"y el contrato es '{jornada_snapshot}'.",
		)

	# 5) Valor hora base (sólo relevante para tipos en horas)
	valor_hora = _compute_valor_hora_base(contrato, jornada_snapshot, ctx.params)

	return EnrichedNovedad(
		documento_identidad=novedad.documento_identidad,
		empleado=emp.name,
		contrato=contrato.name,
		tipo_jornada_snapshot=jornada_snapshot,
		tipo_novedad=novedad.tipo_novedad,
		jornada_aplicable=jornada_aplicable,
		unidad=novedad.unidad,
		valor=novedad.valor,
		cantidad=novedad.cantidad,
		fecha_desde=novedad.fecha_desde,
		fecha_hasta=novedad.fecha_hasta,
		calc_status="pending",
		calc_notes="",
		valor_hora_base=valor_hora,
		salario_mensual=float(contrato.salario or 0.0),
		raw_payload=dict(novedad.raw_payload),
	)


def compute_period_window(year, month, jornada: str) -> tuple[date, date]:
	"""Devuelve (start, end) del periodo según jornada.

	- TC: del 16 del mes anterior al 15 del mes vigente.
	- TP: del 23 del mes anterior al 22 del mes vigente.

	`year` y `month` se castean a int para tolerar el caso de Frappe
	pasando el campo Select `period_month` como string.
	"""
	year = int(year)
	month = int(month)
	cutoff = catalogs.PERIODO_CORTE_TC if jornada == TIPO_JORNADA_FULL_TIME else catalogs.PERIODO_CORTE_TP
	prev_year, prev_month = (year - 1, 12) if month == 1 else (year, month - 1)
	start = date(prev_year, prev_month, cutoff["start_day_prev_month"])
	end = date(year, month, cutoff["end_day_current_month"])
	return start, end


# ──────────────────────────────────────────────────────────────────────
# Helpers privados
# ──────────────────────────────────────────────────────────────────────

def _is_applicable(jornada_aplicable: str, jornada_snapshot: str) -> bool:
	if jornada_aplicable == catalogs.JORNADA_BOTH:
		return True
	if jornada_aplicable == "TC":
		return jornada_snapshot == TIPO_JORNADA_FULL_TIME
	if jornada_aplicable == "TP":
		return jornada_snapshot == TIPO_JORNADA_PART_TIME
	# Por las dudas: tipo desconocido → aplica.
	return True


def _compute_valor_hora_base(
	contrato: ContractRecord,
	jornada_snapshot: str,
	params: GlobalParams,
) -> float:
	"""Calcula el valor hora base.

	- TC: salario / Contrato.horas_trabajadas_mes (si > 0). Fallback al
	  parámetro global `divisor_hora_tc`.
	- TP: valor fijo parametrizado (`hora_tp_fija`), independiente del
	  salario porque la jornada parcial cobra por hora literal.
	"""
	if jornada_snapshot == TIPO_JORNADA_PART_TIME:
		return float(params.hora_tp_fija or 0.0)
	# TC: divisor del contrato → fallback global.
	divisor = float(contrato.horas_trabajadas_mes or 0.0)
	if divisor <= 0:
		divisor = float(params.divisor_hora_tc or 240.0)
	salario = float(contrato.salario or 0.0)
	if divisor <= 0 or salario <= 0:
		return 0.0
	return salario / divisor


def _build_error(
	novedad: NovedadCanonica,
	jornada_aplicable: str,
	note: str,
	*,
	empleado: str | None = None,
	contrato: str | None = None,
) -> EnrichedNovedad:
	return EnrichedNovedad(
		documento_identidad=novedad.documento_identidad,
		empleado=empleado,
		contrato=contrato,
		tipo_jornada_snapshot="",
		tipo_novedad=novedad.tipo_novedad,
		jornada_aplicable=jornada_aplicable,
		unidad=novedad.unidad,
		valor=novedad.valor,
		cantidad=novedad.cantidad,
		fecha_desde=novedad.fecha_desde,
		fecha_hasta=novedad.fecha_hasta,
		calc_status="error",
		calc_notes=note,
		valor_hora_base=None,
		raw_payload=dict(novedad.raw_payload),
	)


def _build_skipped(
	novedad: NovedadCanonica,
	jornada_aplicable: str,
	jornada_snapshot: str,
	empleado: str,
	contrato: str,
	note: str,
) -> EnrichedNovedad:
	return EnrichedNovedad(
		documento_identidad=novedad.documento_identidad,
		empleado=empleado,
		contrato=contrato,
		tipo_jornada_snapshot=jornada_snapshot,
		tipo_novedad=novedad.tipo_novedad,
		jornada_aplicable=jornada_aplicable,
		unidad=novedad.unidad,
		valor=novedad.valor,
		cantidad=novedad.cantidad,
		fecha_desde=novedad.fecha_desde,
		fecha_hasta=novedad.fecha_hasta,
		calc_status="skipped",
		calc_notes=note,
		valor_hora_base=None,
		raw_payload=dict(novedad.raw_payload),
	)


# ──────────────────────────────────────────────────────────────────────
# Frappe-bound builder (runtime context)
# ──────────────────────────────────────────────────────────────────────

def build_runtime_context() -> EnrichmentContext:
	"""Construye un `EnrichmentContext` que consulta a Frappe y al
	DocType Single de parámetros globales.
	"""
	import frappe

	def _resolve_employee(documento: str) -> EmployeeRecord | None:
		documento = (documento or "").strip()
		if not documento:
			return None
		row = frappe.db.get_value(
			"Ficha Empleado",
			{"cedula": documento},
			["name", "cedula", "tipo_jornada", "estado"],
			as_dict=True,
		)
		if not row:
			return None
		return EmployeeRecord(
			name=row["name"],
			cedula=row.get("cedula") or documento,
			tipo_jornada=row.get("tipo_jornada") or "",
			estado=row.get("estado") or "",
		)

	def _resolve_contract(empleado: str, period_start: date, period_end: date) -> ContractRecord | None:
		# Toma el contrato activo a `period_end`. Si hay varios candidatos,
		# el más reciente por `fecha_ingreso`.
		filters = {"empleado": empleado, "estado_contrato": "Activo"}
		rows = frappe.get_all(
			"Contrato",
			filters=filters,
			fields=[
				"name", "empleado", "numero_documento", "tipo_jornada",
				"tipo_contrato", "estado_contrato", "fecha_ingreso",
				"fecha_fin_contrato", "salario", "horas_trabajadas_mes",
			],
			order_by="fecha_ingreso desc",
			limit_page_length=10,
		)
		for row in rows:
			fi = row.get("fecha_ingreso")
			ff = row.get("fecha_fin_contrato")
			if fi and fi > period_end:
				continue
			if ff and ff < period_start:
				continue
			return ContractRecord(
				name=row["name"],
				empleado=row["empleado"],
				numero_documento=row.get("numero_documento") or "",
				tipo_jornada=row.get("tipo_jornada") or "",
				tipo_contrato=row.get("tipo_contrato") or "",
				estado_contrato=row.get("estado_contrato") or "",
				fecha_ingreso=fi,
				fecha_fin_contrato=ff,
				salario=float(row.get("salario") or 0),
				horas_trabajadas_mes=float(row.get("horas_trabajadas_mes") or 0),
			)
		return None

	# Parámetros globales: leer del Single, fallback a defaults.
	params = GlobalParams()
	if frappe.db.exists("DocType", "Payroll Parametros Globales"):
		try:
			doc = frappe.get_single("Payroll Parametros Globales")
			params = GlobalParams(
				hora_tp_fija=float(doc.valor_hora_tp_fija or params.hora_tp_fija),
				auxilio_transporte=float(doc.auxilio_transporte or params.auxilio_transporte),
				jornada_induccion_tp_horas=float(
					doc.jornada_induccion_tp_horas or params.jornada_induccion_tp_horas
				),
				divisor_hora_tc=float(doc.divisor_hora_tc or params.divisor_hora_tc),
				salario_minimo_mensual=float(
					doc.salario_minimo_mensual or params.salario_minimo_mensual
				),
			)
		except Exception:
			pass

	return EnrichmentContext(
		resolve_employee=_resolve_employee,
		resolve_contract=_resolve_contract,
		params=params,
	)
