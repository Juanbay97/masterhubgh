"""Adapter Libranza Compensar.

Reporte mensual de Compensar con hoja única `EstadoCuentaCreditoDirecto`.

Layout:
  R3-R4: Identificación / Nombre empresa / Referencia / fechas / total.
  R7-R8: doble fila de header (la R7 trae "Documento", "Nombre", "Número
         de crédito", "Cuotas" agrupado, "Vr. cuota del mes", "Valor
         vencido", "Valor int. mora", "Valor inicial", "Valor a pagar".
         La R8 sub-divide la columna "Cuotas" en "Pactadas/Pagadas/
         Vencidas").
  R9+: detalle, una fila por crédito por empleado.

Usamos `Valor a pagar` (última columna) como el valor a descontar:
incluye cuota + vencido + intereses de mora.
"""

from __future__ import annotations

import re
from typing import Iterator

from hubgh.hubgh.payroll.adapters import NovedadCanonica


SOURCE_ID = "libranza_compensar"
_FILENAME_PATTERN = re.compile(r"compensar|estadocuentacredito", re.IGNORECASE)


def matches(file_meta) -> int:
	score = 0
	filename = (file_meta or {}).get("filename", "") or ""
	if _FILENAME_PATTERN.search(filename):
		score += 2
	sheets = (file_meta or {}).get("sheets") or []
	if any("estadocuentacredito" in (s or "").lower() for s in sheets):
		score += 1
	return score


def detect_period(workbook) -> tuple[int, int] | None:
	"""Lee la fecha 'Emisión' (R4 col E) para sacar el mes/año."""
	if not workbook.sheetnames:
		return None
	ws = workbook[workbook.sheetnames[0]]
	from datetime import date, datetime

	# La fila 4 suele tener la fecha de Emisión en la col E (idx 4).
	for row in ws.iter_rows(min_row=3, max_row=6, values_only=True):
		for cell in row:
			if isinstance(cell, datetime):
				return cell.year, cell.month
			if isinstance(cell, date):
				return cell.year, cell.month
	return None


def parse(workbook) -> Iterator[NovedadCanonica]:
	if not workbook.sheetnames:
		return
	ws = workbook[workbook.sheetnames[0]]
	# Header real en fila 8 (la 7 es categoría "Cuotas" pero la 8 trae
	# los nombres reales). Caemos a la 7 si la 8 no tiene los esperados.
	header = _row(ws, 8) or _row(ws, 7)
	if not header:
		return
	idx = {(str(h).strip().lower() if h else ""): i for i, h in enumerate(header)}

	def col(*aliases):
		for a in aliases:
			if a in idx:
				return idx[a]
		return None

	doc_idx = col("documento", "cedula", "cédula", "identificación", "identificacion")
	nombre_idx = col("nombre")
	valor_idx = col("valor a pagar", "vr. cuota del mes")
	credito_idx = col("número de crédito", "numero de credito", "no crédito")
	if doc_idx is None or valor_idx is None:
		return

	for row in ws.iter_rows(min_row=9, values_only=True):
		documento = _str_id(row[doc_idx] if doc_idx < len(row) else None)
		if not documento:
			continue
		try:
			valor = float(row[valor_idx] or 0)
		except (TypeError, ValueError):
			continue
		if valor <= 0:
			continue
		yield NovedadCanonica(
			documento_identidad=documento,
			tipo_novedad="LIBRANZA_COMPENSAR",
			valor=round(valor, 2),
			unidad="cop",
			raw_payload={
				"empleado_nombre": str(row[nombre_idx]).strip()
				if nombre_idx is not None and row[nombre_idx]
				else "",
				"credito": str(row[credito_idx]).strip()
				if credito_idx is not None and row[credito_idx]
				else "",
				"sheet": ws.title,
			},
		)


def _row(ws, n: int):
	rows = ws.iter_rows(min_row=n, max_row=n, values_only=True)
	return next(rows, None)


def _str_id(value) -> str:
	if value is None:
		return ""
	if isinstance(value, float) and value.is_integer():
		return str(int(value))
	if isinstance(value, int):
		return str(value)
	return str(value).strip()
