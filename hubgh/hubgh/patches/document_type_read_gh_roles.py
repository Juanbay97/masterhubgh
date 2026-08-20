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
	apply report): DocPerm defaults write/create/delete to 1, and
	ensure_docperm()'s cint_or_zero() comparison treats an unset (None) field
	as already-0 — so a single call passing write=0/create=0/delete=0 on a
	fresh row never calls setattr, and those fields get defaulted to 1 at
	insert. Workaround (ensure_docperm itself is untouched): call it twice —
	the first creates the row, the second re-reads it (real 1s now, not
	None) and correctly narrows write/create/delete to 0. Idempotent.
	"""
	if not frappe.db.exists("DocType", "Document Type"):
		return

	for role in GH_ROLES:
		ensure_docperm("Document Type", role, read=1)
		ensure_docperm("Document Type", role, read=1, write=0, create=0, delete=0, submit=0, cancel=0, amend=0)

	frappe.db.commit()
