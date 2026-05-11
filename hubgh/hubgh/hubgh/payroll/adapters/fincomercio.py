"""Adapter Fincomercio — descuentos de fondo de empleados.

El reporte trae dos hojas:
  - "Descuentos Nomina Detalle": una fila por crédito / aporte / convenio
    por empleado (puede haber varias filas por empleado, más una fila
    TOTAL al final de cada bloque).
  - "Descuentos Nomina Agrupado": resumen por empleado y concepto.

Usamos las dos hojas:
  1. La hoja `Agrupado` da el total por empleado por categoría
     (Afiliación, Aportes / Depositos, Créditos, …). Sumamos todos los
     conceptos para emitir UNA novedad LIBRANZA_FINCOMERCIO con el total.
  2. Si no existe Agrupado, caemos a la fila "TOTAL" del Detalle.

Las cabeceras reales están en la fila 7 (filas 1-6 traen metadata:
PAGADURIA, FECHA DE CORTE, PERIODO, REPORTE No).
"""

from __future__ import annotations

import re
from typing import Iterator

from hubgh.hubgh.payroll.adapters import NovedadCanonica


SOURCE_ID = "fincomercio"
HEADER_ROW = 7
HEADER_ROW_CONCILIACION = 4
_FILENAME_PATTERN = re.compile(r"fincomercio|7898_8153|conciliacionlinea", re.IGNORECASE)


def matches(file_meta) -> int:
	score = 0
	filename = (file_meta or {}).get("filename", "") or ""
	if _FILENAME_PATTERN.search(filename):
		score += 1
	sheets = (file_meta or {}).get("sheets") or []
	# Cualquiera de los dos formatos: el viejo "Descuentos Nomina ..."
	# o el nuevo "Conciliacion en linea" + "Tabla de causales".
	if any("descuentos nomina" in (s or "").lower() for s in sheets):
		score += 2
	elif any("conciliacion en linea" in (s or "").lower() for s in sheets):
		score += 2
	return score


def detect_period(workbook) -> tuple[int, int] | None:
	"""Lee la celda 'PERIODO: dd/mm/yyyy' en la fila 5 de cualquier hoja."""
	for sheet_name in workbook.sheetnames:
		ws = workbook[sheet_name]
		for row in ws.iter_rows(min_row=1, max_row=6, values_only=True):
			for cell in row:
				if not cell:
					continue
				txt = str(cell).strip()
				m = re.match(r"PERIODO:\s*(\d{1,2})/(\d{1,2})/(\d{4})", txt, re.IGNORECASE)
				if m:
					return int(m.group(3)), int(m.group(2))
	return None


def parse(workbook) -> Iterator[NovedadCanonica]:
	# Formato nuevo "Conciliacion en linea" (apareció en abril 2026):
	if "Conciliacion en linea" in workbook.sheetnames:
		yield from _parse_conciliacion(workbook)
		return
	# Formato viejo "Descuentos Nomina ...":
	if "Descuentos Nomina Agrupado" in workbook.sheetnames:
		yield from _parse_agrupado(workbook)
		return
	if "Descuentos Nomina Detalle" in workbook.sheetnames:
		yield from _parse_detalle(workbook)


def _parse_conciliacion(workbook) -> Iterator[NovedadCanonica]:
	"""Formato `conciliacionLinea.xlsx`:
	  R4 headers: ('', Identificación, Apellidos, Nombres, Valor novedad,
	              Valor descontado, Código Causal, ...)
	  R5+ datos. Usamos `Valor descontado` (el monto que efectivamente
	  se descuenta de nómina, normalmente igual al `Valor novedad`).
	"""
	ws = workbook["Conciliacion en linea"]
	header = _row(ws, HEADER_ROW_CONCILIACION)
	if not header:
		return
	idx = {(str(h).strip().lower() if h else ""): i for i, h in enumerate(header)}
	doc_idx = idx.get("identificación") or idx.get("identificacion")
	apellidos_idx = idx.get("apellidos")
	nombres_idx = idx.get("nombres")
	valor_idx = idx.get("valor descontado")
	if valor_idx is None:
		valor_idx = idx.get("valor novedad")
	causal_idx = idx.get("código causal") or idx.get("codigo causal")
	if doc_idx is None or valor_idx is None:
		return

	for row in ws.iter_rows(min_row=HEADER_ROW_CONCILIACION + 1, values_only=True):
		doc = _str_id(row[doc_idx] if doc_idx < len(row) else None)
		if not doc:
			continue
		try:
			valor = float(row[valor_idx] or 0)
		except (TypeError, ValueError):
			continue
		if valor <= 0:
			continue
		empleado_nombre = " ".join(
			str(row[i]).strip()
			for i in (apellidos_idx, nombres_idx)
			if i is not None and row[i]
		).strip()
		yield NovedadCanonica(
			documento_identidad=doc,
			tipo_novedad="LIBRANZA_FINCOMERCIO",
			valor=round(valor, 2),
			unidad="cop",
			raw_payload={
				"empleado_nombre": empleado_nombre,
				"causal": str(row[causal_idx]).strip()
				if causal_idx is not None and row[causal_idx]
				else "",
				"sheet": "Conciliacion en linea",
			},
		)


