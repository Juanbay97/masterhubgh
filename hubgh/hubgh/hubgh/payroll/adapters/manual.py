"""Adapter `manual_internal` — plantillas xlsx llenadas a mano por el operador.

Cuando los datos llegan en imagen / papel / PDF, el operador descarga
una plantilla desde el workspace, la llena y la sube como un archivo
más del Run. Este adapter:

- Reconoce el archivo por la firma de hojas (el sheet_title de la
  plantilla) usando `manual_templates.identify_template_from_sheet`.
- Parsea las filas válidas según el template_id (descuentos, pérdida
  bonificación, ascensos, movimientos).
- Emite NovedadCanonica solo para los conceptos con impacto en payroll
  (descuentos, pérdida bonif). Ascensos y movimientos quedan como
  informativos en raw_payload — los procesa otro flujo aparte.

Esta variante reemplaza el stub anterior que devolvía vacío.
"""

from __future__ import annotations

from typing import Iterator

from hubgh.hubgh.payroll.adapters import NovedadCanonica
from hubgh.hubgh.payroll.manual_templates import identify_template_from_sheet


SOURCE_ID = "manual_internal"

# Tipos canónicos que el adapter sabe emitir desde la columna "Tipo de
# descuento" del template de descuentos.
_DESCUENTO_ALIAS_TO_CANONICAL = {
	"DESCUENTO_GAFAS": "DESCUENTO_GAFAS",
	"DESCUENTO_SANITAS_PREMIUM": "DESCUENTO_SANITAS_PREMIUM",
	"PRESTAMO_EMPRESA": "PRESTAMO_EMPRESA",
	"PRESTAMO_FONGIGA": "PRESTAMO_FONGIGA",
	"DOTACION": "OTRO",   # no hay tipo canónico DOTACION → cae a OTRO con valor literal
	"OTRO_DESCUENTO": "OTRO",
}


def matches(file_meta) -> int:
	"""Score 0..3 si alguna hoja del archivo matchea un template manual."""
	sheets = (file_meta or {}).get("sheets") or []
	if any(identify_template_from_sheet(s) for s in sheets):
		return 3
	return 0


def detect_period(workbook) -> tuple[int, int] | None:
	"""Las plantillas manuales no traen periodo: lo decide el Run."""
	return None


def parse(workbook) -> Iterator[NovedadCanonica]:
	"""Itera todas las hojas y delega al parser de cada template."""
	for sheet_title in workbook.sheetnames:
		template_id = identify_template_from_sheet(sheet_title)
		if not template_id:
			continue
		ws = workbook[sheet_title]
		if template_id == "descuentos":
			yield from _parse_descuentos(ws)
		elif template_id == "perdida_bonificacion":
			yield from _parse_perdida_bonificacion(ws)
		# `ascensos` y `movimientos` se omiten en v1 — son informativos
		# y los procesa otro flujo (actualización de Contrato / PDV).


def _parse_descuentos(ws) -> Iterator[NovedadCanonica]:
	"""Headers en R2: Cédula | Nombre | Tipo | Valor | Motivo."""
	for row in ws.iter_rows(min_row=3, values_only=True):
		documento = _str_id(row[0] if len(row) > 0 else None)
		if not documento:
			continue
		nombre = str(row[1]).strip() if len(row) > 1 and row[1] else ""
		tipo_raw = str(row[2]).strip().upper() if len(row) > 2 and row[2] else ""
		try:
			valor = float(row[3] or 0) if len(row) > 3 else 0
		except (TypeError, ValueError):
			continue
		motivo = str(row[4]).strip() if len(row) > 4 and row[4] else ""
		if valor <= 0:
			continue
		tipo_canonical = _DESCUENTO_ALIAS_TO_CANONICAL.get(tipo_raw, "OTRO")
		yield NovedadCanonica(
			documento_identidad=documento,
			tipo_novedad=tipo_canonical,
			valor=valor,
			unidad="cop",
			raw_payload={
				"empleado_nombre": nombre,
				"motivo": motivo,
				"tipo_manual": tipo_raw,
				"sheet": "manual:descuentos",
			},
		)


def _parse_perdida_bonificacion(ws) -> Iterator[NovedadCanonica]:
	"""Headers en R2: Cédula | Nombre | Valor | Motivo."""
	for row in ws.iter_rows(min_row=3, values_only=True):
		documento = _str_id(row[0] if len(row) > 0 else None)
		if not documento:
			continue
		nombre = str(row[1]).strip() if len(row) > 1 and row[1] else ""
		try:
			valor = float(row[2] or 0) if len(row) > 2 else 0
		except (TypeError, ValueError):
			continue
		motivo = str(row[3]).strip() if len(row) > 3 and row[3] else ""
		if valor <= 0:
			continue
		yield NovedadCanonica(
			documento_identidad=documento,
			tipo_novedad="PERDIDA_BONIFICACION",
			valor=valor,
			unidad="cop",
			raw_payload={
				"empleado_nombre": nombre,
				"motivo": motivo,
				"sheet": "manual:perdida_bonificacion",
			},
		)


def _str_id(value) -> str:
	if value is None:
		return ""
	if isinstance(value, float) and value.is_integer():
		return str(int(value))
	if isinstance(value, int):
		return str(value)
	return str(value).strip()
