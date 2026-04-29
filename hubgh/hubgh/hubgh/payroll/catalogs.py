"""Catálogos del módulo payroll v2.

Estos catálogos son la fuente única de verdad para fuentes externas,
tipos canónicos de novedad y reglas de cálculo. Viven en código, NO
como DocTypes editables: cualquier cambio se hace por PR y revisión.

Reglas de pago confirmadas con el dueño del producto el 2026-04-29.
"""

from dataclasses import dataclass, field
from typing import Callable


# ──────────────────────────────────────────────────────────────────────
# Jornada
# ──────────────────────────────────────────────────────────────────────

JORNADA_TC = "Tiempo Completo"
JORNADA_TP = "Tiempo Parcial"
JORNADA_VALUES = (JORNADA_TC, JORNADA_TP)


# ──────────────────────────────────────────────────────────────────────
# Periodo de corte por jornada
# ──────────────────────────────────────────────────────────────────────
# Confirmado por el dueño 2026-04-29:
#   - TC: del día 16 del mes anterior al día 15 del mes vigente.
#   - TP: del día 23 del mes anterior al día 22 del mes vigente.
# El adapter usa estos valores para validar el rango del archivo y para
# alinear el `Payroll Run.period_year/period_month` con el rango leído.

PERIODO_CORTE_TC = {"start_day_prev_month": 16, "end_day_current_month": 15}
PERIODO_CORTE_TP = {"start_day_prev_month": 23, "end_day_current_month": 22}


# ──────────────────────────────────────────────────────────────────────
# Multiplicadores de horas (sobre valor hora base)
# ──────────────────────────────────────────────────────────────────────

MULTIPLICADORES_HORAS: dict[str, float] = {
	"HD": 1.00,    # Hora diurna ordinaria
	"HN": 1.35,    # Hora nocturna
	"HFD": 1.85,   # Hora festiva diurna
	"HFN": 2.10,   # Hora festiva nocturna
	"HED": 1.25,   # Hora extra diurna
	"HEN": 1.75,   # Hora extra nocturna
	"HEFD": 2.05,  # Hora extra festiva diurna
	"HEFN": 2.55,  # Hora extra festiva nocturna
}


# ──────────────────────────────────────────────────────────────────────
# Prestaciones sociales (porcentaje sobre base salarial)
# ──────────────────────────────────────────────────────────────────────

PRESTACIONES_SOCIALES: dict[str, float] = {
	"CESANTIAS": 0.0833,
	"PRIMA": 0.0833,
	"VACACIONES": 0.0417,
	"INTERESES_CES": 0.0100,
	"SALUD": 0.0850,
	"PENSION": 0.1200,
	"ARL": 0.0696,
	"CAJA": 0.0400,
}


# ──────────────────────────────────────────────────────────────────────
# Fuentes externas (adapters)
# ──────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SourceSpec:
	id: str
	label: str
	parser_module: str
	# Heurísticas de detección — placeholder; el detector real llega en Fase B.
	filename_re: str = ""
	sheets_subset: tuple[str, ...] = ()
	columns_subset: tuple[str, ...] = ()


