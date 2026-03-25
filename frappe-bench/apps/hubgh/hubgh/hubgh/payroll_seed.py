"""
Seed data for Payroll module Sprint 1 catalogs.
Run via: bench --site hubgh.test execute hubgh.hubgh.payroll_seed.seed_payroll_foundation
"""

import calendar
from datetime import date, datetime

import frappe


PAYROLL_UPLOAD_SOURCE_ROWS = [
	{
		"nombre_fuente": "CLONK",
		"tipo_fuente": "clonk",
		"hoja_principal": "Resumen horas",
		"periodicidad": "Quincenal",
		"status": "Active",
		"notas": "3 hojas: Resumen horas, Detalle diario, Ausentismos por tipo",
	},
	{
		"nombre_fuente": "Payflow Resumen",
		"tipo_fuente": "payflow",
		"periodicidad": "Mensual",
		"status": "Active",
		"notas": "Resumen consolidado de liquidacion Payflow",
	},
	{
		"nombre_fuente": "Payflow Detalle",
		"tipo_fuente": "payflow",
		"periodicidad": "Mensual",
		"status": "Active",
		"notas": "Detalle linea por linea de Payflow",
	},
	{
		"nombre_fuente": "Fincomercio",
		"tipo_fuente": "fincomercio",
		"periodicidad": "Mensual",
		"status": "Active",
		"notas": "Creditos y deducciones Fincomercio",
	},
	{
		"nombre_fuente": "Fondo FONGIGA",
		"tipo_fuente": "fondo_empleados",
		"periodicidad": "Mensual",
		"status": "Active",
		"notas": "M HOME FEBRERO 2026.xlsx - Aportes y creditos fondo",
	},
	{
		"nombre_fuente": "Libranzas Bancolombia",
		"tipo_fuente": "libranzas",
		"periodicidad": "Mensual",
		"status": "Active",
		"notas": "Deducciones de libranzas Bancolombia",
	},
	{
		"nombre_fuente": "Libranzas Compensar",
		"tipo_fuente": "libranzas",
		"periodicidad": "Mensual",
		"status": "Active",
		"notas": "Deducciones de libranzas Compensar",
	},
	{
		"nombre_fuente": "Libranzas Vivienda",
		"tipo_fuente": "libranzas",
		"periodicidad": "Mensual",
		"status": "Active",
		"notas": "Deducciones de libranzas credito vivienda",
	},
	{
		"nombre_fuente": "GH Novedad Manual",
		"tipo_fuente": "gh_novedad",
		"periodicidad": "Eventual",
		"status": "Active",
		"notas": "Novedades registradas manualmente en HubGH",
	},
	{
		"nombre_fuente": "Novedad SST",
		"tipo_fuente": "sst",
		"periodicidad": "Eventual",
		"status": "Active",
		"notas": "Incapacidades y novedades de SST",
	},
	{
		"nombre_fuente": "Novedad Bienestar",
		"tipo_fuente": "bienestar",
		"periodicidad": "Eventual",
		"status": "Active",
		"notas": "Compromisos y alertas de Bienestar con impacto nomina",
	},
]

MONTH_NAMES_ES = {
	1: "Enero",
	2: "Febrero",
	3: "Marzo",
	4: "Abril",
	5: "Mayo",
	6: "Junio",
	7: "Julio",
	8: "Agosto",
	9: "Septiembre",
	10: "Octubre",
	11: "Noviembre",
	12: "Diciembre",
}


def seed_payroll_foundation():
	"""Seed all payroll foundation catalogs."""
	seed_novedad_types()
	seed_source_catalog()
	seed_rule_catalog()
	seed_current_period()
	frappe.db.commit()
	print("✓ Payroll foundation data seeded successfully")


def seed_payroll_upload_catalogs(reference_date=None):
	"""Seed only the uploader dropdown catalogs with low-risk defaults."""
	created_sources = seed_source_catalog(default_rows=PAYROLL_UPLOAD_SOURCE_ROWS)
	created_periods = seed_upload_period_catalog(reference_date=reference_date)
	frappe.db.commit()
	print(
		"✓ Payroll upload catalogs ready "
		f"(sources created: {created_sources}, periods created: {created_periods})"
	)


