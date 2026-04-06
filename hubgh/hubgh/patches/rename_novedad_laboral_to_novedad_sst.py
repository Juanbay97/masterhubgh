import frappe


def execute():
	"""Rename legacy SST novelty storage to the new Novedad SST doctype.

	This patch preserves existing records by moving the physical table when needed
	and updating child rows that still point to the previous parenttype.
	"""

	old_table = "tabNovedad Laboral"
	new_table = "tabNovedad SST"

	if frappe.db.exists("DocType", "Novedad Laboral") and not frappe.db.exists("DocType", "Novedad SST"):
		frappe.rename_doc("DocType", "Novedad Laboral", "Novedad SST", force=True)

	old_exists = frappe.db.sql("SHOW TABLES LIKE %s", old_table)
	new_exists = frappe.db.sql("SHOW TABLES LIKE %s", new_table)

	if old_exists and not new_exists:
		frappe.db.sql(f"RENAME TABLE `{old_table}` TO `{new_table}`")

	if frappe.db.has_table("SST Seguimiento") and frappe.db.has_column("SST Seguimiento", "parenttype"):
		frappe.db.sql(
			"""
			UPDATE `tabSST Seguimiento`
			SET parenttype = 'Novedad SST'
			WHERE parenttype = 'Novedad Laboral'
			"""
		)

	if frappe.db.has_table("SST Alerta") and frappe.db.has_column("SST Alerta", "novedad"):
		legacy_refs = frappe.db.sql(
			"""
			SELECT name, novedad
			FROM `tabSST Alerta`
			WHERE novedad IS NOT NULL AND novedad != ''
			""",
			as_dict=True,
		)
		for row in legacy_refs:
			# Keep alert linked if the name exists in the new doctype table.
			if frappe.db.exists("Novedad SST", row.novedad):
				continue
			# If there is no target row, keep record untouched to avoid data loss.

	frappe.db.commit()
