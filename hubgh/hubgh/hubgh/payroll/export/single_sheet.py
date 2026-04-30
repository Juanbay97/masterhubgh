"""Excel single-sheet aplanado por empleado.

Layout de columnas (en orden):

  Identificación
    Cédula | Nombres | Apellidos | Jornada | Salario

  Horas (cantidades)
    HD h | HN h | HFD h | HFN h | HED h | HEN h | HEFD h | HEFN h

  Importes de horas
    $ HD | $ HN | $ HFD | $ HFN | $ HED | $ HEN | $ HEFD | $ HEFN

  Beneficios remunerados (días + importe agregado)
    Vacaciones d | Descanso d | Día Familia d | Día Cumple d |
    L. Maternidad d | L. Remunerada d | L. Luto d | Permiso Calamidad d

  Ausentismos no pagados (días)
    L. No Remunerada d | Suspensión d | Ausencia Injust d

  Incapacidades (días)
    Incap. EG d | Incap. AT d | Incap. Empresa d | Incap. >180 d

  Otros pagos
    Inducción $ | Auxilio Movilización $ | Auxilio Rodamiento $ |
    Bonificación CP $ | Auxilio Transporte $

  Descuentos
    Adelanto Payflow $ | Sanitas $ | Gafas $ | FONGIGA Fondo $ |
    Libranza Comfenalco $ | Libranza Fincomercio $ |
    Libranza Davivienda $ | Libranza Compensar $ |
    Préstamo Empresa $ | Préstamo FONGIGA $ | Pérdida Bonif. $

  Totales
    Total Devengado | Total Descontado | Neto a Pagar
"""

from __future__ import annotations

import io
from collections import defaultdict
from typing import Iterable

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from hubgh.hubgh.payroll.compute import auxilio_transporte


