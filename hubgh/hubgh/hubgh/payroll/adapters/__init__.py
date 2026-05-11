"""Adapters de fuentes externas de novedades de nómina.

Cada adapter expone `parse(file_handle) -> Iterator[NovedadCanonica]` y se
registra en `catalogs.SOURCES`. La selección por archivo la hace
`adapters._detect.detect_source`.

Fase A define solo el contrato. Fase B implementa CLONK + manual.
Fase F agrega Payflow, Fincomercio, FONGIGA y libranzas.
"""

from dataclasses import dataclass, field
from typing import Iterator, Protocol


@dataclass
class NovedadCanonica:
	"""DTO en memoria que un adapter devuelve por cada fila parseada.

	El enrichment posterior resuelve `empleado` y `contrato` desde el
	`documento_identidad`; los adapters NO consultan Frappe directamente.
	"""

	documento_identidad: str
	tipo_novedad: str           # id canónico de NOVEDAD_TYPES
	valor: float | None = None
	cantidad: float | None = None
	unidad: str = "cop"
	fecha_desde: str | None = None
	fecha_hasta: str | None = None
	raw_payload: dict = field(default_factory=dict)


class SourceAdapter(Protocol):
	SOURCE_ID: str

	def matches(self, file_meta) -> int:
		"""Score 0-3 sobre qué tan probable es que este adapter parse el archivo."""

	def detect_period(self, file_handle) -> tuple[int, int] | None:
		"""Extrae (year, month) del archivo si trae periodo en cabecera."""

	def parse(self, file_handle) -> Iterator[NovedadCanonica]:
		"""Itera filas canónicas; los errores van en `raw_payload['_error']`."""