def _coerce_reference_date(reference_date=None):
	if not reference_date:
		return date.today()
	if isinstance(reference_date, datetime):
		return reference_date.date()
	if isinstance(reference_date, date):
		return reference_date
	return frappe.utils.getdate(reference_date)


def _count_business_days(start_date, end_date):
	return sum(1 for day in range(start_date.day, end_date.day + 1) if date(start_date.year, start_date.month, day).weekday() < 5)


def _build_quincena_period(reference_date=None):
	anchor_date = _coerce_reference_date(reference_date)
	year = anchor_date.year
	month = anchor_date.month
	last_day = calendar.monthrange(year, month)[1]
	quincena = 1 if anchor_date.day <= 15 else 2
	start_day = 1 if quincena == 1 else 16
	end_day = 15 if quincena == 1 else last_day
	start_date = date(year, month, start_day)
	end_date = date(year, month, end_day)
	month_name = MONTH_NAMES_ES[month]

	return {
		"nombre_periodo": f"{month_name} {year} - Quincena {quincena}",
		"ano": year,
		"mes": month,
		"fecha_corte_inicio": start_date.isoformat(),
		"fecha_corte_fin": end_date.isoformat(),
		"status": "Active",
		"total_dias": (end_date - start_date).days + 1,
		"dias_laborales": _count_business_days(start_date, end_date),
		"observaciones": "Periodo operativo generado para habilitar el uploader de nomina.",
	}


def seed_upload_period_catalog(reference_date=None):
	"""Ensure there is at least one active payroll period for the uploader."""
	period_data = _build_quincena_period(reference_date)
	existing_active = frappe.db.exists(
		"Payroll Period Config",
		{
			"ano": period_data["ano"],
			"mes": period_data["mes"],
			"fecha_corte_inicio": period_data["fecha_corte_inicio"],
			"fecha_corte_fin": period_data["fecha_corte_fin"],
			"status": "Active",
		},
	)
	if existing_active:
		print(f"  → Active uploader period already exists: {existing_active}")
		return 0

	doc = frappe.get_doc({"doctype": "Payroll Period Config", **period_data})
	doc.insert(ignore_permissions=True)
	print(f"  → Created active uploader period: {doc.name}")
	return 1