# Definición declarativa de columnas: cada tupla
# (header, fuente, agregación, tipo_novedad_id)
# - fuente: "id" | "h_qty" | "h_amt" | "d_qty" | "d_amt" | "amt" | "auxilio_t"
# - agregación: "sum" | "first"
COLUMN_SPEC: list[tuple[str, str, str]] = [
	# Identificación (no calculadas, vienen del primer registro del empleado)
	("Cédula", "id_cedula", "first"),
	("Nombres", "id_nombres", "first"),
	("Apellidos", "id_apellidos", "first"),
	("Jornada", "id_jornada", "first"),
	("Salario", "id_salario", "first"),
	# Horas (cantidad)
	("HD h", "h_qty:HD", "sum"),
	("HN h", "h_qty:HN", "sum"),
	("HFD h", "h_qty:HFD", "sum"),
	("HFN h", "h_qty:HFN", "sum"),
	("HED h", "h_qty:HED", "sum"),
	("HEN h", "h_qty:HEN", "sum"),
	("HEFD h", "h_qty:HEFD", "sum"),
	("HEFN h", "h_qty:HEFN", "sum"),
	# Horas (importe)
	("$ HD", "h_amt:HD", "sum"),
	("$ HN", "h_amt:HN", "sum"),
	("$ HFD", "h_amt:HFD", "sum"),
	("$ HFN", "h_amt:HFN", "sum"),
	("$ HED", "h_amt:HED", "sum"),
	("$ HEN", "h_amt:HEN", "sum"),
	("$ HEFD", "h_amt:HEFD", "sum"),
	("$ HEFN", "h_amt:HEFN", "sum"),
	# Beneficios remunerados (días)
	("Vacaciones d", "d_qty:VACACIONES", "sum"),
	("Descanso d", "d_qty:DESCANSO", "sum"),
	("Día Familia d", "d_qty:DIA_FAMILIA", "sum"),
	("Día Cumple d", "d_qty:DIA_CUMPLEANOS", "sum"),
	("L. Maternidad d", "d_qty:LICENCIA_MATERNIDAD", "sum"),
	("L. Remunerada d", "d_qty:LICENCIA_REMUNERADA", "sum"),
	("L. Luto d", "d_qty:LICENCIA_LUTO", "sum"),
	("Permiso Calamidad d", "d_qty:PERMISO_CALAMIDAD", "sum"),
	# Beneficios remunerados (importe agregado)
	("Beneficios remunerados $", "d_amt_remunerados", "sum"),
	# Ausentismos no pagados (días)
	("L. No Remunerada d", "d_qty:LICENCIA_NO_REMUNERADA", "sum"),
	("Suspensión d", "d_qty:SUSPENSION_CONTRATO", "sum"),
	("Ausencia Injust d", "d_qty:AUSENCIA_INJUSTIFICADA", "sum"),
	("Ausencias descuento $", "d_amt_no_remunerados", "sum"),
	# Incapacidades
	("Incap. EG d", "d_qty:INCAPACIDAD_ENFERMEDAD_GENERAL", "sum"),
	("Incap. AT d", "d_qty:INCAPACIDAD_ACCIDENTE_TRABAJO", "sum"),
	("Incap. Empresa d", "d_qty:INCAPACIDAD_PAGADA_EMPRESA", "sum"),
	("Incap. >180 d", "d_qty:INCAPACIDAD_MAYOR_180_DIAS", "sum"),
	("Incapacidades $", "d_amt_incapacidades", "sum"),
	# Otros pagos
	("Inducción $", "amt:INDUCCION", "sum"),
	("Auxilio Movilización $", "amt:AUXILIO_MOVILIZACION_DOM_FEST", "sum"),
	("Auxilio Rodamiento $", "amt:AUXILIO_RODAMIENTO", "sum"),
	("Bonificación CP $", "amt:BONIFICACION_CP", "sum"),
	("Auxilio Transporte $", "auxilio_t", "first"),
	# Descuentos
	("Adelanto Payflow $", "amt:ADELANTO_NOMINA_PAYFLOW", "sum"),
	("Sanitas $", "amt:DESCUENTO_SANITAS_PREMIUM", "sum"),
	("Gafas $", "amt:DESCUENTO_GAFAS", "sum"),
	("FONGIGA Fondo $", "amt:FONDO_EMPLEADOS_FONGIGA", "sum"),
	("Libranza Comfenalco $", "amt:LIBRANZA_COMFENALCO", "sum"),
	("Libranza Fincomercio $", "amt:LIBRANZA_FINCOMERCIO", "sum"),
	("Libranza Davivienda $", "amt:LIBRANZA_DAVIVIENDA", "sum"),
	("Libranza Compensar $", "amt:LIBRANZA_COMPENSAR", "sum"),
	("Préstamo Empresa $", "amt:PRESTAMO_EMPRESA", "sum"),
	("Préstamo FONGIGA $", "amt:PRESTAMO_FONGIGA", "sum"),
	("Pérdida Bonif. $", "amt:PERDIDA_BONIFICACION", "sum"),
	# Totales
	("Total Devengado", "total_devengado", "sum"),
	("Total Descontado", "total_descontado", "sum"),
	("Neto a Pagar", "neto", "sum"),
]


REMUNERADOS_DIAS = (
	"VACACIONES", "DESCANSO", "DIA_FAMILIA", "DIA_CUMPLEANOS",
	"LICENCIA_MATERNIDAD", "LICENCIA_REMUNERADA", "LICENCIA_LUTO",
	"PERMISO_CALAMIDAD",
)
NO_REMUNERADOS_DIAS = (
	"LICENCIA_NO_REMUNERADA", "SUSPENSION_CONTRATO", "AUSENCIA_INJUSTIFICADA",
)
INCAPACIDADES = (
	"INCAPACIDAD_ENFERMEDAD_GENERAL", "INCAPACIDAD_ACCIDENTE_TRABAJO",
	"INCAPACIDAD_PAGADA_EMPRESA", "INCAPACIDAD_MAYOR_180_DIAS",
)


