"""Auxilio de transporte automático.

NO es una novedad: el sistema lo aplica de oficio en el export.

Regla legal Colombia: el empleado recibe auxilio de transporte si su
salario base es ≤ 2 SMMLV y trabajó al menos un día en el periodo. El
valor del auxilio y el SMMLV viven en `Payroll Parametros Globales`.
"""

from __future__ import annotations


def _tope(params) -> float:
	smmlv = float(getattr(params, "salario_minimo_mensual", 0) or 0)
	return 2.0 * smmlv if smmlv > 0 else 0.0


def is_eligible(salario_mensual: float, params) -> bool:
	tope = _tope(params)
	salario = float(salario_mensual or 0)
	return tope > 0 and 0 < salario <= tope


# Periodo nominal asumido para prorrateo: 30 días.
PERIODO_DIAS = 30


def compute_for_period(
	salario_mensual: float,
	params,
	dias_no_remunerados: float = 0.0,
) -> float:
	"""Devuelve el monto de auxilio aplicable en el periodo.

	Si el empleado tuvo días no remunerados (licencias no remuneradas,
	suspensión, ausencias injustificadas) se prorratea linealmente:

		auxilio_real = auxilio_pleno × (PERIODO_DIAS - dias_no_rem) / PERIODO_DIAS

	`dias_no_remunerados` se acumula en el export desde las novedades
	con `unidad="dias"` y tipos no remunerados; ver
	`single_sheet._aggregate`.
	"""
	if not is_eligible(salario_mensual, params):
		return 0.0
	pleno = float(params.auxilio_transporte or 0.0)
	dias_no = max(0.0, float(dias_no_remunerados or 0.0))
	if dias_no >= PERIODO_DIAS:
		return 0.0
	if dias_no <= 0:
		return round(pleno, 2)
	factor = (PERIODO_DIAS - dias_no) / PERIODO_DIAS
	return round(pleno * factor, 2)
