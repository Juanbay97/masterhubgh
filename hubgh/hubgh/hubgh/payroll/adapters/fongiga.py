"""Adapter FONGIGA / Fondo Empleados — archivo tipo "M HOME".

Trae varias hojas (REAL11, REAL, FEB 011, ENER 011, DETALLADO HOME
BURGUERS). La que captura los descuentos del periodo activo es `REAL11`
(o `REAL` en su variante). Estructura:
  Tercero | Descripción | Descripción Concepto | Neto a pagar/Deducción

Cada fila representa un descuento; el `Descripción Concepto` indica si
es FONDO_EMPLEADOS_FONGIGA o PRESTAMO_FONGIGA. Un mismo empleado puede
aparecer dos veces (una por concepto).

Filename pattern: `M HOME ...` o `MICRO`. Sheets: `REAL11` o `DETALLADO
HOME BURGUERS`.
"""

from __future__ import annotations

import re
from typing import Iterator

from hubgh.hubgh.payroll.adapters import NovedadCanonica


SOURCE_ID = "fongiga"

CONCEPT_MAP: dict[str, str] = {
	"fondo de empleados fongiga": "FONDO_EMPLEADOS_FONGIGA",
	"fondo empleados fongiga": "FONDO_EMPLEADOS_FONGIGA",
	"fondo de empleados": "FONDO_EMPLEADOS_FONGIGA",
	"prestamo fongiga": "PRESTAMO_FONGIGA",
	"préstamo fongiga": "PRESTAMO_FONGIGA",
}

_FILENAME_PATTERN = re.compile(r"\bm\s+home\b|fongiga|micro", re.IGNORECASE)
_FONDO_SHEET_PRIORITY = ("REAL11", "REAL", "DETALLADO HOME BURGUERS")


def matches(file_meta) -> int:
	score = 0
	filename = (file_meta or {}).get("filename", "") or ""
	if _FILENAME_PATTERN.search(filename):
		score += 1
	sheets = set((file_meta or {}).get("sheets") or [])
	if any(s in sheets for s in _FONDO_SHEET_PRIORITY):
		score += 2
	return score


def detect_period(workbook) -> tuple[int, int] | None:
	"""El archivo no trae periodo en celda — lo deducimos del nombre de la
	hoja FEB/ENER/MAR/etc o devolvemos None y dejamos al Run dictarlo.
	"""
	month_aliases = {
		"ENE": 1, "ENER": 1, "FEB": 2, "MAR": 3, "ABR": 4,
		"MAY": 5, "JUN": 6, "JUL": 7, "AGO": 8, "SEP": 9,
		"OCT": 10, "NOV": 11, "DIC": 12,
	}
	for sheet in workbook.sheetnames:
		head = sheet.upper().strip().split()[0] if sheet else ""
		if head in month_aliases:
			# Sin año en el nombre: regresamos solo el mes con None,
			# el caller usará el del Run.
			return None
	return None


def parse(workbook) -> Iterator[NovedadCanonica]:
	target_sheet = next(
		(s for s in _FONDO_SHEET_PRIORITY if s in workbook.sheetnames),
		None,
	)
	if not target_sheet:
		return
	ws = workbook[target_sheet]
	headers = next(ws.iter_rows(min_row=1, max_row=1, values_only=True), None)
	if not headers:
		return
	idx_by_name = {(str(h).strip().lower() if h else ""): i for i, h in enumerate(headers)}

	def first_not_none(*aliases):
		for a in aliases:
			if a in idx_by_name:
				return idx_by_name[a]
		return None

	doc_idx = first_not_none("tercero", "cedula", "identificacion")
	nombre_idx = first_not_none("descripción", "descripcion", "nombre")
	concepto_idx = first_not_none("descripción concepto", "descripcion concepto", "descripcionconcepto")
	valor_idx = first_not_none("neto a pagar", "deducción", "deduccion", "total")
	if doc_idx is None or valor_idx is None:
		return

	for row in ws.iter_rows(min_row=2, values_only=True):
		doc = _str_id(row[doc_idx] if doc_idx < len(row) else None)
		if not doc:
			continue
		concepto_raw = (
			str(row[concepto_idx]).strip().lower()
			if concepto_idx is not None and concepto_idx < len(row) and row[concepto_idx]
			else ""
		)
		tipo = _resolve_concept(concepto_raw)
		if not tipo:
			continue
		try:
			valor = float(row[valor_idx] or 0)
		except (TypeError, ValueError):
			continue
		if valor <= 0:
			continue
		yield NovedadCanonica(
			documento_identidad=doc,
			tipo_novedad=tipo,
			valor=round(valor, 2),
			unidad="cop",
			raw_payload={
				"empleado_nombre": str(row[nombre_idx]).strip() if nombre_idx is not None and row[nombre_idx] else "",
				"concepto_fongiga": concepto_raw,
				"sheet": target_sheet,
			},
		)


def _resolve_concept(text: str) -> str | None:
	if not text:
		return None
	for key, tipo in CONCEPT_MAP.items():
		if key in text:
			return tipo
	# Último intento: si menciona "PRESTAMO" o "FONDO" sin más detalle.
	if "prestamo" in text or "préstamo" in text:
		return "PRESTAMO_FONGIGA"
	if "fondo" in text:
		return "FONDO_EMPLEADOS_FONGIGA"
	return None


def _str_id(value) -> str:
	if value is None:
		return ""
	if isinstance(value, float) and value.is_integer():
		return str(int(value))
	if isinstance(value, int):
		return str(value)
	return str(value).strip().lstrip("0") or str(value).strip()
