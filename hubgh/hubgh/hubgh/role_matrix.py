import re
import unicodedata

import frappe


CANONICAL_ROLE_ALIASES = {
	"Gestión Humana": {
		"Gestión Humana",
		"Gestion Humana",
		"GH_Central",
		"GH Central",
	},
	"HR Selection": {
		"HR Selection",
		"Selección",
		"Seleccion",
	},
	"HR Labor Relations": {
		"HR Labor Relations",
		"Relaciones Laborales",
		"Relaciones_Laborales",
		"Relaciones Laborales GH",
		"RRLL",
		"Sensible RRLL",
		# Compatibilidad operativa: Gestión Humana históricamente cubría RL.
		"Gestión Humana",
		"Gestion Humana",
	},
	"HR Training & Wellbeing": {
		"HR Training & Wellbeing",
		"Formación y Bienestar",
		"Formacion y Bienestar",
	},
	"HR SST": {
		"HR SST",
		"SST",
		"Salud y Seguridad",
		"Clínico SST",
		"Clinico SST",
	},
	"Operativo Nómina": {
		"Operativo Nómina",
		"Operativo Nomina",
		"TC Nómina",
		"TC Nomina",
	},
	"TP Nómina": {
		"TP Nómina",
		"TP Nomina",
	},
	"Contabilidad": {
		"Contabilidad",
		"Contador",
		"Validación Contabilidad",
		"Validacion Contabilidad",
	},
	"Jefe_PDV": {
		"Jefe_PDV",
		"Jefe de tienda",
		"Jefe de Punto",
	},
	"Empleado": {"Empleado"},
	"Candidato": {"Candidato"},
	"GH - Bandeja General": {"GH - Bandeja General"},
	"GH - SST": {"GH - SST"},
	"GH - RRLL": {"GH - RRLL"},
	"System Manager": {"System Manager"},
}


# Mapeo de migración controlado: solo variantes legacy/ortográficas.
ROLE_MIGRATION_CANONICAL_MAP = {
	"Gestion Humana": "Gestión Humana",
	"GH_Central": "Gestión Humana",
	"GH Central": "Gestión Humana",
	"Selección": "HR Selection",
	"Seleccion": "HR Selection",
	"Relaciones Laborales": "HR Labor Relations",
	"Relaciones_Laborales": "HR Labor Relations",
	"RRLL": "HR Labor Relations",
	"Sensible RRLL": "HR Labor Relations",
	"SST": "HR SST",
	"Salud y Seguridad": "HR SST",
	"Clínico SST": "HR SST",
	"Clinico SST": "HR SST",
	"Formación y Bienestar": "HR Training & Wellbeing",
	"Formacion y Bienestar": "HR Training & Wellbeing",
	"Operativo Nomina": "Operativo Nómina",
	"TC Nómina": "Operativo Nómina",
	"TC Nomina": "Operativo Nómina",
	"TP Nomina": "TP Nómina",
	"Contador": "Contabilidad",
	"Validación Contabilidad": "Contabilidad",
	"Validacion Contabilidad": "Contabilidad",
	"Jefe de tienda": "Jefe_PDV",
	"Jefe de Punto": "Jefe_PDV",
}


AREA_ROLE_ALIASES = {
	"HR Selection": sorted(CANONICAL_ROLE_ALIASES["HR Selection"]),
	"HR Labor Relations": sorted(CANONICAL_ROLE_ALIASES["HR Labor Relations"]),
	"HR Training & Wellbeing": sorted(CANONICAL_ROLE_ALIASES["HR Training & Wellbeing"]),
	"HR SST": sorted(CANONICAL_ROLE_ALIASES["HR SST"]),
}


SHELL_ACCESS_CANONICAL_ROLES = {
	"Empleado",
	"Jefe_PDV",
	"Gestión Humana",
	"HR Selection",
	"HR Labor Relations",
	"HR Training & Wellbeing",
	"HR SST",
	"GH - Bandeja General",
	"GH - SST",
	"GH - RRLL",
}

GH_ADMIN_CANONICAL_ROLES = {
	"System Manager",
	"Gestión Humana",
	"GH - Bandeja General",
	"GH - SST",
	"GH - RRLL",
}

OPS_POINT_CANONICAL_ROLES = {"Jefe_PDV", "Empleado"}


def normalize_role_key(role_name):
	value = (role_name or "").strip().lower()
	if not value:
		return ""
	value = unicodedata.normalize("NFKD", value)
	value = "".join(ch for ch in value if not unicodedata.combining(ch))
	value = re.sub(r"[^a-z0-9]+", " ", value)
	return re.sub(r"\s+", " ", value).strip()


def _build_alias_index():
	index = {}
	for canonical, aliases in CANONICAL_ROLE_ALIASES.items():
		for role in set(aliases) | {canonical}:
			norm = normalize_role_key(role)
			if norm and norm not in index:
				index[norm] = canonical
	return index


_ROLE_ALIAS_INDEX = _build_alias_index()


def canonicalize_role(role_name):
	role = (role_name or "").strip()
	if not role:
		return ""
	return _ROLE_ALIAS_INDEX.get(normalize_role_key(role), role)


def canonicalize_roles(roles):
	return {canonicalize_role(r) for r in (roles or []) if r}


def expand_role_aliases(role_name):
	canonical = canonicalize_role(role_name)
	aliases = set(CANONICAL_ROLE_ALIASES.get(canonical, {canonical}))
	aliases.add(canonical)
	aliases.discard("")
	return aliases


def roles_have_any(user_roles, required_roles):
	user_roles = set(user_roles or [])
	if not user_roles or not required_roles:
		return False

	user_canonical = canonicalize_roles(user_roles)
	for required in required_roles:
		if not required:
			continue
		required_canonical = canonicalize_role(required)
		if required_canonical in user_canonical:
			return True
		if user_roles.intersection(expand_role_aliases(required_canonical)):
			return True
	return False


def user_has_any_role(user, *required_roles):
	roles = set(frappe.get_roles(user) or [])
	return roles_have_any(roles, required_roles)


def get_transitional_roles(canonical_roles):
	expanded = set()
	for role in canonical_roles or []:
		expanded.update(expand_role_aliases(role))
	return sorted(expanded)


def expand_roles_for_lookup(user_roles):
	expanded = set()
	for role in user_roles or []:
		expanded.update(expand_role_aliases(role))
	return sorted(expanded)
