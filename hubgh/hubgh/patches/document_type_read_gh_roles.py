import frappe

from hubgh.setup_gh_permissions import ensure_docperm


GH_ROLES = ["Gestión Humana", "GH - Bandeja General", "Gerente GH"]


def execute():
	"""Grant read-only DocPerm on 'Document Type' to the HR-EXT GH roles.

	'HR Selection' already has read=1 (document_type.json). This closes the
	gap for the other roles authorized by
	seleccion_documentos._has_selection_access. Idempotent: ensure_docperm()
	only writes when a flag actually changes.

	KNOWN CAVEAT (verified, tracked as a follow-up, not fixed here — see PR1
	apply report): ensure_docperm(doctype, role, read=1) on a role with no
	pre-existing row silently grants full CRUD, not read-only, because
	DocPerm's own doctype defaults write/create/delete/etc to 1 and
	ensure_docperm never zeroes flags it wasn't asked to set. write=0/
	create=0/delete=0 are deliberately NOT passed here either, because this
	codebase's live sites already carry pre-existing, broader (full-CRUD)
	DocPerm rows for these 3 roles on 'Document Type' (unrelated DB/fixture
	drift) — zeroing those flags would revoke that pre-existing access.
	"""
	if not frappe.db.exists("DocType", "Document Type"):
		return

	for role in GH_ROLES:
		ensure_docperm("Document Type", role, read=1)

	frappe.db.commit()