SOURCES: tuple[SourceSpec, ...] = (
	SourceSpec(
		id="clonk",
		label="CLONK (control de horas y ausentismos)",
		parser_module="hubgh.hubgh.payroll.adapters.clonk",
		filename_re=r"clonk",
		sheets_subset=("Resumen horas", "Detalle diario", "Ausentismos"),
	),
	SourceSpec(
		id="payflow",
		label="Payflow (adelantos de nómina)",
		parser_module="hubgh.hubgh.payroll.adapters.payflow",
		filename_re=r"payflow|pay\s*flow",
	),
	SourceSpec(
		id="fincomercio",
		label="Fincomercio (libranza)",
		parser_module="hubgh.hubgh.payroll.adapters.fincomercio",
		filename_re=r"fincomercio",
	),
	SourceSpec(
		id="fongiga",
		label="Fondo Empleados FONGIGA",
		parser_module="hubgh.hubgh.payroll.adapters.fongiga",
		filename_re=r"fongiga|fon\s*giga",
	),
	SourceSpec(
		id="libranza_davivienda",
		label="Libranza Davivienda",
		parser_module="hubgh.hubgh.payroll.adapters.libranza_davivienda",
		filename_re=r"libranza.*davivienda|davivienda.*libranza",
	),
	SourceSpec(
		id="libranza_compensar",
		label="Libranza Compensar",
		parser_module="hubgh.hubgh.payroll.adapters.libranza_compensar",
		filename_re=r"libranza.*compensar|compensar.*libranza",
	),
	SourceSpec(
		id="libranza_comfenalco",
		label="Libranza Comfenalco",
		parser_module="hubgh.hubgh.payroll.adapters.libranza_comfenalco",
		filename_re=r"libranza.*comfenalco|comfenalco.*libranza",
	),
	SourceSpec(
		id="manual_internal",
		label="Novedad manual interna (HubGH)",
		parser_module="hubgh.hubgh.payroll.adapters.manual",
	),
	SourceSpec(
		id="unknown",
		label="Fuente no reconocida",
		parser_module="hubgh.hubgh.payroll.adapters.unknown",
	),
)


SOURCES_BY_ID: dict[str, SourceSpec] = {spec.id: spec for spec in SOURCES}


# ──────────────────────────────────────────────────────────────────────
# Tipos canónicos de novedad
# ──────────────────────────────────────────────────────────────────────

# Aplicabilidad por jornada del contrato (snapshot al procesar).
# "both" = aplica a TC y TP por igual.
JORNADA_BOTH = "both"


@dataclass(frozen=True)
class NovedadTypeSpec:
	id: str                       # enum canónico fijo en código
	label: str
	unidad: str                   # "horas" | "dias" | "cop" | "unidades"
	jornada_aplicable: str        # "TC" | "TP" | "both"
	# Configurable: el usuario puede tunear el % de pago en línea.
	pago_configurable: bool = False
	porcentaje_default: float = 1.0
	# El módulo de cálculo se resuelve por id de tipo (ver RULES abajo).
	notas: str = ""


