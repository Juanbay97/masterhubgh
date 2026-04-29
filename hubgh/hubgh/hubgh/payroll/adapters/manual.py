"""Adapter manual_internal — novedades cargadas a mano por el operador.

Este adapter no parsea archivos: sirve como punto de entrada para
novedades creadas desde el `payroll_workspace` (Fase E) cuando el usuario
agrega una línea sin subir un archivo.

Quedó acá como módulo registrado para que `_detect.py` lo conozca y
para mantener simétrica la lista de fuentes en `catalogs.SOURCES`.
"""

from __future__ import annotations

from typing import Iterator

from hubgh.hubgh.payroll.adapters import NovedadCanonica


SOURCE_ID = "manual_internal"


def matches(file_meta) -> int:
	# Nunca matchea un archivo: las novedades manuales no llegan por upload.
	return 0


def detect_period(workbook) -> tuple[int, int] | None:
	return None


def parse(workbook) -> Iterator[NovedadCanonica]:
	return iter(())
