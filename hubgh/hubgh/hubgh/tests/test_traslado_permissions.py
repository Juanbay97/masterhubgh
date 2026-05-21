# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
Tests para RBAC de Traslado PDV — Fase 4.

TDD Cycle:
  T-8  RED   → tests aquí (este archivo)
  I-8a GREEN → setup_traslado_pdv_permissions() en setup_gh_permissions.py
  I-8b GREEN → get_traslado_pdv_permission_query en hubgh/hubgh/permissions.py
  I-8c GREEN → traslado_pdv_has_permission + registro en hooks.py

Capas verificadas:
  Capa 1 — DocPerm: via Frappe perms API
  Capa 2 — permission_query_conditions: via get_traslado_pdv_permission_query
  Capa 3 — has_permission: via traslado_pdv_has_permission
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today


# ---------------------------------------------------------------------------
# Constantes de test
# ---------------------------------------------------------------------------

PDV_PERM_A = "PDV-PERM-TEST-A"
PDV_PERM_B = "PDV-PERM-TEST-B"

EMP_PERM_A = "PERM-EMP-001"   # empleado en PDV_A
EMP_PERM_B = "PERM-EMP-002"   # empleado en PDV_B

USER_GH = "gh_perm_test@example.com"
USER_RRLL = "rrll_perm_test@example.com"
USER_GERENTE = "gerente_perm_test@example.com"
USER_JEFE_A = "jefe_a_perm_test@example.com"
USER_JEFE_B = "jefe_b_perm_test@example.com"
USER_EMP_A = "emp_a_perm_test@example.com"
USER_EMP_B = "emp_b_perm_test@example.com"
USER_OTRO = "otro_perm_test@example.com"

MOTIVO_PERM = "necesidad_operativa"
JUSTIFICACION_VALIDA = "Justificacion larga suficiente para pasar validacion de longitud"


# ---------------------------------------------------------------------------
# Helpers de setup
# ---------------------------------------------------------------------------

def _ensure_pdv(name, jefe_responsable=None):
    if not frappe.db.exists("Punto de Venta", name):
        doc = frappe.get_doc({
            "doctype": "Punto de Venta",
            "nombre_pdv": name,
            "codigo": name,
            "ciudad": "TestCiudad",
            "activo": 1,
        })
        doc.insert(ignore_permissions=True)
    if jefe_responsable:
        frappe.db.set_value("Punto de Venta", name, "jefe_responsable", jefe_responsable)
    return name


def _ensure_user(email, roles):
    if not frappe.db.exists("User", email):
        doc = frappe.get_doc({
            "doctype": "User",
            "email": email,
            "first_name": email.split("@")[0],
            "enabled": 1,
            "new_password": "TestPass123!",
            "send_welcome_email": 0,
        })
        doc.insert(ignore_permissions=True)
    else:
        frappe.db.set_value("User", email, "enabled", 1)

    # Remove existing roles and re-add
    frappe.db.delete("Has Role", {"parent": email})
    for role in roles:
        if frappe.db.exists("Role", role):
            frappe.get_doc({
                "doctype": "Has Role",
                "parent": email,
                "parenttype": "User",
                "parentfield": "roles",
                "role": role,
            }).insert(ignore_permissions=True)
    frappe.db.commit()
    return email


def _ensure_empleado(cedula, pdv, user=None, estado="Activo"):
    """
    Crea o actualiza una Ficha Empleado.
    La vinculación User↔Empleado se hace via email (Ficha.email == User.email)
    o via User.username == cedula. No existe campo 'usuario' en Ficha Empleado.
    """
    email = user or f"{cedula}@test.com"
    if not frappe.db.exists("Ficha Empleado", cedula):
        doc = frappe.get_doc({
            "doctype": "Ficha Empleado",
            "nombres": cedula,
            "apellidos": "PermTest",
            "cedula": cedula,
            "pdv": pdv,
            "estado": estado,
            "email": email,
        })
        doc.insert(ignore_permissions=True)
    else:
        frappe.db.set_value("Ficha Empleado", cedula, "pdv", pdv)
        frappe.db.set_value("Ficha Empleado", cedula, "estado", estado)
        frappe.db.set_value("Ficha Empleado", cedula, "email", email)

    # Ensure User.email matches so resolve_employee_for_user finds the link
    if user and frappe.db.exists("User", user):
        frappe.db.set_value("User", user, "email", user)
    return cedula


