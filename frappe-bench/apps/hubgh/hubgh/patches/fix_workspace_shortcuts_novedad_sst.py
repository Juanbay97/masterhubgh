import frappe


def execute():
	if not frappe.db.exists("DocType", "Workspace Shortcut"):
		return

	legacy_links = ["Novedad Laboral", "GH Novedad"]
	rows = frappe.get_all(
		"Workspace Shortcut",
		filters={"link_to": ["in", legacy_links], "type": "DocType"},
		fields=["name", "label", "link_to"],
	)

	for row in rows:
		frappe.db.set_value(
			"Workspace Shortcut",
			row.name,
			{
				"link_to": "Novedad SST",
				"label": "Novedad SST" if "Novedad" in (row.label or "") else (row.label or "Novedad SST"),
			},
		)

	# Clean obvious stale labels if any persisted as custom data.
	frappe.db.sql(
		"""
		UPDATE `tabWorkspace Shortcut`
		SET label = 'Novedad SST'
		WHERE type = 'DocType'
		  AND link_to = 'Novedad SST'
		  AND label IN ('Novedades Laborales', 'Novedades SST')
		"""
	)