NOVEDAD_TYPES: tuple[NovedadTypeSpec, ...] = (
	# ── Horas (CLONK) ────────────────────────────────────────────────
	NovedadTypeSpec("HD", "Hora diurna ordinaria", "horas", JORNADA_BOTH),
	NovedadTypeSpec("HN", "Hora nocturna", "horas", JORNADA_BOTH),
	NovedadTypeSpec("HFD", "Hora festiva diurna", "horas", JORNADA_BOTH),
	NovedadTypeSpec("HFN", "Hora festiva nocturna", "horas", JORNADA_BOTH),
	NovedadTypeSpec("HED", "Hora extra diurna", "horas", JORNADA_BOTH),
	NovedadTypeSpec("HEN", "Hora extra nocturna", "horas", JORNADA_BOTH),
	NovedadTypeSpec("HEFD", "Hora extra festiva diurna", "horas", JORNADA_BOTH),
	NovedadTypeSpec("HEFN", "Hora extra festiva nocturna", "horas", JORNADA_BOTH),

	# ── Ausentismos ──────────────────────────────────────────────────
	NovedadTypeSpec(
		"INCAPACIDAD_ENFERMEDAD_GENERAL",
		"Incapacidad enfermedad general",
		"dias",
		JORNADA_BOTH,
		pago_configurable=True,
		porcentaje_default=0.66,
		notas="66% del valor día desde día 1 (excepto licencias de maternidad).",
	),
	NovedadTypeSpec(
		"INCAPACIDAD_ACCIDENTE_TRABAJO",
		"Incapacidad por accidente de trabajo",
		"dias",
		JORNADA_BOTH,
		pago_configurable=True,
		porcentaje_default=1.00,
		notas="100% del valor día, paga ARL.",
	),
	NovedadTypeSpec(
		"INCAPACIDAD_PAGADA_EMPRESA",
		"Incapacidad pagada por la empresa",
		"dias",
		JORNADA_BOTH,
		pago_configurable=True,
		porcentaje_default=1.00,
		notas="100% del valor día, paga empresa.",
	),
	NovedadTypeSpec(
		"INCAPACIDAD_MAYOR_180_DIAS",
		"Incapacidad mayor a 180 días",
		"dias",
		JORNADA_BOTH,
		pago_configurable=True,
		porcentaje_default=0.50,
		notas="50% del valor día.",
	),
	NovedadTypeSpec(
		"LICENCIA_REMUNERADA",
		"Licencia remunerada",
		"dias",
		JORNADA_BOTH,
		pago_configurable=True,
		porcentaje_default=1.00,
	),
	NovedadTypeSpec(
		"LICENCIA_NO_REMUNERADA",
		"Licencia no remunerada",
		"dias",
		JORNADA_BOTH,
		porcentaje_default=0.00,
		notas="No paga; no cuenta días para prestaciones sociales.",
	),
	NovedadTypeSpec(
		"LICENCIA_LUTO",
		"Licencia por luto",
		"dias",
		JORNADA_BOTH,
		pago_configurable=True,
		porcentaje_default=1.00,
		notas="100% del valor día, máximo 5 días.",
	),
	NovedadTypeSpec(
		"PERMISO_CALAMIDAD",
		"Permiso por calamidad doméstica",
		"dias",
		JORNADA_BOTH,
		pago_configurable=True,
		porcentaje_default=1.00,
	),
	NovedadTypeSpec(
		"AUSENCIA_INJUSTIFICADA",
		"Ausencia no justificada",
		"dias",
		JORNADA_BOTH,
		porcentaje_default=-1.00,
		notas="Descuenta el valor día.",
	),
	NovedadTypeSpec(
		"SUSPENSION_CONTRATO",
		"Suspensión de contrato",
		"dias",
		JORNADA_BOTH,
		porcentaje_default=0.00,
		notas="No paga; suspende prestaciones del periodo.",
	),

	# ── Vacaciones ───────────────────────────────────────────────────
	NovedadTypeSpec(
		"VACACIONES",
		"Vacaciones disfrutadas o compensadas",
		"dias",
		JORNADA_BOTH,
		porcentaje_default=1.00,
		notas="valor_día_actual × días_hábiles.",
	),

	# ── Beneficios remunerados (CLONK Novedades) ─────────────────────
	NovedadTypeSpec(
		"DESCANSO",
		"Descanso compensatorio remunerado",
		"dias",
		JORNADA_BOTH,
		porcentaje_default=1.00,
		notas="100% del valor día. Concepto más frecuente del CLONK.",
	),
	NovedadTypeSpec(
		"DIA_FAMILIA",
		"Día de la familia",
		"dias",
		JORNADA_BOTH,
		porcentaje_default=1.00,
		notas="Beneficio empresa, 100% del valor día.",
	),
	NovedadTypeSpec(
		"DIA_CUMPLEANOS",
		"Día de cumpleaños",
		"dias",
		JORNADA_BOTH,
		porcentaje_default=1.00,
		notas="Beneficio empresa, 100% del valor día.",
	),
	NovedadTypeSpec(
		"LICENCIA_MATERNIDAD",
		"Licencia de maternidad",
		"dias",
		JORNADA_BOTH,
		porcentaje_default=1.00,
		notas="100% del valor día; lo cubre la EPS, la empresa registra y reclama.",
	),

	# ── Pagos / auxilios ─────────────────────────────────────────────
	NovedadTypeSpec(
		"AUXILIO_MOVILIZACION_DOM_FEST",
		"Auxilio movilización dom-fest",
		"cop",
		JORNADA_BOTH,
		notas="Valor literal pactado por nómina.",
	),
	NovedadTypeSpec(
		"AUXILIO_RODAMIENTO",
		"Auxilio rodamiento y/o mantenimiento operación",
		"cop",
		JORNADA_BOTH,
		notas="Valor literal pactado por nómina.",
	),

	# ── Bonificaciones ───────────────────────────────────────────────
	NovedadTypeSpec(
		"BONIFICACION_CP",
		"Bonificación CP",
		"cop",
		JORNADA_BOTH,
		notas="Valor declarado explícitamente.",
	),
	NovedadTypeSpec(
		"PERDIDA_BONIFICACION",
		"Pérdida de bonificación",
		"cop",
		JORNADA_BOTH,
		notas="Valor declarado, descuenta.",
	),

	# ── Inducción ────────────────────────────────────────────────────
	NovedadTypeSpec(
		"INDUCCION",
		"Inducción",
		"horas",
		JORNADA_BOTH,
		porcentaje_default=1.00,
		notas="TC = 1 día completo (8h equivalente). TP = 7.33 horas × hora_tp_fija.",
	),

	# ── Descuentos (valor literal del archivo) ──────────────────────
	NovedadTypeSpec("ADELANTO_NOMINA_PAYFLOW", "Adelanto nómina Payflow", "cop", JORNADA_BOTH),
	NovedadTypeSpec("DESCUENTO_SANITAS_PREMIUM", "Descuento Sanitas Premium", "cop", JORNADA_BOTH),
	NovedadTypeSpec("DESCUENTO_GAFAS", "Descuento gafas", "cop", JORNADA_BOTH),
	NovedadTypeSpec("FONDO_EMPLEADOS_FONGIGA", "Fondo de empleados FONGIGA", "cop", JORNADA_BOTH),
	NovedadTypeSpec("LIBRANZA_COMFENALCO", "Libranza Comfenalco", "cop", JORNADA_BOTH),
	NovedadTypeSpec("LIBRANZA_FINCOMERCIO", "Libranza Fincomercio", "cop", JORNADA_BOTH),
	NovedadTypeSpec("LIBRANZA_DAVIVIENDA", "Libranza Davivienda", "cop", JORNADA_BOTH),
	NovedadTypeSpec("LIBRANZA_COMPENSAR", "Libranza Compensar", "cop", JORNADA_BOTH),
	NovedadTypeSpec("PRESTAMO_EMPRESA", "Préstamo empresa", "cop", JORNADA_BOTH),
	NovedadTypeSpec("PRESTAMO_FONGIGA", "Préstamo FONGIGA", "cop", JORNADA_BOTH),

	# ── Cambios contractuales con impacto de pago ───────────────────
	NovedadTypeSpec(
		"ASCENSO",
		"Ascenso",
		"unidades",
		JORNADA_BOTH,
		notas="Cambia salario base; aplicar prorrateo si es retroactivo en el periodo.",
	),

	# ── Catch-all ────────────────────────────────────────────────────
	NovedadTypeSpec(
		"OTRO",
		"Otro (especificar)",
		"cop",
		JORNADA_BOTH,
		pago_configurable=True,
	),
)


