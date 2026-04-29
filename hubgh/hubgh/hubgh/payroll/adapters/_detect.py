"""Detector de fuente por scoring multi-señal.

Cada adapter registra heurísticas en `catalogs.SOURCES` (filename_re,
sheets_subset, columns_subset). El detector las ejecuta y devuelve el
SourceSpec con mayor score. En empate o score < 2, devuelve `unknown`
para que el usuario seleccione manualmente.

Fase B sustituye el stub por una implementación real.
"""

from __future__ import annotations

from hubgh.hubgh.payroll import catalogs


def detect_source(file_meta) -> str:
	"""Devuelve el id de la fuente detectada.

	Fase A devuelve siempre `unknown`. Fase B implementa el scoring real.
	"""
	return "unknown"


def detect_period(file_meta) -> tuple[int, int] | None:
	"""Devuelve (year, month) extraído del archivo o None si no se pudo.

	Fase A devuelve None. Fase B implementa la lectura de cabecera CLONK.
	"""
	return None