def build_single_sheet(
	novedades: Iterable,
	params,
	employees_meta: dict[str, dict] | None = None,
	period_label: str = "",
) -> bytes:
	"""Devuelve el .xlsx en memoria (bytes).

	`novedades` es un iterable de objetos con los atributos de
	`EnrichedNovedad` (computed_amount/quantity ya seteados).
	`employees_meta` es un dict opcional `empleado_name -> {"nombres":..., "apellidos":..., "cedula":...}`
	para enriquecer las filas. Si falta, se usa el `documento_identidad`.
	"""
	by_employee = _aggregate(novedades, employees_meta or {})
	wb = Workbook()
	ws = wb.active
	ws.title = "Prenómina"

	# Header
	headers = [spec[0] for spec in COLUMN_SPEC]
	ws.append(headers)
	header_fill = PatternFill("solid", fgColor="305496")
	header_font = Font(bold=True, color="FFFFFF")
	for cell in ws[1]:
		cell.fill = header_fill
		cell.font = header_font
		cell.alignment = Alignment(horizontal="center", wrap_text=True)
	ws.row_dimensions[1].height = 32

	# Filas
	for emp_id in sorted(by_employee.keys()):
		row_data = by_employee[emp_id]
		row = []
		for header, source, _agg in COLUMN_SPEC:
			row.append(_resolve_value(row_data, source, params))
		ws.append(row)

	# Totales fila final
	total_row_idx = ws.max_row + 1
	ws.cell(row=total_row_idx, column=1, value="TOTAL")
	for col_idx, (_h, source, agg) in enumerate(COLUMN_SPEC, start=1):
		if agg != "sum" or source.startswith("id_") or source == "auxilio_t":
			continue
		col_letter = get_column_letter(col_idx)
		ws.cell(
			row=total_row_idx,
			column=col_idx,
			value=f"=SUM({col_letter}2:{col_letter}{total_row_idx - 1})",
		)
	for cell in ws[total_row_idx]:
		cell.font = Font(bold=True)
		cell.fill = PatternFill("solid", fgColor="D9E1F2")

	# Formato de columnas $: anchos y formato moneda
	for col_idx, (header, _src, _agg) in enumerate(COLUMN_SPEC, start=1):
		ws.column_dimensions[get_column_letter(col_idx)].width = max(
			14, min(28, len(header) + 2)
		)
		if "$" in header or "Devengado" in header or "Descontado" in header or "Neto" in header:
			for row_idx in range(2, ws.max_row + 1):
				ws.cell(row=row_idx, column=col_idx).number_format = '"$"#,##0.00'
		elif " h" in header or " d" in header:
			for row_idx in range(2, ws.max_row + 1):
				ws.cell(row=row_idx, column=col_idx).number_format = "0.00"

	if period_label:
		ws.title = f"Prenómina {period_label}"[:31]

	buf = io.BytesIO()
	wb.save(buf)
	return buf.getvalue()


# ──────────────────────────────────────────────────────────────────────
# Agregación por empleado
# ──────────────────────────────────────────────────────────────────────

