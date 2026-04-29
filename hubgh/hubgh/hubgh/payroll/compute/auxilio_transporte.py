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


def compute_for_period(salario_mensual: float, params) -> float:
	"""Devuelve el monto de auxilio aplicable en el periodo.

	Si el contrato no fue continuo (ingresó / se retiró a mitad de periodo)
	la prorrata vive en hardening (Fase H). Por ahora todo o nada.
	"""
	if not is_eligible(salario_mensual, params):
		return 0.0
	return round(float(params.auxilio_transporte or 0.0), 2)