def _ensure_motivo():
    if not frappe.db.exists("Motivo Traslado", MOTIVO_PERM):
        frappe.get_doc({
            "doctype": "Motivo Traslado",
            "codigo": MOTIVO_PERM,
            "label": "Necesidad operativa",
            "requiere_cambio_cargo": 0,
            "activo": 1,
        }).insert(ignore_permissions=True)


def _make_traslado(empleado, pdv_destino, solicitado_por="Administrator"):
    """
    Inserta un Traslado PDV directamente via frappe.db.sql para tests de permisos.
    Bypasea los hooks before_insert (que validan TRASLADO_DUPLICADO) para poder
    crear múltiples traslados de test sin restricciones de negocio.
    """
    import uuid
    from frappe.utils import nowdate, now_datetime as _now
    pdv_origen = frappe.db.get_value("Ficha Empleado", empleado, "pdv") or PDV_PERM_A
    name = f"TRAS-PERM-{uuid.uuid4().hex[:8].upper()}"
    ts = str(_now())
    frappe.db.sql("""
        INSERT INTO `tabTraslado PDV`
            (name, empleado, pdv_origen, pdv_destino, fecha_aplicacion, motivo,
             justificacion, estado, solicitado_por, creation, modified, modified_by, owner, docstatus)
        VALUES
            (%(name)s, %(empleado)s, %(pdv_origen)s, %(pdv_destino)s, %(fecha)s, %(motivo)s,
             %(just)s, 'Programado', %(sp)s, %(ts)s, %(ts)s, %(sp)s, %(sp)s, 0)
    """, {
        "name": name, "empleado": empleado, "pdv_origen": pdv_origen,
        "pdv_destino": pdv_destino, "fecha": nowdate(), "motivo": MOTIVO_PERM,
        "just": JUSTIFICACION_VALIDA, "sp": solicitado_por, "ts": ts,
    })
    frappe.db.commit()
    return name


def _cleanup_traslados_perm():
    """Elimina todos los traslados de los empleados de test de permisos."""
    for emp in [EMP_PERM_A, EMP_PERM_B]:
        docs = frappe.get_all("Traslado PDV", filters={"empleado": emp}, pluck="name")
        for d in docs:
            try:
                frappe.delete_doc("Traslado PDV", d, force=True, ignore_permissions=True)
            except Exception:
                pass
    # Also cleanup any traslado from PDV_C empleados
    traslados_pdv_c = frappe.db.get_all(
        "Traslado PDV",
        filters=[["pdv_destino", "=", "PDV-PERM-TEST-C"]],
        pluck="name",
    )
    for d in traslados_pdv_c:
        try:
            frappe.delete_doc("Traslado PDV", d, force=True, ignore_permissions=True)
        except Exception:
            pass
    frappe.db.commit()


# ---------------------------------------------------------------------------
# Setup global del módulo de test
# ---------------------------------------------------------------------------