def seed_novedad_types():
	"""Seed Payroll Novedad Type catalog with types from CLONK."""
	novedad_types = [
		# Ausentismos (from CLONK sheet 3)
		{"codigo": "DESCANSO", "novedad_type": "Descanso", "sensitivity": "operational", "status": "Active"},
		{"codigo": "VACACIONES", "novedad_type": "Vacaciones", "sensitivity": "operational", "status": "Active"},
		{"codigo": "INC-EG", "novedad_type": "Incapacidad Enfermedad General", "sensitivity": "clinical", "status": "Active", "requiere_soporte": 1},
		{"codigo": "INC-AT", "novedad_type": "Incapacidad Accidente de Trabajo", "sensitivity": "sst_clinical", "status": "Active", "requiere_soporte": 1},
		{"codigo": "ENF-GENERAL", "novedad_type": "Enfermedad General", "sensitivity": "clinical", "status": "Active", "requiere_soporte": 1},
		{"codigo": "AUSENTISMO", "novedad_type": "Ausentismo", "sensitivity": "disciplinary", "status": "Active"},
		{"codigo": "LIC-REM", "novedad_type": "Licencia Remunerada", "sensitivity": "operational", "status": "Active", "requiere_soporte": 1},
		{"codigo": "LIC-NO-REM", "novedad_type": "Licencia No Remunerada", "sensitivity": "operational", "status": "Active", "requiere_soporte": 1},
		{"codigo": "CALAMIDAD", "novedad_type": "Calamidad Doméstica", "sensitivity": "operational", "status": "Active", "requiere_soporte": 1},
		{"codigo": "MATERNIDAD", "novedad_type": "Licencia de Maternidad", "sensitivity": "clinical", "status": "Active", "requiere_soporte": 1},
		{"codigo": "DIA-FAMILIA", "novedad_type": "Día de la Familia", "sensitivity": "operational", "status": "Active"},
		{"codigo": "CUMPLEANOS", "novedad_type": "Día de Cumpleaños", "sensitivity": "operational", "status": "Active"},
		{"codigo": "INDUCCION", "novedad_type": "Inducción", "sensitivity": "operational", "status": "Active"},
		{"codigo": "LUTO", "novedad_type": "Licencia de Luto", "sensitivity": "operational", "status": "Active", "requiere_soporte": 1},
		# Horas extras (from CLONK sheet 1)
		{"codigo": "HED", "novedad_type": "Hora Extra Diurna", "sensitivity": "operational", "status": "Active"},
		{"codigo": "HEN", "novedad_type": "Hora Extra Nocturna", "sensitivity": "operational", "status": "Active"},
		{"codigo": "HEFD", "novedad_type": "Hora Extra Festivo Diurna", "sensitivity": "operational", "status": "Active"},
		{"codigo": "HEFN", "novedad_type": "Hora Extra Festivo Nocturna", "sensitivity": "operational", "status": "Active"},
		{"codigo": "HD", "novedad_type": "Hora Diurna", "sensitivity": "operational", "status": "Active"},
		{"codigo": "HN", "novedad_type": "Hora Nocturna", "sensitivity": "operational", "status": "Active"},
		{"codigo": "HFD", "novedad_type": "Hora Festivo Diurna", "sensitivity": "operational", "status": "Active"},
		{"codigo": "HFN", "novedad_type": "Hora Festivo Nocturna", "sensitivity": "operational", "status": "Active"},
		# Novedades administrativas
		{"codigo": "NR", "novedad_type": "Novedad Registrada", "sensitivity": "operational", "status": "Active"},
		{"codigo": "NNR", "novedad_type": "Novedad No Registrada", "sensitivity": "disciplinary", "status": "Active"},
		{"codigo": "DNR", "novedad_type": "Día No Registrado", "sensitivity": "disciplinary", "status": "Active"},
		# Descuentos
		{"codigo": "DESC-LIBRANZA", "novedad_type": "Descuento Libranza", "sensitivity": "operational", "status": "Active"},
		{"codigo": "DESC-FONDO", "novedad_type": "Descuento Fondo Empleados", "sensitivity": "operational", "status": "Active"},
		{"codigo": "DESC-SANITAS", "novedad_type": "Descuento Sanitas Premium", "sensitivity": "operational", "status": "Active"},
		{"codigo": "DESC-GAFAS", "novedad_type": "Descuento Gafas Convenio", "sensitivity": "operational", "status": "Active"},
		{"codigo": "DESC-PRESTAMO", "novedad_type": "Descuento Préstamo Empresa", "sensitivity": "operational", "status": "Active"},
		# Devengos
		{"codigo": "AUX-HOME12", "novedad_type": "Auxilio HOME 12", "sensitivity": "operational", "status": "Active"},
		{"codigo": "AUX-DOMINICAL", "novedad_type": "Auxilio Dominical Nocturno", "sensitivity": "operational", "status": "Active"},
		{"codigo": "BONIF", "novedad_type": "Bonificación", "sensitivity": "operational", "status": "Active"},
		{"codigo": "BONIF-PERD", "novedad_type": "Pérdida de Bonificación", "sensitivity": "disciplinary", "status": "Active"},
	]

	for data in novedad_types:
		if not frappe.db.exists("Payroll Novedad Type", data["codigo"]):
			doc = frappe.get_doc({"doctype": "Payroll Novedad Type", **data})
			doc.insert(ignore_permissions=True)
			print(f"  → Created novedad type: {data['codigo']}")


