# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
TDD — Phase 1.2: document_type_read_gh_roles patch idempotency.

NOTE: this site already has pre-existing (broader, full-CRUD) DocPerm rows for
these 3 roles on 'Document Type' — DB/fixture drift, unrelated to this patch
(absent from document_type.json; not a Custom DocPerm override either). Tests
are black-box and never delete pre-existing rows; they assert only what the
patch promises: read=1 ends up present, and row counts never grow.

KNOWN CAVEAT (verified, tracked as a follow-up, not fixed here — see PR1 apply
report): ensure_docperm(doctype, role, read=1) on a role with NO pre-existing
row silently grants full CRUD, not read-only, because DocPerm's own doctype
defaults write/create/delete/etc to 1 and ensure_docperm never zeroes flags it
wasn't asked to set. This affects several other ensure_docperm() call sites
too, not just this patch — a dedicated fix is intentionally out of scope here.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from hubgh.patches.document_type_read_gh_roles import GH_ROLES, execute as apply_patch


def _docperm_rows(role):
	return frappe.get_all(
		"DocPerm",
		filters={"parent": "Document Type", "parenttype": "DocType", "role": role, "permlevel": 0},
		fields=["name", "read", "write", "create", "delete"],
	)


class TestDocumentTypeReadGhRolesPatch(FrappeTestCase):

	def test_every_gh_role_ends_up_with_read_permission(self):
		apply_patch()
		for role in GH_ROLES:
			rows = _docperm_rows(role)
			self.assertTrue(rows, f"Expected at least one DocPerm row for role {role!r}")
			self.assertTrue(
				any(int(row.read or 0) == 1 for row in rows),
				f"Role {role!r} must have read=1 on Document Type after the patch runs",
			)

	def test_running_patch_twice_never_duplicates_rows(self):
		before_counts = {role: len(_docperm_rows(role)) for role in GH_ROLES}
		apply_patch()
		after_first_counts = {role: len(_docperm_rows(role)) for role in GH_ROLES}
		apply_patch()
		after_second_counts = {role: len(_docperm_rows(role)) for role in GH_ROLES}

		for role in GH_ROLES:
			self.assertGreaterEqual(
				after_first_counts[role], before_counts[role],
				f"First run must not remove any pre-existing DocPerm row for {role!r}",
			)
			self.assertEqual(
				after_second_counts[role], after_first_counts[role],
				f"Second run must not add a duplicate DocPerm row for {role!r}",
			)
