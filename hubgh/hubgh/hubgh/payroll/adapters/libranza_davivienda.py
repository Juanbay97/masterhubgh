"""Adapter Libranza Davivienda.

Reporte mensual del banco con dos hojas:
  - "Hoja 1": detalle del descuento por empleado. Cabecera empresa en
    R2-R9 (logo/email/forma de pago) y headers reales en R12.
    Headers: idx | Cedula | Empleado | Tipo Producto | No Crédito |
             Vr Cuota | Vr Cuota más 4x1000 | Plazo | Fecha Desembolso |
             Vr. Desembolso | Saldos
    A partir de R13 cada fila es una cuota a descontar. Las últimas
    filas son subtotales ("Sub Total:", "4 x 1000:", "Total:") y se
    ignoran porque no tienen cédula.
  - "Formato Novedades": plantilla en blanco para reportar retiros del
    convenio — no la procesamos en v1.

Usamos `Vr Cuota más 4x1000` como valor a descontar (es el monto real
que el cliente paga, incluye el 4x1000 que cobra el banco).
"""

from __future__ import annotations

import re
from typing import Iterator

from hubgh.hubgh.payroll.adapters import NovedadCanonica


SOURCE_ID = "libranza_davivienda"
HEADER_ROW = 12
_FILENAME_PATTERN = re.compile(r"davivienda|09191", re.IGNORECASE)


def matches(file_meta) -> int:
	score = 0
	filename = (file_meta or {}).get("filename", "") or ""
	if _FILENAME_PATTERN.search(filename):
		score += 1
	sheets = (file_meta or {}).get("sheets") or []
	if any("formato novedades" in (s or "").lower() for s in sheets):
		score += 2
	return score


def detect_period(workbook) -> tuple[int, int] | None:
	"""Lee 'Fecha de Pago Mayo 05 de 2026' o similar de la hoja 1."""
	if "Hoja 1" not in workbook.sheetnames:
		return None
	ws = workbook["Hoja 1"]
	# Buscar la celda con "Fecha de Pago"
	for row in ws.iter_rows(min_row=1, max_row=10, values_only=True):
		for cell in row:
			if not cell:
				continue
			text = str(cell)
			m = re.search(
				r"(enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre)\D+(\d{4})",
				text,
				re.IGNORECASE,
			)
			if m:
				month_name = m.group(1).lower()
				meses = {
					"enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
					"mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
					"septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
				}
				return int(m.group(2)), meses.get(month_name, 0)
	return None


def parse(workbook) -> Iterator[NovedadCanonica]:
	if "Hoja 1" not in workbook.sheetnames:
		return
	ws = workbook["Hoja 1"]
	header = _row(ws, HEADER_ROW)
	if not header:
		return
	idx = {(str(h).strip().lower() if h else ""): i for i, h in enumerate(header)}

	def col(*aliases):
		for a in aliases:
			if a in idx:
				return idx[a]
		return None

	doc_idx = col("cedula", "cédula", "identificacion", "identificación")
	nombre_idx = col("empleado", "nombre del empleado")
	# Preferimos "vr cuota más 4x1000" (monto real). Fallback a "vr cuota".
	valor_idx = col("vr cuota más 4x1000", "vr cuota mas 4x1000", "valor a aplicar", "vr cuota")
	credito_idx = col("no crédito o cuenta afc", "no credito o cuenta afc", "no del crédito", "no del credito")
	if doc_idx is None or valor_idx is None:
		return

	for row in ws.iter_rows(min_row=HEADER_ROW + 1, values_only=True):
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
			tipo_novedad="LIBRANZA_DAVIVIENDA",
			valor=round(valor, 2),
			unidad="cop",
			raw_payload={
				"empleado_nombre": str(row[nombre_idx]).strip()
				if nombre_idx is not None and row[nombre_idx]
				else "",
				"credito": str(row[credito_idx]).strip()
				if credito_idx is not None and row[credito_idx]
				else "",
				"sheet": "Hoja 1",
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
