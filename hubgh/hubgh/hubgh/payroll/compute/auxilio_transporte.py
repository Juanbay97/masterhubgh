"""Auxilio de transporte automático (no es novedad — se aplica de oficio).

Reglas vigentes (confirmadas por el dueño 2026-04-30):

- Aplica a TC **y TP**, siempre que el ingreso mensual estimado sea
  ≤ 2 SMMLV. Para TC el ingreso = `salario_mensual`. Para TP, que cobra
  por hora literal, el ingreso lo evalúa el caller pasando
  `ingresos_periodo` (suma del devengado del periodo).

- Prorrateo: 24 días al mes = 100% (6 días/semana × 4 semanas). El
  empleado recibe `auxilio × min(dias_trabajados / 24, 1)`. Si no se
  pasa `dias_trabajados`, asumimos 24 (full).
"""

from __future__ import annotations


PERIODO_DIAS_AUXILIO = 24  # 6 días/semana × 4 semanas (regla confirmada)


def _tope(params) -> float:
	smmlv = float(getattr(params, "salario_minimo_mensual", 0) or 0)
	return 2.0 * smmlv if smmlv > 0 else 0.0


def is_eligible(salario_mensual: float, params, ingresos_periodo: float = 0.0) -> bool:
	"""Elegible si los ingresos del mes son ≤ 2 SMMLV.

	Para TC: usa `salario_mensual`.
	Para TP (salario_mensual=0): usa `ingresos_periodo`.
	"""
	tope = _tope(params)
	if tope <= 0:
		return False
	salario = float(salario_mensual or 0)
	if salario > 0:
		return 0 < salario <= tope
	# TP / sin salario fijo: evaluar por devengado del periodo.
	devengado = float(ingresos_periodo or 0)
	return 0 < devengado <= tope


def compute_for_period(
	salario_mensual: float,
	params,
	dias_trabajados: float | None = None,
	dias_no_remunerados: float = 0.0,
	ingresos_periodo: float = 0.0,
) -> float:
	"""Devuelve el monto de auxilio aplicable en el periodo.

	`dias_trabajados`: si se pasa, se usa para prorratear directamente.
	`dias_no_remunerados`: si no se pasa `dias_trabajados`, se infiere
	`PERIODO_DIAS_AUXILIO - dias_no_remunerados`.
	`ingresos_periodo`: total devengado del periodo (importa para TP).
	"""
	if not is_eligible(salario_mensual, params, ingresos_periodo=ingresos_periodo):
		return 0.0
	pleno = float(params.auxilio_transporte or 0.0)
	if pleno <= 0:
		return 0.0

	if dias_trabajados is not None:
		dias_eff = max(0.0, float(dias_trabajados))
	else:
		dias_eff = max(0.0, PERIODO_DIAS_AUXILIO - float(dias_no_remunerados or 0))

	# Cap al 100%.
	factor = min(dias_eff / PERIODO_DIAS_AUXILIO, 1.0) if PERIODO_DIAS_AUXILIO > 0 else 0.0
	return round(pleno * factor, 2)
