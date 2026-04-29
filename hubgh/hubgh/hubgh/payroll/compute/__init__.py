"""Orchestrator del cómputo de novedades.

Recibe una `EnrichedNovedad` con `calc_status='pending'` y un
`GlobalParams`, y devuelve la misma instancia mutada con
`computed_amount`, `computed_quantity`, `calc_status` y `calc_notes`
listos para persistir en `Payroll Novedad`.

El ruteo es por id de tipo:
- Recargos / horas extra → compute.recargos
- Inducción → compute.induccion
- Ausentismos / licencias / beneficios / vacaciones → compute.ausentismos
- Descuentos / pagos literales → compute.literal

Todo lo demás cae en `OTRO` y se trata como literal si trae `valor`.
"""

from __future__ import annotations

from hubgh.hubgh.payroll.compute import ausentismos, induccion, literal, recargos


def compute_novedad(novedad, params) -> None:
	"""Mutates `novedad` in place. No-op si calc_status no es 'pending'."""
	if getattr(novedad, "calc_status", "") != "pending":
		return

	tipo = novedad.tipo_novedad

	if recargos.applies(tipo):
		amount, qty, notes = recargos.compute(novedad)
	elif induccion.applies(tipo):
		amount, qty, notes = induccion.compute(novedad, params)
	elif ausentismos.applies(tipo):
		amount, qty, notes = ausentismos.compute(novedad)
	elif literal.applies(tipo):
		amount, qty, notes = literal.compute(novedad)
	elif tipo == "OTRO" and novedad.valor is not None:
		# Catch-all: si OTRO trae valor, lo tratamos como literal.
		amount, qty, notes = literal.compute(novedad) if False else (
			float(novedad.valor or 0.0),
			0.0,
			f"OTRO con valor literal ${novedad.valor}.",
		)
	else:
		novedad.computed_amount = 0.0
		novedad.computed_quantity = float(novedad.cantidad or 0.0)
		novedad.calc_status = "skipped"
		novedad.calc_notes = f"Sin módulo de cómputo para tipo '{tipo}'."
		return

	novedad.computed_amount = amount
	novedad.computed_quantity = qty
	novedad.calc_status = "computed"
	novedad.calc_notes = notes
