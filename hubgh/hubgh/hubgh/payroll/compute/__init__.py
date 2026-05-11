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

from hubgh.hubgh.payroll.compute import (
	ausentismos,
	dias_remunerados,
	induccion,
	literal,
	recargos,
)


def compute_novedad(novedad, params) -> None:
	"""Mutates `novedad` in place. No-op si calc_status no es 'pending'.

	Emite `partial` (amount=0, qty=cantidad cruda) cuando faltan datos
	estructurales del empleado/contrato pero la novedad pudo registrarse
	con lo que viene del archivo (el operador la verá en la prenómina y
	el importe se podrá ajustar manualmente o re-correr cuando el
	empleado se cree).
	"""
	if getattr(novedad, "calc_status", "") != "pending":
		return

	tipo = novedad.tipo_novedad

	if recargos.applies(tipo):
		amount, qty, notes = recargos.compute(novedad)
	elif induccion.applies(tipo):
		amount, qty, notes = induccion.compute(novedad, params)
	elif dias_remunerados.applies(tipo):
		amount, qty, notes = dias_remunerados.compute(novedad, params)
	elif ausentismos.applies(tipo):
		amount, qty, notes = ausentismos.compute(novedad, params)
	elif literal.applies(tipo):
		amount, qty, notes = literal.compute(novedad)
	elif tipo == "OTRO" and novedad.valor is not None:
		amount, qty, notes = (
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
	# Si el cómputo dio amount=0 pero la novedad trae cantidad real
	# (horas/días) y NO es un caso legítimo de pago al 0% (lic no
	# remunerada / suspensión), marcamos `partial`: la cantidad quedó
	# registrada pero el importe espera datos faltantes (salario,
	# valor_hora_base) cuando se cree el empleado/contrato.
	zero_pct_types = {"LICENCIA_NO_REMUNERADA", "SUSPENSION_CONTRATO"}
	is_legit_zero = tipo in zero_pct_types
	missing_basis = (novedad.salario_mensual or 0) <= 0 and (novedad.valor_hora_base or 0) <= 0
	if amount == 0 and (novedad.cantidad or 0) > 0 and not is_legit_zero and missing_basis:
		novedad.calc_status = "partial"
		extra = ""
		if getattr(novedad, "calc_notes", ""):
			extra = " · " + novedad.calc_notes
		novedad.calc_notes = "Solo cantidad registrada; falta empleado/contrato para importe." + extra
	else:
		novedad.calc_status = "computed"
		novedad.calc_notes = notes
