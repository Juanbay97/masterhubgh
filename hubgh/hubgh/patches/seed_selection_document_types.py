import frappe

from hubgh.hubgh.selection_document_types import sync_selection_document_types, sync_selection_workspace_shortcut


def execute():
	if not frappe.db.exists("DocType", "Document Type"):
		return

	sync_selection_document_types()
	sync_selection_workspace_shortcut()
	frappe.db.commit()
