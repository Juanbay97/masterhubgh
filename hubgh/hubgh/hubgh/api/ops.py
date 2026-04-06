"""Compatibility wrapper for legacy import paths.

Single source of truth: `hubgh.api.ops`.
Keep this module as explicit re-export only, pending future cleanup.
"""

from hubgh.api.ops import (  # noqa: F401
	create_novedad,
	export_cursos_pdf,
	export_docs_zip,
	get_person_docs,
	get_punto_lite,
	get_punto_novedades,
)

__all__ = [
	"get_punto_lite",
	"get_punto_novedades",
	"create_novedad",
	"get_person_docs",
	"export_docs_zip",
	"export_cursos_pdf",
]
