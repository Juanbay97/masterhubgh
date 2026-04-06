import frappe


def execute():
	settings = frappe.get_doc("System Settings")
	settings.allow_invalid_emails = 1
	settings.save(ignore_permissions=True)
	frappe.db.commit()
