"""Cálculo de recargos y horas extra.

Para los 8 tipos H* del catálogo:
  computed_amount = cantidad × valor_hora_base × MULTIPLICADORES_HORAS[tipo]

`valor_hora_base` lo provee el enrichment según jornada (TC: salario /
horas_trabajadas_mes; TP: hora_tp_fija). Esa decisión vive ahí, acá
sólo aplicamos el multiplicador.

Filtro por cargo: si `novedad.cargo_aplica_horas_extras` es False y el
tipo es una hora extra (HED/HEN/HEFD/HEFN), devolvemos 0 con nota
explícita. Los recargos por nocturno/festivo (HN/HFD/HFN) y la hora
ordinaria (HD) NO se filtran — esos los cobra cualquier cargo que los
haya trabajado.
"""

from __future__ import annotations

from hubgh.hubgh.payroll import catalogs


HOUR_TYPES = frozenset(catalogs.MULTIPLICADORES_HORAS.keys())
# Subconjunto de tipos que son "hora extra" propiamente dicha (no recargo).
EXTRA_HOUR_TYPES = frozenset({"HED", "HEN", "HEFD", "HEFN"})


def applies(tipo_novedad: str) -> bool:
	return tipo_novedad in HOUR_TYPES


def compute(novedad) -> tuple[float, float, str]:
	"""Devuelve (computed_amount, computed_quantity, calc_notes)."""
	multiplicador = catalogs.MULTIPLICADORES_HORAS.get(novedad.tipo_novedad)
	if multiplicador is None:
		return 0.0, 0.0, f"Tipo {novedad.tipo_novedad} no es un recargo de hora."

	cantidad = float(novedad.cantidad or 0.0)

	# Filtro por cargo: si el cargo no aplica horas extra, los tipos HE*
	# se descartan con nota clara. La cantidad queda registrada por
	# auditoría pero no devenga importe.
	if (
		novedad.tipo_novedad in EXTRA_HOUR_TYPES
		and getattr(novedad, "cargo_aplica_horas_extras", True) is False
	):
		return 0.0, cantidad, (
			f"Cargo no aplica horas extra; {cantidad:.2f}h de "
			f"{novedad.tipo_novedad} registradas sin importe."
		)

	valor_hora = float(novedad.valor_hora_base or 0.0)
	if cantidad <= 0 or valor_hora <= 0:
		return 0.0, cantidad, "Cantidad o valor hora cero — no devenga."
	amount = round(cantidad * valor_hora * multiplicador, 2)
	notes = f"{cantidad:.2f}h × ${valor_hora:.2f} × {multiplicador} = ${amount:.2f}"
	return amount, round(cantidad, 4), notes
