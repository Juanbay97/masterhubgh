"""Cálculo de inducción.

Confirmado por el dueño:
- Tiempo Completo: 1 día completo al valor día (`salario / 30`).
- Tiempo Parcial: jornada parametrizada (default 7.33 h) × hora_tp_fija.

Pago al 100%. La cantidad recibida del CLONK viene en días; se multiplica
para cubrir más de un día de inducción si el evento durase varios.
"""

from __future__ import annotations


def applies(tipo_novedad: str) -> bool:
	return tipo_novedad == "INDUCCION"


def compute(novedad, params) -> tuple[float, float, str]:
	"""Devuelve (computed_amount, computed_quantity, calc_notes)."""
	dias = float(novedad.cantidad or 0.0)
	if dias <= 0:
		return 0.0, 0.0, "Cantidad de días de inducción es 0."

	jornada = novedad.tipo_jornada_snapshot
	if jornada == "Tiempo Parcial":
		horas_jornada = float(params.jornada_induccion_tp_horas or 7.33)
		hora_tp = float(params.hora_tp_fija or 0.0)
		amount = round(dias * horas_jornada * hora_tp, 2)
		notes = (
			f"TP: {dias:.2f}d × {horas_jornada}h × ${hora_tp:.2f}/h = ${amount:.2f}"
		)
		return amount, dias, notes

	# TC (incluye TC-Admin y Aprendizaje normalizados).
	salario = float(novedad.salario_mensual or 0.0)
	if salario <= 0:
		return 0.0, dias, "TC: sin salario, no devenga."
	valor_dia = salario / 30.0
	amount = round(dias * valor_dia, 2)
	notes = f"TC: {dias:.2f}d × ${valor_dia:.2f}/d = ${amount:.2f}"
	return amount, dias, notes
