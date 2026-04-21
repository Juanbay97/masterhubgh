import frappe


def execute():
	"""Backfill missing cargo on Candidato with default 'Auxiliar de Cocina'.

	Runs once via bench migrate. Safe to re-run: only updates rows
	where cargo IS NULL or empty string.
	"""
	frappe.db.sql("""
		UPDATE `tabCandidato`
		SET cargo = 'Auxiliar de Cocina'
		WHERE (cargo IS NULL OR cargo = '')
	""")
	frappe.db.commit()
