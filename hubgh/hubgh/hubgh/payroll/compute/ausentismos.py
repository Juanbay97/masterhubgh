"""Cálculo de ausentismos, licencias, beneficios remunerados y vacaciones.

Reglas (confirmadas por el dueño en revisión 2026-04-30):

  Tiempo Completo (TC):
    valor_dia = salario_mensual / 30
    DESCANSO, VACACIONES, LIC_REMUNERADA, LUTO (≤ 5d), CALAMIDAD,
    LIC_MATERNIDAD, INCAP_AT, INCAP_PAGADA_EMPRESA → 100% × valor_dia × días
    INCAP_ENFERMEDAD_GENERAL → 66% × valor_dia × días
    INCAP_>180_DIAS → 50% × valor_dia × días
    AUSENCIA_INJUSTIFICADA → -100% × valor_dia × días (descuenta)
    LIC_NO_REMUNERADA, SUSPENSION_CONTRATO → 0

  Tiempo Parcial (TP):
    El TP cobra por hora literal (hora_tp_fija). No tiene salario
    mensual; los días remunerados se pagan al SMMLV diario.

    valor_dia_tp = SMMLV / 30  (params.salario_minimo_mensual / 30)

    DESCANSO → 0 (no se le paga descanso al TP)
    VACACIONES, LIC_REMUNERADA, LUTO (≤ 5d), CALAMIDAD, LIC_MATERNIDAD,
    INCAP_AT, INCAP_PAGADA_EMPRESA → 100% × valor_dia_tp × días
    INCAP_ENFERMEDAD_GENERAL → 66% × valor_dia_tp × días
    INCAP_>180_DIAS → 50% × valor_dia_tp × días
    AUSENCIA_INJUSTIFICADA → -100% × valor_dia_tp × días (descuenta el día SMMLV)
    LIC_NO_REMUNERADA, SUSPENSION_CONTRATO → 0

DIA_FAMILIA y DIA_CUMPLEANOS NO se calculan acá — su regla 5.83h/2.92h
vive en `compute/dias_remunerados.py`.
"""

from __future__ import annotations

from hubgh.hubgh.payroll import catalogs


_TC = "Tiempo Completo"
_TP = "Tiempo Parcial"

# Tipos día con regla "5.83h jornada completa / 2.92h media jornada".
# No los procesa este módulo; los excluimos de `applies()`.
_DIAS_REMUNERADOS_FIJOS = frozenset({"DIA_FAMILIA", "DIA_CUMPLEANOS"})


def applies(tipo_novedad: str) -> bool:
	spec = catalogs.NOVEDAD_TYPES_BY_ID.get(tipo_novedad)
	if not spec or spec.unidad != "dias":
		return False
	if tipo_novedad == "INDUCCION":
		return False
	if tipo_novedad in _DIAS_REMUNERADOS_FIJOS:
		return False
	return True


def compute(novedad, params=None) -> tuple[float, float, str]:
	"""Devuelve (computed_amount, computed_quantity, calc_notes)."""
	spec = catalogs.NOVEDAD_TYPES_BY_ID.get(novedad.tipo_novedad)
	if spec is None:
		return 0.0, 0.0, f"Tipo {novedad.tipo_novedad} no está en catalogs.NOVEDAD_TYPES."

	dias = float(novedad.cantidad or 0.0)
	jornada = novedad.tipo_jornada_snapshot or ""

	# Caso especial TP: no se paga descanso.
	if novedad.tipo_novedad == "DESCANSO" and jornada == _TP:
		return 0.0, dias, "TP: descanso no remunerado."

	# Tope LICENCIA_LUTO = 5 días (aplica a ambas jornadas).
	dias_pagables = dias
	tope_note = ""
	if novedad.tipo_novedad == "LICENCIA_LUTO" and dias > 5:
		dias_pagables = 5.0
		tope_note = f" (tope luto: {dias - 5:.0f} días por encima no pagados)"

	# Override de porcentaje desde el override manual del operador.
	porcentaje = float(spec.porcentaje_default)
	override = (novedad.raw_payload or {}).get("override_porcentaje") if novedad.raw_payload else None
	if override is not None:
		try:
			porcentaje = float(override)
		except (TypeError, ValueError):
			pass

	# Resolver valor del día según jornada.
	if jornada == _TP:
		smmlv = _smmlv(params)
		if smmlv <= 0:
			return 0.0, dias, "TP: SMMLV no parametrizado — no devenga."
		valor_dia = smmlv / 30.0
		base_label = f"SMMLV/30 ${valor_dia:.2f}"
	else:
		# TC (incluye TC-Admin / Aprendizaje normalizados).
		salario = float(novedad.salario_mensual or 0.0)
		if salario <= 0 or dias_pagables <= 0:
			return 0.0, dias, "Sin salario o sin días pagables — no devenga."
		valor_dia = salario / 30.0
		base_label = f"salario/30 ${valor_dia:.2f}"

	if dias_pagables <= 0:
		return 0.0, dias, "Sin días pagables — no devenga."

	amount = round(dias_pagables * valor_dia * porcentaje, 2)
	notes = (
		f"{jornada or 'sin jornada'}: {dias_pagables:.2f}d × {base_label} × "
		f"{porcentaje:.4g} = ${amount:.2f}{tope_note}"
	)
	return amount, round(dias, 4), notes


def _smmlv(params) -> float:
	if params is None:
		return float(catalogs.PARAMETROS_GLOBALES_DEFAULTS.get("salario_minimo_mensual", 0))
	return float(getattr(params, "salario_minimo_mensual", 0) or 0)
