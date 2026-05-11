"""Días remunerados con regla de jornada (5.83 h / 2.92 h).

Aplica a DIA_FAMILIA, DIA_CUMPLEANOS y conceptos similares (día de
votación, etc.) confirmados por el dueño:

  Jornada completa (TC): 5.83 h × valor_hora_TC × días
    (jornada semanal de 35 h dividida en 6 días = 5.83 h/día).
  Media jornada (TP):    2.92 h × hora_tp_fija × días
    (la mitad de 5.83 h por la jornada parcial).

`valor_hora_TC` lo trae enrichment como `salario_mensual /
horas_trabajadas_mes` (con fallback al divisor global del DocType
`Payroll Parametros Globales`).
"""

from __future__ import annotations


HORAS_TC = 5.83
HORAS_TP = 2.92

APPLIES_TO = frozenset({"DIA_FAMILIA", "DIA_CUMPLEANOS"})


def applies(tipo_novedad: str) -> bool:
	return tipo_novedad in APPLIES_TO


def compute(novedad, params) -> tuple[float, float, str]:
	"""Devuelve (computed_amount, computed_quantity, calc_notes)."""
	dias = float(novedad.cantidad or 0.0)
	if dias <= 0:
		return 0.0, 0.0, "Cantidad de días en cero."
	jornada = novedad.tipo_jornada_snapshot or ""

	if jornada == "Tiempo Parcial":
		hora_tp = float(params.hora_tp_fija or 0.0) if params else 0.0
		if hora_tp <= 0:
			return 0.0, dias, "TP sin hora_tp_fija parametrizada."
		amount = round(dias * HORAS_TP * hora_tp, 2)
		notes = f"TP: {dias:.2f}d × {HORAS_TP}h × ${hora_tp:.2f}/h = ${amount:.2f}"
		return amount, dias, notes

	# TC: usar valor_hora_base resuelto en enrichment (salario / horas).
	valor_hora = float(novedad.valor_hora_base or 0.0)
	if valor_hora <= 0:
		# Fallback: salario / divisor global si no hay valor_hora_base.
		salario = float(novedad.salario_mensual or 0.0)
		divisor = float((params and params.divisor_hora_tc) or 240.0)
		if salario <= 0 or divisor <= 0:
			return 0.0, dias, "TC: sin valor hora ni salario, no devenga."
		valor_hora = salario / divisor
	amount = round(dias * HORAS_TC * valor_hora, 2)
	notes = f"TC: {dias:.2f}d × {HORAS_TC}h × ${valor_hora:.2f}/h = ${amount:.2f}"
	return amount, dias, notes
