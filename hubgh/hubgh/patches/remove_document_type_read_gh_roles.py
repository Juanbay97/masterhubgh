import frappe


GH_ROLES = ["Gestión Humana", "GH - Bandeja General", "Gerente GH"]


def execute():
	"""Manual rollback for document_type_read_gh_roles.py — NOT in patches.txt,
	run via `bench execute hubgh.patches.remove_document_type_read_gh_roles.execute`.
	Only deletes rows matching EXACTLY read=1/write=0/create=0/delete=0 so a
	broader permission granted afterwards is never touched.
	"""
	if not frappe.db.exists("DocType", "Document Type"):
		return

	for role in GH_ROLES:
		rows = frappe.get_all(
			"DocPerm",
			filters={"parent": "Document Type", "parenttype": "DocType", "role": role},
			fields=["name", "read", "write", "create", "delete", "permlevel"],
		)
		for row in rows:
			if (
				int(row.permlevel or 0) == 0
				and int(row.read or 0) == 1
				and int(row.write or 0) == 0
				and int(row.create or 0) == 0
				and int(row.delete or 0) == 0
			):
				frappe.delete_doc("DocPerm", row.name, ignore_permissions=True, force=True)

	frappe.clear_cache(doctype="Document Type")
	frappe.db.commit()
