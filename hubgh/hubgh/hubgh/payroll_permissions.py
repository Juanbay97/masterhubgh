import frappe

from hubgh.hubgh.people_ops_flags import resolve_payroll_novedades_v1_enabled
from hubgh.hubgh.role_matrix import canonicalize_roles, roles_have_any, user_has_any_role


# Role-based access matrix for payroll operations
PAYROLL_ROLE_MATRIX = {
	"operativo_nomina": {
		"roles": ["Gestión Humana", "Operativo Nómina"],
		"access": {
			"tc_tray": "full",
			"tp_tray": "full", 
			"import_batches": "full",
			"liquidation_cases": "read",
			"payroll_catalogs": "read",
			"employee_payroll_data": "read"
		},
		"description": "Full access to TC/TP trays and import operations"
	},
	"tp_nomina": {
		"roles": ["TP Nómina"],
		"access": {
			"tp_tray": "full",
			"import_batches": "read",
			"liquidation_cases": "read",
			"payroll_catalogs": "read",
			"employee_payroll_data": "read"
		},
		"description": "TP review and consolidated payroll access"
	},
	"sensible_rrll": {
		"roles": ["HR Labor Relations", "Gestión Humana"],
		"access": {
			"absence_validation": "full",
			"disciplinary_review": "full",
			"liquidation_cases": "validate",
			"employee_payroll_data": "sensitive_only",
			"payroll_catalogs": "read"
		},
		"description": "Absence validation and disciplinary oversight"
	},
	"clinico_sst": {
		"roles": ["HR SST"],
		"access": {
			"incapacity_support": "full",
			"medical_documents": "full",
			"absence_validation": "medical_only",
			"employee_payroll_data": "medical_only"
		},
		"description": "Incapacity support documents and medical oversight"
	},
	"validacion_contabilidad": {
		"roles": ["Contabilidad"],
		"access": {
			"liquidation_cases": "validate",
			"financial_review": "full",
			"payroll_exports": "read",
			"employee_payroll_data": "financial_only"
		},
		"description": "Financial validation and liquidation checks"
	},
	"administracion": {
		"roles": ["System Manager", "Administrator"],
		"access": {
			"all_operations": "full",
			"payroll_configuration": "full",
			"user_management": "full",
			"system_flags": "full"
		},
		"description": "Full administrative access to all payroll operations"
	}
}


def get_user_payroll_permissions(user=None):
	"""Get payroll permissions for a user based on their roles."""
	user = user or frappe.session.user
	
	if user == "Administrator":
		return PAYROLL_ROLE_MATRIX["administracion"]["access"]
	
	permissions = {}
	user_roles = canonicalize_roles(frappe.get_roles(user) or [])
	
	for config in PAYROLL_ROLE_MATRIX.values():
		if roles_have_any(user_roles, config["roles"]):
			permissions.update(config["access"])
	
	return permissions


def validate_payroll_access(operation, user=None, context=None):
	"""
	Validate if user has access to a specific payroll operation.
	
	Args:
		operation: String representing the operation (e.g., 'tc_tray', 'tp_tray')
		user: User to check (defaults to session user)
		context: Additional context for validation
		
	Returns:
		dict: {"allowed": bool, "reason": str, "level": str}
	"""
	user = user or frappe.session.user
	context = context or {}
	
	# Check if payroll module is enabled
	feature_enabled = _check_payroll_feature_flag()
	if not feature_enabled:
		return {
			"allowed": False,
			"reason": "Payroll module is disabled",
			"level": "feature_flag"
		}
	
	# Administrator always has access
	if user == "Administrator":
		return {
			"allowed": True,
			"reason": "Administrator access",
			"level": "admin"
		}
	
	# Get user permissions
	permissions = get_user_payroll_permissions(user)
	
	# Check specific operation
	if operation in permissions:
		access_level = permissions[operation]
		
		# Handle different access levels
		if access_level == "full":
			return {
				"allowed": True,
				"reason": f"Full access to {operation}",
				"level": "full"
			}
		elif access_level in ["read", "validate"]:
			return {
				"allowed": True,
				"reason": f"{access_level.title()} access to {operation}",
				"level": access_level
			}
		elif access_level.endswith("_only"):
			# Contextual access (e.g., medical_only, sensitive_only)
			return _validate_contextual_access(operation, access_level, user, context)
	
	# Check broader permissions
	if "all_operations" in permissions and permissions["all_operations"] == "full":
		return {
			"allowed": True,
			"reason": "Full administrative access",
			"level": "admin"
		}
	
	return {
		"allowed": False,
		"reason": f"No permission for operation: {operation}",
		"level": "denied"
	}


def _validate_contextual_access(operation, access_level, user, context):
	"""Validate contextual access based on access level restrictions."""
	
	if access_level == "sensitive_only":
		# Check if user can access sensitive data for this employee
		employee_id = context.get("employee_id")
		if not employee_id:
			return {
				"allowed": False,
				"reason": "Employee context required for sensitive access",
				"level": "context_missing"
			}
		
		# RRLL can access sensitive data for disciplinary cases
		if user_has_any_role(user, "RRLL", "Relaciones Laborales"):
			return {
				"allowed": True,
				"reason": "RRLL sensitive data access",
				"level": "sensitive"
			}
	
	elif access_level == "medical_only":
		# Medical data access for SST users
		if user_has_any_role(user, "SST", "Salud y Seguridad"):
			return {
				"allowed": True,
				"reason": "SST medical data access",
				"level": "medical"
			}
	
	elif access_level == "financial_only":
		# Financial data access for accounting
		if user_has_any_role(user, "Contabilidad", "Contador"):
			return {
				"allowed": True,
				"reason": "Accounting financial data access",
				"level": "financial"
			}
	
	return {
		"allowed": False,
		"reason": f"Insufficient context for {access_level}",
		"level": "context_denied"
	}


