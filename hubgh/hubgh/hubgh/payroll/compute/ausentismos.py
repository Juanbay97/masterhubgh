"""Cálculo de ausentismos, licencias, beneficios remunerados y vacaciones.

Modelo unificado: cada tipo tiene un `porcentaje_default` en el catálogo
y se calcula como:

    valor_dia = salario_mensual / 30
    computed_amount = cantidad_dias × valor_dia × porcentaje_efectivo

`porcentaje_efectivo` es el override de la línea (si `manual_override` y
hay un `valor` interpretable como factor) o, en su defecto, el
`porcentaje_default` del catálogo.

Casos especiales por id de tipo:
- AUSENCIA_INJUSTIFICADA → porcentaje = -1.0 (descuenta el día completo).
- LICENCIA_NO_REMUNERADA y SUSPENSION_CONTRATO → porcentaje = 0.0.
- LICENCIA_LUTO → tope de 5 días pagados (días por encima quedan
  marcados pero no se pagan).
"""

from __future__ import annotations

from hubgh.hubgh.payroll import catalogs


# Tipos en días que pasan por este módulo (todo lo que sea unidad="dias"
# y exista en el catálogo, salvo INDUCCION que tiene módulo propio).
def applies(tipo_novedad: str) -> bool:
	spec = catalogs.NOVEDAD_TYPES_BY_ID.get(tipo_novedad)
	if not spec:
		return False
	if spec.unidad != "dias":
		return False
	return tipo_novedad != "INDUCCION"


def compute(novedad) -> tuple[float, float, str]:
	"""Devuelve (computed_amount, computed_quantity, calc_notes)."""
	spec = catalogs.NOVEDAD_TYPES_BY_ID.get(novedad.tipo_novedad)
	if spec is None:
		return 0.0, 0.0, f"Tipo {novedad.tipo_novedad} no está en catalogs.NOVEDAD_TYPES."

	dias = float(novedad.cantidad or 0.0)
	salario = float(novedad.salario_mensual or 0.0)

	# Tope LICENCIA_LUTO = 5 días.
	dias_pagables = dias
	tope_note = ""
	if novedad.tipo_novedad == "LICENCIA_LUTO" and dias > 5:
		dias_pagables = 5.0
		tope_note = f" (tope luto: {dias - 5:.0f} días por encima no pagados)"

	porcentaje = float(spec.porcentaje_default)
	# La novedad puede traer un override en `valor` interpretado como % cuando
	# manual_override viene seteado y `valor` es razonable (-2..2). Esto es
	# para que el operador del workspace pueda tunear sin tocar código.
	valor_override = novedad.raw_payload.get("override_porcentaje") if novedad.raw_payload else None
	if valor_override is not None:
		try:
			porcentaje = float(valor_override)
		except (TypeError, ValueError):
			pass

	if salario <= 0 or dias_pagables <= 0:
		return 0.0, dias, "Sin salario o sin días pagables — no devenga."

	valor_dia = salario / 30.0
	amount = round(dias_pagables * valor_dia * porcentaje, 2)
	notes = (
		f"{dias_pagables:.2f}d × ${valor_dia:.2f}/d × {porcentaje:.4g} "
		f"= ${amount:.2f}{tope_note}"
	)
	return amount, round(dias, 4), notes
