"""Auxilio de transporte automático.

NO es una novedad: el sistema lo aplica de oficio en el export.

Regla legal Colombia: el empleado recibe auxilio de transporte si su
salario base es ≤ 2 SMMLV y trabajó al menos un día en el periodo. El
valor es fijo por año y vive en `Payroll Parametros Globales`.

Esta función la consume el export para inyectar una columna fija por
empleado elegible. No produce `Payroll Novedad`.
"""

from __future__ import annotations


# Tope legal: 2 salarios mínimos. Hardcodeado el SMMLV 2026 = 1_300_000
# (placeholder hasta que el dueño confirme; en hardening se mueve a
# parametros globales).
SMMLV_2026 = 1_300_000.0
TOPE_AUXILIO = 2 * SMMLV_2026


def is_eligible(salario_mensual: float) -> bool:
	return 0 < float(salario_mensual or 0) <= TOPE_AUXILIO


def compute_for_period(salario_mensual: float, params) -> float:
	"""Devuelve el monto de auxilio aplicable en el periodo.

	Si el contrato no fue continuo (ingresó / se retiró a mitad de periodo)
	la prorrata vive en hardening (Fase H). Por ahora todo o nada.
	"""
	if not is_eligible(salario_mensual):
		return 0.0
	return round(float(params.auxilio_transporte or 0.0), 2)