def seed_source_catalog(default_rows=None):
	"""Seed Payroll Source Catalog with all mapped sources."""
	sources = default_rows or [
		{
			"nombre_fuente": "CLONK",
			"tipo_fuente": "clonk",
			"hoja_principal": "Resumen horas",
			"periodicidad": "Quincenal",
			"status": "Active",
			"notas": "3 hojas: Resumen horas, Detalle diario, Ausentismos por tipo",
		},
		{
			"nombre_fuente": "Payflow Resumen",
			"tipo_fuente": "payflow",
			"periodicidad": "Mensual",
			"status": "Active",
			"notas": "Resumen consolidado de liquidación Payflow",
		},
		{
			"nombre_fuente": "Payflow Detalle",
			"tipo_fuente": "payflow",
			"periodicidad": "Mensual",
			"status": "Active",
			"notas": "Detalle línea por línea de Payflow",
		},
		{
			"nombre_fuente": "Fincomercio",
			"tipo_fuente": "fincomercio",
			"periodicidad": "Mensual",
			"status": "Active",
			"notas": "Créditos y deducciones Fincomercio",
		},
		{
			"nombre_fuente": "Fondo FONGIGA",
			"tipo_fuente": "fondo_empleados",
			"periodicidad": "Mensual",
			"status": "Active",
			"notas": "M HOME FEBRERO 2026.xlsx - Aportes y créditos fondo",
		},
		{
			"nombre_fuente": "Libranzas Bancolombia",
			"tipo_fuente": "libranzas",
			"periodicidad": "Mensual",
			"status": "Active",
			"notas": "Deducciones de libranzas Bancolombia",
		},
		{
			"nombre_fuente": "Libranzas Compensar",
			"tipo_fuente": "libranzas",
			"periodicidad": "Mensual",
			"status": "Active",
			"notas": "Deducciones de libranzas Compensar",
		},
		{
			"nombre_fuente": "Libranzas Vivienda",
			"tipo_fuente": "libranzas",
			"periodicidad": "Mensual",
			"status": "Active",
			"notas": "Deducciones de libranzas crédito vivienda",
		},
		{
			"nombre_fuente": "SIESA Parametrizado",
			"tipo_fuente": "siesa",
			"periodicidad": "Eventual",
			"status": "Draft",
			"notas": "Exportaciones parametrizadas desde SIESA",
		},
		{
			"nombre_fuente": "GH Novedad Manual",
			"tipo_fuente": "gh_novedad",
			"periodicidad": "Eventual",
			"status": "Active",
			"notas": "Novedades registradas manualmente en HubGH",
		},
		{
			"nombre_fuente": "Novedad SST",
			"tipo_fuente": "sst",
			"periodicidad": "Eventual",
			"status": "Active",
			"notas": "Incapacidades y novedades de SST",
		},
		{
			"nombre_fuente": "Novedad Bienestar",
			"tipo_fuente": "bienestar",
			"periodicidad": "Eventual",
			"status": "Active",
			"notas": "Compromisos y alertas de Bienestar con impacto nómina",
		},
	]

	created = 0
	for data in sources:
		if not frappe.db.exists("Payroll Source Catalog", data["nombre_fuente"]):
			doc = frappe.get_doc({"doctype": "Payroll Source Catalog", **data})
			doc.insert(ignore_permissions=True)
			print(f"  → Created source: {data['nombre_fuente']}")
			created += 1

	return created