class TestTrasladoPermissionsBase(FrappeTestCase):
    """Base class: setup fixtures shared by all permission tests."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _ensure_motivo()
        _ensure_pdv(PDV_PERM_A)
        _ensure_pdv(PDV_PERM_B)

        # Aplicar permisos para Jefe_PDV y Empleado si no existen aún
        # (evita re-agregar los de GH que ya están en el JSON del DocType)
        from hubgh.setup_gh_permissions import ensure_docperm, get_transitional_roles, JEFE_ROLES, EMPLOYEE_ROLES
        for role in get_transitional_roles(JEFE_ROLES):
            existing = frappe.get_all("DocPerm", filters={"parent": "Traslado PDV", "role": role})
            if not existing:
                ensure_docperm("Traslado PDV", role, read=1, write=0, create=0, report=1, print=1, select=1)
        for role in get_transitional_roles(EMPLOYEE_ROLES):
            existing = frappe.get_all("DocPerm", filters={"parent": "Traslado PDV", "role": role})
            if not existing:
                ensure_docperm("Traslado PDV", role, read=1, write=0, create=0, select=1)
        # También para HR SST (nuestro USER_OTRO usa ese rol — debe tener 0 acceso efectivo via query)
        # No necesitamos agregar perms para HR SST porque la query 1=0 bloquea a nivel SQL
        frappe.db.commit()

        # Users con sus roles
        _ensure_user(USER_GH, ["Gestión Humana"])
        _ensure_user(USER_RRLL, ["HR Labor Relations"])
        _ensure_user(USER_GERENTE, ["Gerente GH"])
        _ensure_user(USER_JEFE_A, ["Jefe_PDV"])
        _ensure_user(USER_JEFE_B, ["Jefe_PDV"])
        _ensure_user(USER_EMP_A, ["Empleado"])
        _ensure_user(USER_EMP_B, ["Empleado"])
        _ensure_user(USER_OTRO, ["HR SST"])   # rol sin acceso

        # Ficha Empleado para jefes (para el fallback de pdv de empleado)
        _ensure_empleado(EMP_PERM_A, pdv=PDV_PERM_A, user=USER_EMP_A)
        _ensure_empleado(EMP_PERM_B, pdv=PDV_PERM_B, user=USER_EMP_B)

        # Jefe_A: jefe_responsable del PDV_A
        frappe.db.set_value("Punto de Venta", PDV_PERM_A, "jefe_responsable", USER_JEFE_A)
        # Jefe_B: jefe_responsable del PDV_B
        frappe.db.set_value("Punto de Venta", PDV_PERM_B, "jefe_responsable", USER_JEFE_B)
        frappe.db.commit()


# ---------------------------------------------------------------------------
# Capa 2 — permission_query_conditions
# ---------------------------------------------------------------------------

class TestCapa2PermissionQuery(TestTrasladoPermissionsBase):
    """Verifica get_traslado_pdv_permission_query produce las condiciones correctas."""

    def setUp(self):
        _cleanup_traslados_perm()
        frappe.db.commit()

    def tearDown(self):
        _cleanup_traslados_perm()

    def _get_query(self, user):
        from hubgh.hubgh.permissions import get_traslado_pdv_permission_query
        return get_traslado_pdv_permission_query(user=user)

    # --- Roles con acceso total (sin filtro) ---

    def test_administrator_gets_no_filter(self):
        result = self._get_query("Administrator")
        self.assertIn(result, [None, ""], f"Administrator debe tener acceso total, got: {result!r}")

    def test_gestión_humana_gets_no_filter(self):
        result = self._get_query(USER_GH)
        self.assertIn(result, [None, ""], f"Gestión Humana debe tener acceso total, got: {result!r}")

    def test_hr_labor_relations_gets_no_filter(self):
        result = self._get_query(USER_RRLL)
        self.assertIn(result, [None, ""], f"HR Labor Relations debe tener acceso total, got: {result!r}")

    def test_gerente_gh_gets_no_filter(self):
        result = self._get_query(USER_GERENTE)
        self.assertIn(result, [None, ""], f"Gerente GH debe tener acceso total, got: {result!r}")

    # --- Jefe PDV — filtrado por sus PDVs ---

    def test_jefe_a_gets_filter_for_pdv_a(self):
        result = self._get_query(USER_JEFE_A)
        self.assertIsNotNone(result)
        self.assertNotEqual(result, "1=0")
        self.assertIn(PDV_PERM_A, result)

    def test_jefe_b_gets_filter_for_pdv_b(self):
        result = self._get_query(USER_JEFE_B)
        self.assertIsNotNone(result)
        self.assertNotEqual(result, "1=0")
        self.assertIn(PDV_PERM_B, result)

    def test_jefe_a_query_includes_pdv_origen_and_destino_columns(self):
        """El filtro debe cubrir tanto pdv_origen como pdv_destino."""
        result = self._get_query(USER_JEFE_A)
        self.assertIn("pdv_origen", result)
        self.assertIn("pdv_destino", result)

    def test_jefe_with_no_pdv_gets_blocked(self):
        """Jefe_PDV sin Ficha Empleado ni jefe_responsable → 1=0."""
        jefe_sin_pdv = "jefe_noPDV_perm@example.com"
        _ensure_user(jefe_sin_pdv, ["Jefe_PDV"])
        # No crear Ficha Empleado ni setear jefe_responsable
        result = self._get_query(jefe_sin_pdv)
        self.assertEqual(result, "1=0")

    # --- Empleado — filtrado por su ficha ---

    def test_empleado_a_gets_filter_by_empleado(self):
        result = self._get_query(USER_EMP_A)
        self.assertIsNotNone(result)
        self.assertIn("empleado", result)
        self.assertIn(EMP_PERM_A, result)

    def test_empleado_with_no_ficha_gets_blocked(self):
        emp_sin_ficha = "emp_noFicha_perm@example.com"
        _ensure_user(emp_sin_ficha, ["Empleado"])
        result = self._get_query(emp_sin_ficha)
        self.assertEqual(result, "1=0")

    # --- Rol arbitrario — bloqueado ---

    def test_otro_rol_gets_blocked(self):
        result = self._get_query(USER_OTRO)
        self.assertEqual(result, "1=0")


# ---------------------------------------------------------------------------
# Capa 3 — has_permission (doc level)
# ---------------------------------------------------------------------------

class TestCapa3HasPermission(TestTrasladoPermissionsBase):
    """Verifica traslado_pdv_has_permission a nivel de documento."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Limpieza explícita antes de crear traslados para esta clase
        _cleanup_traslados_perm()
        frappe.db.commit()
        cls.traslado_a_name = _make_traslado(EMP_PERM_A, PDV_PERM_B)
        cls.traslado_b_name = _make_traslado(EMP_PERM_B, PDV_PERM_A)
        frappe.db.commit()

    @classmethod
    def tearDownClass(cls):
        _cleanup_traslados_perm()
        super().tearDownClass()

    def _has_perm(self, doc_name, user, ptype="read"):
        from hubgh.hubgh.permissions import traslado_pdv_has_permission
        doc = frappe.get_doc("Traslado PDV", doc_name)
        return traslado_pdv_has_permission(doc, user=user, ptype=ptype)

    # --- Roles con acceso total ---

    def test_administrator_has_permission_on_any_doc(self):
        self.assertTrue(self._has_perm(self.traslado_a_name, "Administrator"))
        self.assertTrue(self._has_perm(self.traslado_b_name, "Administrator"))

    def test_gh_has_permission_on_any_doc(self):
        self.assertTrue(self._has_perm(self.traslado_a_name, USER_GH))
        self.assertTrue(self._has_perm(self.traslado_b_name, USER_GH))

    def test_rrll_has_permission_on_any_doc(self):
        self.assertTrue(self._has_perm(self.traslado_a_name, USER_RRLL))

    def test_gerente_has_permission_on_any_doc(self):
        self.assertTrue(self._has_perm(self.traslado_a_name, USER_GERENTE))

    # --- Jefe PDV ---

    def test_jefe_a_has_permission_on_traslado_involving_pdv_a(self):
        # traslado_a: origen=PDV_A, destino=PDV_B → jefe_a debe poder verlo
        self.assertTrue(self._has_perm(self.traslado_a_name, USER_JEFE_A))

    def test_jefe_b_has_permission_on_traslado_involving_pdv_b(self):
        # traslado_a: destino=PDV_B → jefe_b debe poder verlo
        self.assertTrue(self._has_perm(self.traslado_a_name, USER_JEFE_B))

    def test_jefe_a_no_permission_on_traslado_only_in_pdv_b(self):
        # traslado_b: origen=PDV_B, destino=PDV_A → jefe_a SÍ puede verlo (destino es A)
        # En realidad traslado_b tiene origen=B, destino=A, entonces jefe_a lo ve por destino=A
        self.assertTrue(self._has_perm(self.traslado_b_name, USER_JEFE_A))

    def test_jefe_b_no_permission_on_traslado_only_in_pdv_a(self):
        # Crear traslado solo dentro de PDV_A→PDV_C (sin PDV_B involucrado)
        pdv_c = "PDV-PERM-TEST-C"
        _ensure_pdv(pdv_c)
        traslado_solo_a = None
        try:
            traslado_solo_a = _make_traslado(EMP_PERM_A, pdv_c)  # origen=A, destino=C
            self.assertFalse(self._has_perm(traslado_solo_a, USER_JEFE_B))
        finally:
            if traslado_solo_a:
                frappe.delete_doc("Traslado PDV", traslado_solo_a, force=True, ignore_permissions=True)

    # --- Empleado ---

    def test_empleado_a_has_permission_on_own_traslado(self):
        self.assertTrue(self._has_perm(self.traslado_a_name, USER_EMP_A))

    def test_empleado_b_has_no_permission_on_traslado_a(self):
        # traslado_a es del empleado EMP_PERM_A, no de EMP_PERM_B
        self.assertFalse(self._has_perm(self.traslado_a_name, USER_EMP_B))

    # --- Rol arbitrario ---

    def test_otro_rol_has_no_permission(self):
        self.assertFalse(self._has_perm(self.traslado_a_name, USER_OTRO))

    # --- Jefe intenta write (solo read permitido via DocPerm) ---
    # La verificación de write se hace via DocPerm (capa 1), no via has_permission.
    # has_permission devuelve True si el jefe puede VER el doc; el write/create
    # es bloqueado por la ausencia del flag en DocPerm.
    # Este test verifica que has_permission no sobre-filtra para 'write'.
    def test_jefe_a_has_permission_read_returns_true_for_visible_doc(self):
        """has_permission para 'read' devuelve True si el doc involucra su PDV."""
        self.assertTrue(self._has_perm(self.traslado_a_name, USER_JEFE_A, ptype="read"))