def _check_payroll_feature_flag():
	"""Check if payroll novedades v1 feature is enabled."""
	try:
		return resolve_payroll_novedades_v1_enabled()
	except Exception:
		return False


def enforce_payroll_access(operation, user=None, context=None):
	"""Raise a permission error when the current user lacks payroll access."""
	result = validate_payroll_access(operation, user=user, context=context)
	if result["allowed"]:
		return result

	reason = result.get("reason") or f"No permission for operation: {operation}"
	frappe.throw(reason, frappe.PermissionError)


def can_user_access_tc_tray(user=None):
	"""Check if user can access TC review tray."""
	result = validate_payroll_access("tc_tray", user=user)
	return result["allowed"]


def can_user_access_tp_tray(user=None):
	"""Check if user can access TP review tray."""
	result = validate_payroll_access("tp_tray", user=user)
	return result["allowed"]


def can_user_access_import_batches(user=None):
	"""Check if user can access import batches."""
	result = validate_payroll_access("import_batches", user=user)
	return result["allowed"]


def can_user_access_liquidation_cases(user=None):
	"""Check if user can access liquidation cases."""
	result = validate_payroll_access("liquidation_cases", user=user)
	return result["allowed"]


def can_user_view_employee_payroll(employee_id, user=None):
	"""Check if user can view payroll data for specific employee."""
	context = {"employee_id": employee_id}
	result = validate_payroll_access("employee_payroll_data", user=user, context=context)
	return result["allowed"]


@frappe.whitelist()
def get_user_payroll_access_summary(user=None):
	"""API endpoint to get current user's payroll access summary."""
	user = user or frappe.session.user
	
	permissions = get_user_payroll_permissions(user)
	access_summary = {}
	
	# Check each operation
	operations = [
		"tc_tray", "tp_tray", "import_batches", "liquidation_cases",
		"employee_payroll_data", "payroll_catalogs"
	]
	
	for op in operations:
		result = validate_payroll_access(op, user=user)
		access_summary[op] = {
			"allowed": result["allowed"],
			"level": result.get("level", "none"),
			"reason": result.get("reason", "")
		}
	
	return {
		"user": user,
		"permissions": permissions,
		"operations": access_summary,
		"feature_enabled": _check_payroll_feature_flag()
	}


# DocType Permission Query Functions (for hooks.py)

def get_payroll_import_batch_query(user=None):
	"""Permission query for Payroll Import Batch DocType."""
	user = user or frappe.session.user
	
	if not _check_payroll_feature_flag():
		return "1=0"  # Block all access if feature is disabled
	
	if user == "Administrator":
		return ""
	
	# Check if user can access import batches
	access_result = validate_payroll_access("import_batches", user=user)
	if not access_result["allowed"]:
		return "1=0"
	
	return ""  # Allow all if user has permission


def get_payroll_import_line_query(user=None):
	"""Permission query for Payroll Import Line DocType."""
	user = user or frappe.session.user
	
	if not _check_payroll_feature_flag():
		return "1=0"
	
	if user == "Administrator":
		return ""
	
	# Check TC/TP access
	tc_access = validate_payroll_access("tc_tray", user=user)
	tp_access = validate_payroll_access("tp_tray", user=user)
	
	if not (tc_access["allowed"] or tp_access["allowed"]):
		return "1=0"
	
	return ""


def get_payroll_liquidation_case_query(user=None):
	"""Permission query for Payroll Liquidation Case DocType."""
	user = user or frappe.session.user
	
	if not _check_payroll_feature_flag():
		return "1=0"
	
	if user == "Administrator":
		return ""
	
	# Check liquidation access
	access_result = validate_payroll_access("liquidation_cases", user=user)
	if not access_result["allowed"]:
		return "1=0"
	
	return ""


def payroll_import_batch_has_permission(doc, user=None, permission_type="read"):
	"""Has permission check for Payroll Import Batch."""
	user = user or frappe.session.user
	
	if not _check_payroll_feature_flag():
		return False
	
	if user == "Administrator":
		return True
	
	access_result = validate_payroll_access("import_batches", user=user)
	return access_result["allowed"]


def payroll_import_line_has_permission(doc, user=None, permission_type="read"):
	"""Has permission check for Payroll Import Line."""
	user = user or frappe.session.user
	
	if not _check_payroll_feature_flag():
		return False
	
	if user == "Administrator":
		return True
	
	# Check TC/TP access based on context
	if permission_type in ["write", "submit"]:
		# Write operations require specific tray access
		tc_access = validate_payroll_access("tc_tray", user=user)
		tp_access = validate_payroll_access("tp_tray", user=user)
		return tc_access["allowed"] or tp_access["allowed"]
	else:
		# Read operations are more permissive
		tc_access = validate_payroll_access("tc_tray", user=user)
		tp_access = validate_payroll_access("tp_tray", user=user)
		employee_access = validate_payroll_access("employee_payroll_data", user=user)
		return tc_access["allowed"] or tp_access["allowed"] or employee_access["allowed"]


def payroll_liquidation_case_has_permission(doc, user=None, permission_type="read"):
	"""Has permission check for Payroll Liquidation Case."""
	user = user or frappe.session.user
	
	if not _check_payroll_feature_flag():
		return False
	
	if user == "Administrator":
		return True
	
	access_result = validate_payroll_access("liquidation_cases", user=user)
	return access_result["allowed"]
