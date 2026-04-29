"""Generación del Excel single-sheet de la prenómina.

Una sola hoja, una fila por empleado, columnas por categoría agregada.
La función pública es `build_single_sheet(novedades, params, employees,
period_label) -> bytes` que devuelve el .xlsx en memoria.
"""

from .single_sheet import build_single_sheet

__all__ = ["build_single_sheet"]
