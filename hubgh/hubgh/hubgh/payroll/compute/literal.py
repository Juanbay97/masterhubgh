"""Cálculo de novedades con valor literal.

Para descuentos (libranzas, préstamos, fondos, sanitas, gafas, adelantos
Payflow) y pagos no calculados (auxilios, bonificaciones declaradas):

    computed_amount = valor (con signo según si es ingreso o descuento)

El signo se determina por el id del tipo: los descuentos quedan negativos
para que el total devengado − total descontado se calcule por suma
algebraica en el export.
"""

from __future__ import annotations


# Tipos de descuento (signo negativo en computed_amount).
# Ojo: PERDIDA_BONIFICACION NO está acá porque la bonificación la
# calcula contabilidad — el sistema sólo registra el flag 1/0 como
# novedad informativa y aparece en la hoja Hechos del export como
# columna "Tiene bonif.".
DESCUENTO_TYPES = frozenset(
	{
		"ADELANTO_NOMINA_PAYFLOW",
		"DESCUENTO_SANITAS_PREMIUM",
		"DESCUENTO_GAFAS",
		"FONDO_EMPLEADOS_FONGIGA",
		"LIBRANZA_COMFENALCO",
		"LIBRANZA_FINCOMERCIO",
		"LIBRANZA_DAVIVIENDA",
		"LIBRANZA_COMPENSAR",
		"PRESTAMO_EMPRESA",
		"PRESTAMO_FONGIGA",
	}
)

PAGO_TYPES = frozenset(
	{
		"AUXILIO_MOVILIZACION_DOM_FEST",
		"AUXILIO_RODAMIENTO",
		"BONIFICACION_CP",
	}
)

LITERAL_TYPES = DESCUENTO_TYPES | PAGO_TYPES


def applies(tipo_novedad: str) -> bool:
	return tipo_novedad in LITERAL_TYPES


def compute(novedad) -> tuple[float, float, str]:
	"""Devuelve (computed_amount, computed_quantity, calc_notes)."""
	valor = float(novedad.valor or 0.0)
	if valor == 0.0:
		return 0.0, 0.0, "Valor literal en cero — sin movimiento."

	if novedad.tipo_novedad in DESCUENTO_TYPES:
		amount = -abs(valor)
		notes = f"Descuento literal: -${abs(valor):.2f}"
	else:
		amount = abs(valor)
		notes = f"Pago literal: +${abs(valor):.2f}"
	return round(amount, 2), 0.0, notes
