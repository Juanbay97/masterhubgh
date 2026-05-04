# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
festivos — Detección de festivos colombianos.

Usa la librería `holidays` si está disponible; cae en fallback a un dict
hardcodeado que cubre 2026-2028 para garantizar correctitud sin dependencias.
"""

from __future__ import annotations

from datetime import date as _date

# Fallback hardcodeado para festivos colombianos 2026-2028
# Clave: "YYYY-MM-DD", Valor: nombre del festivo
CO_HOLIDAYS_HARDCODED: dict[str, str] = {
	# 2026
	"2026-01-01": "Año Nuevo",
	"2026-01-12": "Reyes Magos",
	"2026-03-23": "Día de San José",
	"2026-04-02": "Jueves Santo",
	"2026-04-03": "Viernes Santo",
	"2026-05-01": "Día del Trabajo",
	"2026-05-18": "Ascensión del Señor",
	"2026-06-08": "Corpus Christi",
	"2026-06-15": "Sagrado Corazón",
	"2026-06-29": "San Pedro y San Pablo",
	"2026-07-20": "Batalla de Boyacá",
	"2026-08-07": "Batalla de Boyacá (2)",
	"2026-08-17": "La Asunción de la Virgen",
	"2026-10-12": "Día de la Raza",
	"2026-11-02": "Todos los Santos",
	"2026-11-16": "Independencia de Cartagena",
	"2026-12-08": "Inmaculada Concepción",
	"2026-12-25": "Navidad",
	# 2027
	"2027-01-01": "Año Nuevo",
	"2027-01-11": "Reyes Magos",
	"2027-03-22": "Día de San José",
	"2027-03-25": "Jueves Santo",
	"2027-03-26": "Viernes Santo",
	"2027-05-01": "Día del Trabajo",
	"2027-05-10": "Ascensión del Señor",
	"2027-05-31": "Corpus Christi",
	"2027-06-07": "Sagrado Corazón",
	"2027-06-28": "San Pedro y San Pablo",
	"2027-07-20": "Batalla de Boyacá",
	"2027-08-07": "Batalla de Boyacá (2)",
	"2027-08-16": "La Asunción de la Virgen",
	"2027-10-18": "Día de la Raza",
	"2027-11-01": "Todos los Santos",
	"2027-11-15": "Independencia de Cartagena",
	"2027-12-08": "Inmaculada Concepción",
	"2027-12-25": "Navidad",
	# 2028
	"2028-01-01": "Año Nuevo",
	"2028-01-10": "Reyes Magos",
	"2028-03-20": "Día de San José",
	"2028-04-13": "Jueves Santo",
	"2028-04-14": "Viernes Santo",
	"2028-05-01": "Día del Trabajo",
	"2028-05-29": "Ascensión del Señor",
	"2028-06-19": "Corpus Christi",
	"2028-06-26": "Sagrado Corazón",
	"2028-07-03": "San Pedro y San Pablo",
	"2028-07-20": "Batalla de Boyacá",
	"2028-08-07": "Batalla de Boyacá (2)",
	"2028-08-21": "La Asunción de la Virgen",
	"2028-10-16": "Día de la Raza",
	"2028-11-06": "Todos los Santos",
	"2028-11-13": "Independencia de Cartagena",
	"2028-12-08": "Inmaculada Concepción",
	"2028-12-25": "Navidad",
}


def is_colombia_holiday(fecha: str) -> bool:
	"""
	Retorna True si fecha (YYYY-MM-DD) es festivo colombiano.

	Usa la librería `holidays` si está disponible; cae en fallback
	a CO_HOLIDAYS_HARDCODED para 2026-2028.

	Args:
		fecha: Fecha en formato "YYYY-MM-DD".

	Returns:
		True si es festivo, False en caso contrario.
	"""
	try:
		import holidays as _holidays_lib
		if _holidays_lib is None:
			raise ImportError("holidays is None")
		year = int(fecha[:4])
		co = _holidays_lib.Colombia(years=[year])
		from datetime import date as _d
		parts = fecha.split("-")
		d = _d(int(parts[0]), int(parts[1]), int(parts[2]))
		return d in co
	except (ImportError, AttributeError, TypeError):
		return fecha in CO_HOLIDAYS_HARDCODED
