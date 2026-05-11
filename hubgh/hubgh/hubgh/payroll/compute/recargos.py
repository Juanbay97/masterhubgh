"""Cálculo de recargos y horas extra.

Para los 8 tipos H* del catálogo:
  computed_amount = cantidad × valor_hora_base × MULTIPLICADORES_HORAS[tipo]

`valor_hora_base` lo provee el enrichment según jornada (TC: salario /
horas_trabajadas_mes; TP: hora_tp_fija). Esa decisión vive ahí, acá
sólo aplicamos el multiplicador.
"""

from __future__ import annotations

from hubgh.hubgh.payroll import catalogs


HOUR_TYPES = frozenset(catalogs.MULTIPLICADORES_HORAS.keys())


def applies(tipo_novedad: str) -> bool:
	return tipo_novedad in HOUR_TYPES


def compute(novedad) -> tuple[float, float, str]:
	"""Devuelve (computed_amount, computed_quantity, calc_notes)."""
	multiplicador = catalogs.MULTIPLICADORES_HORAS.get(novedad.tipo_novedad)
	if multiplicador is None:
		return 0.0, 0.0, f"Tipo {novedad.tipo_novedad} no es un recargo de hora."
	cantidad = float(novedad.cantidad or 0.0)
	valor_hora = float(novedad.valor_hora_base or 0.0)
	if cantidad <= 0 or valor_hora <= 0:
		return 0.0, cantidad, "Cantidad o valor hora cero — no devenga."
	amount = round(cantidad * valor_hora * multiplicador, 2)
	notes = f"{cantidad:.2f}h × ${valor_hora:.2f} × {multiplicador} = ${amount:.2f}"
	return amount, round(cantidad, 4), notes
