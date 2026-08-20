# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
TDD — Phase 1.2: document_type_read_gh_roles patch idempotency.

CORRECTION (gate feedback): the full-CRUD rows an earlier version found were
NOT "pre-existing drift" — they were created by this patch's own first-ever
run (ensure_docperm's fresh-row defect, see patch docstring), committed for
real by execute()'s own frappe.db.commit(). Verified against a genuinely
clean baseline: the corrected two-pass patch grants EXACTLY
read=1/write=0/create=0/delete=0. These tests assert that exact flag set.
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

	def test_fresh_grant_is_exactly_read_only(self):
		"""Starting from NO pre-existing row, the patch must grant EXACTLY
		read=1/write=0/create=0/delete=0 — not full CRUD."""
		for role in GH_ROLES:
			frappe.db.delete("DocPerm", {"parent": "Document Type", "parenttype": "DocType", "role": role})
		frappe.db.commit()
		frappe.clear_cache(doctype="Document Type")

		apply_patch()

		for role in GH_ROLES:
			rows = _docperm_rows(role)
			self.assertEqual(len(rows), 1, f"Expected exactly one DocPerm row for role {role!r}")
			row = rows[0]
			self.assertEqual(int(row.read or 0), 1, f"Role {role!r} must have read=1")
			self.assertEqual(int(row.write or 0), 0, f"Role {role!r} must NOT get write access")
			self.assertEqual(int(row.create or 0), 0, f"Role {role!r} must NOT get create access")
			self.assertEqual(int(row.delete or 0), 0, f"Role {role!r} must NOT get delete access")

	def test_running_patch_twice_never_duplicates_rows_or_widens_them(self):
		apply_patch()
		after_first = {role: _docperm_rows(role) for role in GH_ROLES}
		apply_patch()
		after_second = {role: _docperm_rows(role) for role in GH_ROLES}

		for role in GH_ROLES:
			self.assertEqual(len(after_second[role]), len(after_first[role]), f"Duplicated row for {role!r}")
			self.assertEqual(
				(after_second[role][0].read, after_second[role][0].write,
				 after_second[role][0].create, after_second[role][0].delete),
				(1, 0, 0, 0),
				f"Second run must not widen the grant for {role!r}",
			)