def seed_rule_catalog():
	"""Seed Payroll Rule Catalog with business rules from meetings."""
	import json

	rules = [
		{
			"codigo_regla": "HOME12-FIJO",
			"nombre_regla": "HOME 12 Auxilio Fijo",
			"descripcion_regla": "Auxilio fijo $110.000/mes para empleados HOME 12 con 6 PDV completos",
			"tipo_regla": "home12_fijo",
			"parametros": json.dumps({"amount": 110000, "pdv_count": 6, "currency": "COP"}),
			"aplica_a": "empleado",
			"activa": 1,
		},
		{
			"codigo_regla": "HOME12-PROP",
			"nombre_regla": "HOME 12 Proporcional por Incapacidad",
			"descripcion_regla": "Auxilio HOME 12 proporcional si hay incapacidad en el período",
			"tipo_regla": "home12_proporcional",
			"parametros": json.dumps({"base_amount": 110000, "proportional_on": "dias_laborados"}),
			"aplica_a": "empleado",
			"activa": 1,
		},
		{
			"codigo_regla": "AUX-DOM-NOCHE",
			"nombre_regla": "Auxilio Dominical Nocturno",
			"descripcion_regla": "Auxilio $7.000 por turno dominical después de 9:55PM",
			"tipo_regla": "auxilio_dominical",
			"parametros": json.dumps({"amount": 7000, "after_time": "21:55", "day": "sunday", "currency": "COP"}),
			"aplica_a": "empleado",
			"activa": 1,
		},
		{
			"codigo_regla": "TOPE-DESC-702K",
			"nombre_regla": "Tope Deducciones Payflow",
			"descripcion_regla": "Tope máximo de deducciones $702.000 según reporte Payflow",
			"tipo_regla": "tope_descuento",
			"parametros": json.dumps({"max_amount": 702000, "source": "payflow", "currency": "COP"}),
			"aplica_a": "empleado",
			"activa": 1,
		},
		{
			"codigo_regla": "SANITAS-PREM",
			"nombre_regla": "Sanitas Premium Devengo=Descuento",
			"descripcion_regla": "Plan Sanitas Premium: devengo $200.000 = descuento $200.000 (neto 0)",
			"tipo_regla": "sanitas_premium",
			"parametros": json.dumps({"devengo": 200000, "descuento": 200000, "currency": "COP"}),
			"aplica_a": "empleado",
			"activa": 1,
		},
		{
			"codigo_regla": "GAFAS-CONV",
			"nombre_regla": "Gafas Convenio",
			"descripcion_regla": "Convenio gafas: $200.000 subsidiado, excedente en cuotas",
			"tipo_regla": "gafas_convenio",
			"parametros": json.dumps({"subsidio": 200000, "cuotas_max": 6, "currency": "COP"}),
			"aplica_a": "empleado",
			"activa": 1,
		},
		{
			"codigo_regla": "PRESTAMO-EMP",
			"nombre_regla": "Préstamo Empresa",
			"descripcion_regla": "Reportar inicio, fin y cuotas de préstamos empresa",
			"tipo_regla": "prestamo_empresa",
			"parametros": json.dumps({"track_fields": ["fecha_inicio", "fecha_fin", "cuotas", "monto"]}),
			"aplica_a": "empleado",
			"activa": 1,
		},
		{
			"codigo_regla": "BONIF-PERD",
			"nombre_regla": "Pérdida de Bonificación",
			"descripcion_regla": "Registrar pérdida de bonificación según informe de Mónica",
			"tipo_regla": "bonificacion_perdida",
			"parametros": json.dumps({"source": "informe_monica", "requires_approval": True}),
			"aplica_a": "empleado",
			"activa": 1,
		},
		{
			"codigo_regla": "INC-LEGAL",
			"nombre_regla": "Incapacidad Legal",
			"descripcion_regla": "Reglas de cálculo para incapacidades legales (EG, AT)",
			"tipo_regla": "incapacidad_legal",
			"parametros": json.dumps({
				"eg_employer_days": 2,
				"eg_eps_from_day": 3,
				"at_arl_from_day": 1,
			}),
			"aplica_a": "empleado",
			"activa": 1,
		},
	]

	for data in rules:
		if not frappe.db.exists("Payroll Rule Catalog", data["codigo_regla"]):
			doc = frappe.get_doc({"doctype": "Payroll Rule Catalog", **data})
			doc.insert(ignore_permissions=True)
			print(f"  → Created rule: {data['codigo_regla']}")


def seed_current_period():
	"""Seed the current active payroll period (March 2026)."""
	period_data = {
		"nombre_periodo": "Marzo 2026 - Quincena 1",
		"ano": 2026,
		"mes": 3,
		"fecha_corte_inicio": "2026-03-01",
		"fecha_corte_fin": "2026-03-15",
		"status": "Active",
		"total_dias": 15,
		"dias_laborales": 11,
		"observaciones": "Primera quincena de marzo 2026",
	}

	# Check if any active period exists for this month
	existing = frappe.db.exists(
		"Payroll Period Config",
		{"ano": 2026, "mes": 3, "status": "Active"},
	)
	if not existing:
		doc = frappe.get_doc({"doctype": "Payroll Period Config", **period_data})
		doc.insert(ignore_permissions=True)
		print(f"  → Created period: {period_data['nombre_periodo']}")
