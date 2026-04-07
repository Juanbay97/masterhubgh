import frappe

from hubgh.access_profiles import ensure_roles_and_profiles
from hubgh.utils import run_canonical_person_identity_backfill


def execute():
	frappe.logger("hubgh.person_identity").info(
		"backfill_canonical_person_identity_by_document:start"
	)
	ensure_roles_and_profiles()
	return run_canonical_person_identity_backfill(commit=True)