NOVEDAD_TYPES_BY_ID: dict[str, NovedadTypeSpec] = {spec.id: spec for spec in NOVEDAD_TYPES}


# ──────────────────────────────────────────────────────────────────────
# Parámetros globales — defaults; el DocType Single los persiste y permite override.
# ──────────────────────────────────────────────────────────────────────

PARAMETROS_GLOBALES_DEFAULTS: dict[str, float] = {
	"hora_tp_fija": 9530.0,            # COP, ajustar por año
	"auxilio_transporte": 249095.0,    # COP, ajustar por año
	"jornada_induccion_tp_horas": 7.33,
	"divisor_hora_tc": 240.0,          # salario_mensual / 240 = valor hora TC
	"salario_minimo_mensual": 1750905.0,  # SMMLV 2026 (Colombia)
}


# ──────────────────────────────────────────────────────────────────────
# Mapeo de string del archivo de origen → id canónico
# ──────────────────────────────────────────────────────────────────────
# Útil para los adapters al traducir conceptos crudos del archivo a tipos canónicos.

CONCEPT_ALIASES: dict[str, str] = {
	# Ausentismos (hoja AUSENTISMOS del prenómina + CLONK Novedades)
	"ausencia no justificada": "AUSENCIA_INJUSTIFICADA",
	"ausentismo": "AUSENCIA_INJUSTIFICADA",  # CLONK lo nombra así
	"incapacidad >180 dias": "INCAPACIDAD_MAYOR_180_DIAS",
	"incapacidad accidente trabajo": "INCAPACIDAD_ACCIDENTE_TRABAJO",
	"incapacidad at": "INCAPACIDAD_ACCIDENTE_TRABAJO",  # CLONK
	"incapacidad enfermedad general": "INCAPACIDAD_ENFERMEDAD_GENERAL",
	"incapacidad eg": "INCAPACIDAD_ENFERMEDAD_GENERAL",  # CLONK
	"incapacidad pagada empresa": "INCAPACIDAD_PAGADA_EMPRESA",
	"licencia no remunerada": "LICENCIA_NO_REMUNERADA",
	"l. no remunerada": "LICENCIA_NO_REMUNERADA",  # CLONK
	"licencia por luto": "LICENCIA_LUTO",
	"licencia remunerada": "LICENCIA_REMUNERADA",
	"permiso por calamidad domestica": "PERMISO_CALAMIDAD",
	"suspension de contrato": "SUSPENSION_CONTRATO",
	"suspension": "SUSPENSION_CONTRATO",  # CLONK
	"maternidad": "LICENCIA_MATERNIDAD",  # CLONK
	# Beneficios remunerados (CLONK)
	"descanso": "DESCANSO",
	"dia familia": "DIA_FAMILIA",
	"dia cumpleanos": "DIA_CUMPLEANOS",
	"dia cumpleano": "DIA_CUMPLEANOS",
	# Vacaciones
	"vacaciones": "VACACIONES",
	# Pagos / auxilios
	"auxilio movilizacion dom-fest": "AUXILIO_MOVILIZACION_DOM_FEST",
	"auxilio rodamiento y/o mantenimiento operacion": "AUXILIO_RODAMIENTO",
	# Bonificaciones
	"bonificacion cp": "BONIFICACION_CP",
	"perdida bonificaciones": "PERDIDA_BONIFICACION",
	# Descuentos
	"adelanto nomina payflow": "ADELANTO_NOMINA_PAYFLOW",
	"descuento empleado sanitas premiun": "DESCUENTO_SANITAS_PREMIUM",
	"descuento empleado sanitas premium": "DESCUENTO_SANITAS_PREMIUM",
	"descuento gafas": "DESCUENTO_GAFAS",
	"fondo empleados": "FONDO_EMPLEADOS_FONGIGA",
	"fondo de empleados fongiga": "FONDO_EMPLEADOS_FONGIGA",
	"libranza comfenalco": "LIBRANZA_COMFENALCO",
	"libranza fincomercio": "LIBRANZA_FINCOMERCIO",
	"libranza davivienda": "LIBRANZA_DAVIVIENDA",
	"libranza compensar": "LIBRANZA_COMPENSAR",
	"prestamo empresa": "PRESTAMO_EMPRESA",
	"prestamo fongiga": "PRESTAMO_FONGIGA",
	# Inducción
	"induccion": "INDUCCION",
}


def canonicalize_concept(text: str | None) -> str:
	"""Mapea un concepto crudo del archivo a un id canónico de NOVEDAD_TYPES.

	Devuelve `OTRO` si el texto no matchea ningún alias conocido. Los adapters
	pueden registrar aliases adicionales antes de llamar a este resolver.
	"""
	if not text:
		return "OTRO"
	import unicodedata

	normalized = unicodedata.normalize("NFKD", str(text)).strip().lower()
	normalized = "".join(c for c in normalized if not unicodedata.combining(c))
	normalized = " ".join(normalized.split())
	return CONCEPT_ALIASES.get(normalized, "OTRO")