def _aggregate(novedades: Iterable, employees_meta: dict[str, dict]) -> dict[str, dict]:
	by_emp: dict[str, dict] = defaultdict(lambda: _empty_emp_record())
	for nov in novedades:
		key = nov.empleado or nov.documento_identidad or "SIN_EMPLEADO"
		rec = by_emp[key]
		# Identidad (first)
		if not rec["id_set"]:
			meta = employees_meta.get(key, {})
			rec["id_cedula"] = meta.get("cedula") or nov.documento_identidad or ""
			rec["id_nombres"] = meta.get("nombres") or nov.raw_payload.get("empleado_nombre") or ""
			rec["id_apellidos"] = meta.get("apellidos") or ""
			rec["id_jornada"] = nov.tipo_jornada_snapshot or ""
			rec["id_salario"] = float(nov.salario_mensual or 0.0)
			rec["id_set"] = True
		# Cantidades por tipo
		tipo = nov.tipo_novedad
		amount = float(nov.computed_amount or 0.0)
		qty = float(nov.computed_quantity or nov.cantidad or 0.0)
		if nov.unidad == "horas":
			rec["h_qty"][tipo] += qty
			rec["h_amt"][tipo] += amount
		elif nov.unidad == "dias":
			rec["d_qty"][tipo] += qty
			rec["d_amt"][tipo] += amount
		else:
			# cop / unidades
			rec["amt"][tipo] += amount
		# Totales por categoría agregada
		if tipo in REMUNERADOS_DIAS or tipo in INCAPACIDADES:
			rec["total_devengado"] += amount
		elif tipo in NO_REMUNERADOS_DIAS:
			rec["total_descontado"] += amount  # ausencia_injustificada ya negativo
		else:
			# horas, induccion, auxilios, bonificaciones suman al devengado.
			# Descuentos literales suman al descontado.
			from hubgh.hubgh.payroll.compute.literal import DESCUENTO_TYPES

			if tipo in DESCUENTO_TYPES:
				rec["total_descontado"] += amount
			else:
				rec["total_devengado"] += amount
	return dict(by_emp)


def _empty_emp_record() -> dict:
	return {
		"id_set": False,
		"id_cedula": "", "id_nombres": "", "id_apellidos": "",
		"id_jornada": "", "id_salario": 0.0,
		"h_qty": defaultdict(float), "h_amt": defaultdict(float),
		"d_qty": defaultdict(float), "d_amt": defaultdict(float),
		"amt": defaultdict(float),
		"total_devengado": 0.0,
		"total_descontado": 0.0,
	}


def _resolve_value(rec: dict, source: str, params):
	if source.startswith("id_"):
		return rec.get(source, "")
	if source == "auxilio_t":
		dias_no_rem = sum(rec["d_qty"].get(t, 0.0) for t in NO_REMUNERADOS_DIAS)
		return auxilio_transporte.compute_for_period(
			rec.get("id_salario", 0.0), params, dias_no_remunerados=dias_no_rem
		)
	if source.startswith("h_qty:"):
		return rec["h_qty"].get(source.split(":", 1)[1], 0.0)
	if source.startswith("h_amt:"):
		return rec["h_amt"].get(source.split(":", 1)[1], 0.0)
	if source.startswith("d_qty:"):
		return rec["d_qty"].get(source.split(":", 1)[1], 0.0)
	if source.startswith("amt:"):
		return rec["amt"].get(source.split(":", 1)[1], 0.0)
	if source == "d_amt_remunerados":
		return sum(rec["d_amt"].get(t, 0.0) for t in REMUNERADOS_DIAS)
	if source == "d_amt_no_remunerados":
		return sum(rec["d_amt"].get(t, 0.0) for t in NO_REMUNERADOS_DIAS)
	if source == "d_amt_incapacidades":
		return sum(rec["d_amt"].get(t, 0.0) for t in INCAPACIDADES)
	if source == "total_devengado":
		dias_no_rem = sum(rec["d_qty"].get(t, 0.0) for t in NO_REMUNERADOS_DIAS)
		auxilio = auxilio_transporte.compute_for_period(
			rec.get("id_salario", 0.0), params, dias_no_remunerados=dias_no_rem
		)
		return rec["total_devengado"] + auxilio
	if source == "total_descontado":
		return rec["total_descontado"]
	if source == "neto":
		dias_no_rem = sum(rec["d_qty"].get(t, 0.0) for t in NO_REMUNERADOS_DIAS)
		auxilio = auxilio_transporte.compute_for_period(
			rec.get("id_salario", 0.0), params, dias_no_remunerados=dias_no_rem
		)
		return rec["total_devengado"] + auxilio + rec["total_descontado"]
	return ""