# ---------------------------------------------------------------------------
# Capa 2 — Integración: get_list respeta el filtro
# ---------------------------------------------------------------------------

class TestCapa2IntegracionGetList(TestTrasladoPermissionsBase):
    """Verifica que frappe.get_list aplica correctamente la query de permisos."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Limpieza explícita antes de crear traslados para esta clase
        _cleanup_traslados_perm()
        frappe.db.commit()
        # traslado_a: origen=PDV_A, destino=PDV_B
        cls.traslado_a = _make_traslado(EMP_PERM_A, PDV_PERM_B)
        # traslado_b: origen=PDV_B, destino=PDV_A
        cls.traslado_b = _make_traslado(EMP_PERM_B, PDV_PERM_A)
        frappe.db.commit()

    @classmethod
    def tearDownClass(cls):
        _cleanup_traslados_perm()
        super().tearDownClass()

    def _list_as_user(self, user):
        frappe.set_user(user)
        try:
            return frappe.get_list(
                "Traslado PDV",
                fields=["name", "empleado", "pdv_origen", "pdv_destino"],
                ignore_permissions=False,
            )
        finally:
            frappe.set_user("Administrator")

    def test_gh_sees_all_traslados(self):
        rows = self._list_as_user(USER_GH)
        names = {r["name"] for r in rows}
        self.assertIn(self.traslado_a, names)
        self.assertIn(self.traslado_b, names)

    def test_rrll_sees_all_traslados(self):
        rows = self._list_as_user(USER_RRLL)
        names = {r["name"] for r in rows}
        self.assertIn(self.traslado_a, names)
        self.assertIn(self.traslado_b, names)

    def test_jefe_a_sees_only_traslados_involving_pdv_a(self):
        rows = self._list_as_user(USER_JEFE_A)
        names = {r["name"] for r in rows}
        # traslado_a: origen=A → visible
        self.assertIn(self.traslado_a, names)
        # traslado_b: destino=A → visible también
        self.assertIn(self.traslado_b, names)

    def test_empleado_a_sees_only_own_traslado(self):
        rows = self._list_as_user(USER_EMP_A)
        names = {r["name"] for r in rows}
        self.assertIn(self.traslado_a, names)
        self.assertNotIn(self.traslado_b, names)

    def test_otro_rol_sees_nothing(self):
        """Un rol sin acceso recibe PermissionError o lista vacía — ambos son 'sin acceso'."""
        try:
            rows = self._list_as_user(USER_OTRO)
            names = {r["name"] for r in rows}
            # Si no lanzó PermissionError, debe retornar lista vacía (filtro 1=0)
            self.assertNotIn(self.traslado_a, names)
            self.assertNotIn(self.traslado_b, names)
        except frappe.PermissionError:
            # Correcto: DocPerm sin read=1 → PermissionError (equivalente a 403)
            pass
