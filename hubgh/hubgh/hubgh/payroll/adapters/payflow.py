"""Adapter Payflow — adelantos de nómina.

El archivo trae dos hojas con cabeceras vacías arriba:
  - "Payflow - Resumen": una fila por empleado con el total a deducir.
  - "Payflow - Detalles": una fila por transacción.

Usamos `Resumen` como fuente de verdad: una `NovedadCanonica` por
empleado, tipo ADELANTO_NOMINA_PAYFLOW, valor literal del archivo.

Filename pattern: `CO-RD-...` (los reportes Payflow al cliente arrancan
con ese prefijo). Sheets contienen "Payflow" en el nombre.
"""

from __future__ import annotations

import re
from typing import Iterator

from hubgh.hubgh.payroll.adapters import NovedadCanonica


SOURCE_ID = "payflow"
HEADER_ROW = 4  # Cabecera real está en la fila 4 (1-based).
_FILENAME_PATTERN = re.compile(r"co-rd|payflow", re.IGNORECASE)


def matches(file_meta) -> int:
	score = 0
	filename = (file_meta or {}).get("filename", "") or ""
	if _FILENAME_PATTERN.search(filename):
		score += 1
	sheets = set((file_meta or {}).get("sheets") or [])
	if any("payflow" in s.lower() for s in sheets):
		score += 2
	return score


def detect_period(workbook) -> tuple[int, int] | None:
	"""Lee la primera Fecha de la hoja Detalles y devuelve (year, month)."""
	if "Payflow - Detalles" not in workbook.sheetnames:
		return None
	ws = workbook["Payflow - Detalles"]
	header_idx = _resolve_header(ws)
	col_fecha = header_idx.get("Fecha")
	if col_fecha is None:
		return None
	from hubgh.hubgh.payroll.adapters.clonk import _coerce_date

	for row in ws.iter_rows(min_row=HEADER_ROW + 1, values_only=True):
		dt = _coerce_date(row[col_fecha] if col_fecha < len(row) else None)
		if dt:
			return dt.year, dt.month
	return None


def parse(workbook) -> Iterator[NovedadCanonica]:
	if "Payflow - Resumen" not in workbook.sheetnames:
		return
	ws = workbook["Payflow - Resumen"]
	header_idx = _resolve_header(ws)
	cedula_idx = header_idx.get("Cedula") or header_idx.get("Cédula")
	importe_idx = next(
		(idx for label, idx in header_idx.items() if label.lower().startswith("importe")),
		None,
	)
	nombre_idx = header_idx.get("Nombre")
	apellidos_idx = header_idx.get("Apellidos")
	if cedula_idx is None or importe_idx is None:
		return

	for row in ws.iter_rows(min_row=HEADER_ROW + 1, values_only=True):
		cedula = _str_id(row[cedula_idx] if cedula_idx < len(row) else None)
		if not cedula:
			continue
		valor = row[importe_idx] if importe_idx < len(row) else None
		try:
			amount = float(valor or 0)
		except (TypeError, ValueError):
			continue
		if amount <= 0:
			continue
		yield NovedadCanonica(
			documento_identidad=cedula,
			tipo_novedad="ADELANTO_NOMINA_PAYFLOW",
			valor=amount,
			unidad="cop",
			raw_payload={
				"empleado_nombre": _join_name(
					row[nombre_idx] if nombre_idx is not None else None,
					row[apellidos_idx] if apellidos_idx is not None else None,
				),
				"sheet": "Payflow - Resumen",
			},
		)


def _resolve_header(ws) -> dict[str, int]:
	headers = next(
		ws.iter_rows(min_row=HEADER_ROW, max_row=HEADER_ROW, values_only=True),
		None,
	)
	if not headers:
		return {}
	return {str(h).strip(): i for i, h in enumerate(headers) if h}


def _str_id(value) -> str:
	if value is None:
		return ""
	if isinstance(value, float) and value.is_integer():
		return str(int(value))
	return str(value).strip()


def _join_name(*parts) -> str:
	return " ".join(str(p).strip() for p in parts if p).strip()
