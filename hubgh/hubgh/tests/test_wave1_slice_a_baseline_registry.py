from frappe.tests.utils import FrappeTestCase

from hubgh.hubgh.governance.wave1_baseline_registry import (
	DOCTYPE_STRATEGY_BASELINE,
	DOCTYPE_DECISION_OPTIONS,
	DOCTYPE_DECISION_REGISTRY,
	ENTITY_OWNERSHIP_BASELINE,
	PROTECTED_NON_REGRESSION_SURFACES,
	ROLE_DIMENSION_MATRIX_BASELINE,
	ROLE_DIMENSIONS,
	RUNTIME_IMPACT_CONTRACT,
	SHARED_CATALOG_BASELINE,
	SLICE_ID,
	validate_doctype_decision_registry,
)
from hubgh.hubgh.role_matrix import canonicalize_role


class TestWave1SliceABaselineRegistry(FrappeTestCase):
	def test_slice_identity_and_runtime_contract_are_non_executing(self):
		self.assertEqual(SLICE_ID, "W1-S1A")
		self.assertTrue(all(flag is False for flag in RUNTIME_IMPACT_CONTRACT.values()))

	def test_role_matrix_dimensions_are_complete_and_valid(self):
		expected_dimensions = ("D1", "D2", "D3", "D4", "D5", "D6", "D7")
		self.assertEqual(ROLE_DIMENSIONS, expected_dimensions)

		allowed = {"N", "R", "W", "M"}
		for canonical_role, role_def in ROLE_DIMENSION_MATRIX_BASELINE.items():
			dimensions = role_def["dimensions"]
			self.assertEqual(tuple(dimensions.keys()), expected_dimensions, canonical_role)
			self.assertTrue(set(dimensions.values()).issubset(allowed), canonical_role)

	def test_role_aliases_canonicalize_to_declared_roles(self):
		for canonical_role, role_def in ROLE_DIMENSION_MATRIX_BASELINE.items():
			self.assertEqual(canonicalize_role(canonical_role), canonical_role)
			for alias in role_def["aliases"]:
				self.assertEqual(canonicalize_role(alias), canonical_role)

	def test_entity_catalog_and_doctype_baselines_have_expected_coverage(self):
		self.assertEqual(len(ENTITY_OWNERSHIP_BASELINE), 9)
		for entity_key, payload in ENTITY_OWNERSHIP_BASELINE.items():
			self.assertTrue(payload.get("anchor_artifacts"), entity_key)
			self.assertTrue(payload.get("owner_area"), entity_key)
			self.assertTrue(payload.get("lifecycle_stage"), entity_key)

		self.assertEqual(len(SHARED_CATALOG_BASELINE), 6)
		for family_key, payload in SHARED_CATALOG_BASELINE.items():
			self.assertTrue(payload.get("owner"), family_key)
			self.assertTrue(payload.get("backup_owner"), family_key)
			self.assertTrue(payload.get("stable_keys_required") is True, family_key)

		self.assertEqual(len(DOCTYPE_STRATEGY_BASELINE), 9)
		for strategy_key, payload in DOCTYPE_STRATEGY_BASELINE.items():
			self.assertTrue(payload.get("artifacts"), strategy_key)
			self.assertTrue(payload.get("decision"), strategy_key)
			self.assertTrue(payload.get("guardrail"), strategy_key)

	def test_non_regression_surface_statements_cover_protected_flows(self):
		self.assertEqual(len(PROTECTED_NON_REGRESSION_SURFACES), 4)
		combined = " ".join(PROTECTED_NON_REGRESSION_SURFACES).lower()
		self.assertIn("onboarding", combined)
		self.assertIn("persona 360", combined)
		self.assertIn("punto 360", combined)
		self.assertIn("bandeja", combined)

	def test_doctype_decision_registry_is_complete_and_valid(self):
		self.assertGreaterEqual(len(DOCTYPE_DECISION_REGISTRY), 12)
		for doctype, payload in DOCTYPE_DECISION_REGISTRY.items():
			self.assertTrue(doctype)
			self.assertIn(payload.get("decision"), DOCTYPE_DECISION_OPTIONS)
			self.assertTrue(payload.get("domain"))
			self.assertTrue(payload.get("justification"))
			self.assertTrue(payload.get("rollback_strategy"))

		validation = validate_doctype_decision_registry()
		self.assertTrue(validation["valid"])
		self.assertEqual(validation["issues"], [])
		self.assertEqual(validation["total"], len(DOCTYPE_DECISION_REGISTRY))
