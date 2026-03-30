import frappe

from hubgh.utils import run_canonical_person_identity_backfill


def execute():
	frappe.logger("hubgh.person_identity").info(
		"backfill_canonical_person_identity_by_document:start"
	)
	return run_canonical_person_identity_backfill(commit=True)
