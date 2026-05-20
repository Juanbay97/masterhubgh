import frappe

from hubgh.access_profiles import apply_workspace_role_matrix


def execute():
	if not frappe.db.exists("DocType", "Workspace"):
		return

	logger = frappe.logger("hubgh.patches.phase9_workspace_role_unification")
	logger.info("phase9_workspace_role_unification:start")

	try:
		apply_workspace_role_matrix()
	except Exception:
		logger.error(
			"phase9_workspace_role_unification:engine_failed",
			extra={"error": frappe.get_traceback()},
		)
		# do NOT re-raise — partial success is preferable to blocking migrate.
		# per-workspace failures are already absorbed by apply_workspace_role_matrix
		# via its inner try/except; this outer except catches catastrophic engine
		# failures (e.g., module import errors).
		return

	frappe.db.commit()
	logger.info("phase9_workspace_role_unification:done")
