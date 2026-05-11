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
class CargoSalary:
	"""Datos de nómina asociados a un Cargo del catálogo."""

	name: str
	salario_base_tc: float = 0.0
	horas_trabajadas_mes: float = 0.0
	aplica_horas_extras: bool = True
	tipo_cargo: str = ""   # "Operativo" | "Administrativo" | ""


@dataclass
class EnrichmentContext:
	"""Resolvers inyectables y parámetros globales.

	Los resolvers reciben el periodo (ya calculado por el caller) para
	que puedan elegir el contrato vigente al cierre y devolver None si
	el empleado o el contrato no existen.

	`resolve_cargo` es el fallback cuando el archivo trae cargo pero el
	empleado / contrato no están en DB. Permite resolver el salario
	desde el catálogo `Cargo` (campo salario_base_tc).
	"""

	resolve_employee: Callable[[str], EmployeeRecord | None]
	resolve_contract: Callable[[str, date, date], ContractRecord | None]
	resolve_cargo: Callable[[str], CargoSalary | None] = field(default=lambda _: None)
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
	cargo_aplica_horas_extras: bool = True  # filtro para HE* en compute/recargos
	cargo_tipo: str = ""            # "Operativo" | "Administrativo" | "" — gate de bonificación PDV
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

	# Modo best-effort: aunque falte empleado, contrato o jornada
	# canonicalizable, persistimos la novedad con lo que se pueda y
	# dejamos `calc_status='pending'` con notas claras. El compute
	# decidirá si puede calcular el importe ('computed') o solo la
	# cantidad ('partial'). Los `error` se reservan para fallos del
	# adapter (no llegan acá).
	notas: list[str] = []

	# 1) Empleado (opcional)
	emp = ctx.resolve_employee(novedad.documento_identidad)
	if emp is None:
		notas.append(
			f"Empleado no encontrado por documento '{novedad.documento_identidad}'."
		)
		empleado_name = None
		emp_jornada = ""
	else:
		empleado_name = emp.name
		emp_jornada = emp.tipo_jornada or ""

	# 2) Contrato vigente al periodo (opcional)
	contrato = ctx.resolve_contract(empleado_name, period_start, period_end) if empleado_name else None
	if empleado_name and contrato is None:
		notas.append(
			f"Sin contrato activo para empleado '{empleado_name}' en el periodo "
			f"{period_start.isoformat()} a {period_end.isoformat()}."
		)

	# 3) Snapshot de jornada — el archivo es la fuente de verdad. Lo que
	# la DB diga sólo aplica cuando el archivo no trae nada interpretable.
	clonk_contrato_text = (novedad.raw_payload or {}).get("contrato_text", "")
	contrato_jornada_raw = contrato.tipo_jornada if contrato else ""
	jornada_snapshot = (
		normalize_tipo_jornada(clonk_contrato_text)
		or normalize_tipo_jornada(contrato_jornada_raw)
		or normalize_tipo_jornada(emp_jornada)
	)
	if not jornada_snapshot:
		notas.append(
			"Sin jornada canonicalizable en el archivo ni en la DB; los cómputos "
			"por hora quedarán en cero."
		)

	# 4) Aplicabilidad — si la jornada está clara y el tipo no aplica, skip.
	if jornada_snapshot and not _is_applicable(jornada_aplicable, jornada_snapshot):
		return _build_skipped(
			novedad,
			jornada_aplicable,
			jornada_snapshot,
			empleado_name or "",
			contrato.name if contrato else "",
			f"Tipo '{novedad.tipo_novedad}' aplica a '{jornada_aplicable}' "
			f"y la jornada es '{jornada_snapshot}'.",
		)

	# 5) Resolver salario y valor hora base. Prioridad:
	#    a) Contrato en DB (TC: salario / horas_trabajadas_mes; TP: hora_tp_fija).
	#    b) Catálogo Cargo (cuando el archivo trae cargo pero no hay contrato):
	#       resuelve salario_base_tc / horas_trabajadas_mes del Cargo.
	#    c) Sin nada → 0 (queda en `partial`).
	cargo_label = (novedad.raw_payload or {}).get("cargo") or ""
	cargo_record: CargoSalary | None = None
	# Resolvemos siempre el cargo del archivo (haya contrato o no) porque
	# `aplica_horas_extras` se usa para filtrar HE* aunque tengamos
	# contrato en DB. Si falla la consulta lo dejamos en None y el
	# default sigue siendo "sí aplica".
	if cargo_label:
		try:
			cargo_record = ctx.resolve_cargo(cargo_label)
		except Exception:
			cargo_record = None

	if contrato and jornada_snapshot:
		valor_hora = _compute_valor_hora_base(contrato, jornada_snapshot, ctx.params)
		salario = float(contrato.salario or 0.0)
	elif jornada_snapshot == TIPO_JORNADA_PART_TIME:
		# TP: hora fija parametrizada, sin importar contrato/cargo.
		valor_hora = float(ctx.params.hora_tp_fija or 0.0)
		salario = 0.0  # TP no tiene salario mensual fijo.
	elif cargo_record and cargo_record.salario_base_tc > 0 and jornada_snapshot == TIPO_JORNADA_FULL_TIME:
		# TC: usar el catálogo Cargo como fallback al contrato.
		salario = float(cargo_record.salario_base_tc)
		divisor = float(cargo_record.horas_trabajadas_mes or 0)
		if divisor <= 0:
			divisor = float(ctx.params.divisor_hora_tc or 240.0)
		valor_hora = salario / divisor if divisor > 0 else 0.0
		notas.append(f"Salario resuelto desde Cargo '{cargo_label}' (sin contrato en DB).")
	else:
		valor_hora = 0.0
		salario = 0.0

	return EnrichedNovedad(
		documento_identidad=novedad.documento_identidad,
		empleado=empleado_name,
		contrato=contrato.name if contrato else None,
		tipo_jornada_snapshot=jornada_snapshot,
		tipo_novedad=novedad.tipo_novedad,
		jornada_aplicable=jornada_aplicable,
		unidad=novedad.unidad,
		valor=novedad.valor,
		cantidad=novedad.cantidad,
		fecha_desde=novedad.fecha_desde,
		fecha_hasta=novedad.fecha_hasta,
		calc_status="pending",
		calc_notes=" ".join(notas),
		valor_hora_base=valor_hora,
		salario_mensual=salario,
		cargo_aplica_horas_extras=(cargo_record.aplica_horas_extras if cargo_record else True),
		cargo_tipo=(cargo_record.tipo_cargo if cargo_record else ""),
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

_CARGO_SUFFIX_RE = __import__("re").compile(
	r"\s*[-–—]\s*(i|ii|iii|iv|v|vi|vii|viii|ix|x|1|2|3|4|5|6|7|8|9|10)\s*$",
	__import__("re").IGNORECASE,
)


def canonicalize_cargo(text: str | None) -> str:
	"""Normaliza un nombre de cargo del archivo.

	Quita: tildes, mayúsculas, sufijos ` - I`, ` - II`, ` - 1`, ` - 2`, etc.
	Mantiene el resto del texto ya con espacios colapsados. La idea es que
	`AUXILIAR DE PRODUCCION`, `AUXILIAR DE PRODUCCION - I` y
	`AUXILIAR DE PRODUCCIÓN  -  III` queden todos en `auxiliar de produccion`
	y empaten al mismo Cargo canónico.
	"""
	import unicodedata

	if not text:
		return ""
	t = str(text).strip()
	# Quitar romanos / numeritos al final.
	t = _CARGO_SUFFIX_RE.sub("", t).strip()
	# Tildes off + lowercase + colapsar espacios.
	t = unicodedata.normalize("NFKD", t)
	t = "".join(c for c in t if not unicodedata.combining(c))
	t = " ".join(t.lower().split())
	return t


def build_runtime_context() -> EnrichmentContext:
	"""Construye un `EnrichmentContext` que consulta a Frappe y al
	DocType Single de parámetros globales.
	"""
	import frappe

	# Resolver de cargo cacheado para el run completo: el archivo trae el
	# mismo string de cargo cientos de veces; resolverlo una sola vez por
	# valor único.
	_cargo_cache: dict[str, CargoSalary | None] = {}

	# Mapa canónico construido al primer lookup: { canonical_nombre: row }.
	_canonical_index: dict[str, dict] | None = None

	def _build_canonical_index() -> dict[str, dict]:
		all_cargos = frappe.get_all(
			"Cargo",
			filters={"activo": 1},
			fields=[
				"name", "nombre", "salario_base_tc", "horas_trabajadas_mes",
				"aplica_horas_extras", "tipo_cargo",
			],
			limit_page_length=0,
		)
		idx: dict[str, dict] = {}
		for row in all_cargos:
			# Si dos cargos canonicalizan igual, gana el primero con
			# salario_base_tc > 0; sino el primero a secas.
			canon = canonicalize_cargo(row.get("nombre")) or canonicalize_cargo(row.get("name"))
			if not canon:
				continue
			existing = idx.get(canon)
			if existing is None or (
				not (existing.get("salario_base_tc") or 0) and (row.get("salario_base_tc") or 0)
			):
				idx[canon] = row
		return idx

	def _resolve_cargo(cargo_label: str) -> CargoSalary | None:
		nonlocal _canonical_index
		if not cargo_label:
			return None
		key = cargo_label.strip()
		if key in _cargo_cache:
			return _cargo_cache[key]

		# 1) Match exacto por name o nombre (rápido, sin construir índice).
		_fields = ["name", "salario_base_tc", "horas_trabajadas_mes", "aplica_horas_extras", "tipo_cargo"]
		row = frappe.db.get_value(
			"Cargo",
			{"name": key, "activo": 1},
			_fields,
			as_dict=True,
		) or frappe.db.get_value(
			"Cargo",
			{"nombre": key, "activo": 1},
			_fields,
			as_dict=True,
		)

		# 2) Match canónico (strip de "- I/II/III", tildes, lowercase).
		if not row:
			if _canonical_index is None:
				_canonical_index = _build_canonical_index()
			canon = canonicalize_cargo(key)
			row = _canonical_index.get(canon)

		if not row:
			_cargo_cache[key] = None
			return None
		result = CargoSalary(
			name=row["name"],
			salario_base_tc=float(row.get("salario_base_tc") or 0),
			horas_trabajadas_mes=float(row.get("horas_trabajadas_mes") or 0),
			aplica_horas_extras=bool(row.get("aplica_horas_extras", 1)),
			tipo_cargo=str(row.get("tipo_cargo") or ""),
		)
		_cargo_cache[key] = result
		return result

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
		resolve_cargo=_resolve_cargo,
		params=params,
	)