def _row(ws, n: int):
	rows = ws.iter_rows(min_row=n, max_row=n, values_only=True)
	return next(rows, None)


def _parse_agrupado(workbook) -> Iterator[NovedadCanonica]:
	ws = workbook["Descuentos Nomina Agrupado"]
	headers = _header(ws)
	doc_idx = _find(headers, ("identificacion", "número de identificación", "numero de identificacion"))
	concepto_idx = _find(headers, ("nombre concepto",))
	valor_idx = _find(headers, ("valor de descuento", "valor"))
	if doc_idx is None or valor_idx is None:
		return

	# Sumar por empleado todos los conceptos NO-TOTAL.
	totals: dict[str, float] = {}
	names: dict[str, str] = {}
	apellidos_idx = _find(headers, ("apellidos",))
	nombres_idx = _find(headers, ("nombres",))
	for row in ws.iter_rows(min_row=HEADER_ROW + 1, values_only=True):
		doc = _str_id(row[doc_idx] if doc_idx < len(row) else None)
		if not doc:
			continue
		concepto = (
			str(row[concepto_idx]).strip()
			if concepto_idx is not None and row[concepto_idx]
			else ""
		)
		# Las filas TOTAL ya consolidadas las ignoramos para no doblar.
		if concepto.upper() == "TOTAL":
			continue
		try:
			valor = float(row[valor_idx] or 0)
		except (TypeError, ValueError):
			continue
		if valor <= 0:
			continue
		totals[doc] = totals.get(doc, 0.0) + valor
		if doc not in names:
			names[doc] = _join_name(
				row[nombres_idx] if nombres_idx is not None else None,
				row[apellidos_idx] if apellidos_idx is not None else None,
			)

	for doc, total in totals.items():
		yield NovedadCanonica(
			documento_identidad=doc,
			tipo_novedad="LIBRANZA_FINCOMERCIO",
			valor=round(total, 2),
			unidad="cop",
			raw_payload={"empleado_nombre": names.get(doc, ""), "sheet": "Descuentos Nomina Agrupado"},
		)


def _parse_detalle(workbook) -> Iterator[NovedadCanonica]:
	ws = workbook["Descuentos Nomina Detalle"]
	headers = _header(ws)
	doc_idx = _find(headers, ("número de identificación", "numero de identificacion", "identificacion"))
	valor_idx = _find(headers, ("valor",))
	concepto_idx = _find(headers, ("nombre línea", "nombre linea"))
	if doc_idx is None or valor_idx is None:
		return
	for row in ws.iter_rows(min_row=HEADER_ROW + 1, values_only=True):
		doc = _str_id(row[doc_idx] if doc_idx < len(row) else None)
		if not doc:
			continue
		concepto = (
			str(row[concepto_idx]).strip()
			if concepto_idx is not None and row[concepto_idx]
			else ""
		)
		if concepto.upper() == "TOTAL":
			continue
		try:
			valor = float(row[valor_idx] or 0)
		except (TypeError, ValueError):
			continue
		if valor <= 0:
			continue
		yield NovedadCanonica(
			documento_identidad=doc,
			tipo_novedad="LIBRANZA_FINCOMERCIO",
			valor=valor,
			unidad="cop",
			raw_payload={"concepto_fincomercio": concepto, "sheet": "Descuentos Nomina Detalle"},
		)


def _header(ws) -> list[str]:
	row = next(ws.iter_rows(min_row=HEADER_ROW, max_row=HEADER_ROW, values_only=True), None)
	return [str(h).strip() if h else "" for h in (row or [])]


def _find(headers: list[str], aliases: tuple[str, ...]) -> int | None:
	low = [h.lower() for h in headers]
	for alias in aliases:
		if alias.lower() in low:
			return low.index(alias.lower())
	return None


def _str_id(value) -> str:
	if value is None:
		return ""
	if isinstance(value, float) and value.is_integer():
		return str(int(value))
	return str(value).strip()


def _join_name(*parts) -> str:
	return " ".join(str(p).strip() for p in parts if p).strip()
