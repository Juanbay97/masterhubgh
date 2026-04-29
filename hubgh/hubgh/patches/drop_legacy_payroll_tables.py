"""Drop tables del módulo de novedades de nómina legacy.

Parte de la reescritura del proceso de novedades. Los DocTypes y módulos
asociados se eliminaron del código; este patch retira las tablas y los
registros de DocType remanentes para que `bench migrate` quede consistente.

No se hace dump previo: el dueño del producto confirmó que no hay valor en
los datos históricos de payroll legacy en producción.
"""

import frappe


LEGACY_DOCTYPES = (
	"Payroll Import Line",
	"Payroll Import Batch",
	"Payroll Liquidation Case",
	"Payroll Novedad Type",
	"Payroll Rule Catalog",
	"Payroll Source Catalog",
	"Payroll Period Config",
)


def execute():
	for doctype in LEGACY_DOCTYPES:
		_drop_doctype(doctype)


def _drop_doctype(doctype: str) -> None:
	table_name = f"tab{doctype}"
	frappe.db.sql(f"DROP TABLE IF EXISTS `{table_name}`")

	if frappe.db.exists("DocType", doctype):
		frappe.delete_doc(
			"DocType",
			doctype,
			ignore_missing=True,
			ignore_permissions=True,
			force=True,
		)

	frappe.db.delete("Custom Field", {"dt": doctype})
	frappe.db.delete("Property Setter", {"doc_type": doctype})
	frappe.db.delete("DocField", {"parent": doctype})

	frappe.db.commit()
