"""E2E seeder for Corrección de Datos de Candidato.

Run inside the bench container:

    bench --site hubgh.local execute hubgh.tests._seed_correccion_e2e.seed
    bench --site hubgh.local execute hubgh.tests._seed_correccion_e2e.cleanup

Fixtures created (all idempotent):

* Users:
    - test.seleccion@hubgh-test.local  (roles: HR Selection, Gestión Humana, Selección)
    - test.gerente@hubgh-test.local    (roles: Gerente GH, Gestión Humana, System Manager)
  Password for both: ``Test123!``
* Candidatos:
    - 9000000001  -> pre-contrato                                  (CAND_PRE)
    - 9000000002  -> con Ficha Empleado + Contrato submitted       (CAND_POST)
    - 9000000003  -> con Person Document Certificación bancaria    (CAND_BANK)

NOTE on POST candidate: Contrato.submit() requires many siesa catalog FKs.
We bypass full controller validation by setting docstatus=1 directly via
db_set after a fast insert; this is acceptable for E2E fixtures only.
"""

from __future__ import annotations

import frappe

TEST_USERS = {
    "test.seleccion@hubgh-test.local": {
        "first_name": "TestSel",
        "last_name": "User",
        "password": "Hubgh-E2E-TestSeleccion-2026",
        "roles": ["HR Selection", "Gestión Humana", "Selección"],
    },
    "test.gerente@hubgh-test.local": {
        "first_name": "TestGer",
        "last_name": "User",
        "password": "Hubgh-E2E-TestGerente-2026",
        "roles": ["Gerente GH", "Gestión Humana", "System Manager"],
    },
}

PRE_CEDULA = "9000000001"
POST_CEDULA = "9000000002"
BANK_CEDULA = "9000000003"

ALL_CEDULAS = [PRE_CEDULA, POST_CEDULA, BANK_CEDULA]

BANK_DOC_TYPE = "Certificación bancaria (No mayor a 30 días)."


def _pick_first(doctype: str) -> str | None:
    rows = frappe.get_all(doctype, fields=["name"], limit_page_length=1)
    return rows[0].name if rows else None


def _seed_user(email: str, spec: dict) -> str:
    # Bypass password-strength validation; these are throwaway test users.
    frappe.flags.in_test = True
    if frappe.db.exists("User", email):
        user = frappe.get_doc("User", email)
    else:
        user = frappe.new_doc("User")
        user.email = email
        user.first_name = spec["first_name"]
        user.last_name = spec["last_name"]
        user.send_welcome_email = 0
        user.enabled = 1
        user.flags.ignore_password_policy = True
        user.insert(ignore_permissions=True)

    existing_roles = {r.role for r in (user.roles or [])}
    missing = [r for r in spec["roles"] if r not in existing_roles]
    if missing:
        for role in missing:
            user.append("roles", {"role": role})
        user.save(ignore_permissions=True)

    # Reset password each run so tests are deterministic.
    from frappe.utils.password import update_password
    update_password(email, spec["password"])
    return email


def _seed_candidato(cedula: str, email: str, first: str, pdv: str, ciudad: str) -> str:
    if frappe.db.exists("Candidato", cedula):
        return cedula
    doc = frappe.new_doc("Candidato")
    doc.tipo_documento = "Cedula"
    doc.numero_documento = cedula
    doc.nombres = first
    doc.primer_apellido = "Candidato"
    doc.apellidos = "Candidato"
    doc.email = email
    doc.celular = "3000000000"
    doc.direccion = "Calle Falsa 123"
    doc.ciudad = ciudad
    doc.pdv_destino = pdv
    doc.cargo_postulado = None
    doc.estado_proceso = "En Proceso"
    doc.insert(ignore_permissions=True)
    return doc.name


def _seed_ficha(cedula: str, pdv: str) -> str:
    if not frappe.db.exists("Ficha Empleado", cedula):
        doc = frappe.new_doc("Ficha Empleado")
        doc.cedula = cedula
        doc.nombres = "TestPost"
        doc.apellidos = "Candidato"
        doc.pdv = pdv
        doc.insert(ignore_permissions=True)
        name = doc.name
    else:
        name = cedula
    # Always (re-)link back to Candidato (idempotent)
    if frappe.db.exists("Candidato", cedula):
        frappe.db.set_value("Candidato", cedula, "persona", name)
    return name


def _seed_contrato(cedula: str, pdv: str) -> str:
    """Insert + force-submit a Contrato bypassing siesa catalog requirements."""
    existing = frappe.get_all("Contrato", filters={"candidato": cedula}, fields=["name", "docstatus"])
    if existing:
        if existing[0].docstatus != 1:
            frappe.db.set_value("Contrato", existing[0].name, "docstatus", 1)
            frappe.db.commit()
        return existing[0].name

    doc = frappe.new_doc("Contrato")
    doc.candidato = cedula
    doc.empleado = cedula  # Ficha Empleado.name == cedula
    doc.estado_contrato = "Pendiente"  # workflow start state
    doc.id_compania = "4"
    doc.numero_contrato = 1
    doc.tipo_contrato = "Indefinido"
    doc.fecha_ingreso = frappe.utils.today()
    doc.pdv_destino = pdv
    doc.numero_documento = cedula
    doc.nombres = "TestPost"
    doc.apellidos = "Candidato"
    doc.salario = 1500000
    doc.horas_trabajadas_mes = 220
    # Skip controller validation: insert then flip docstatus directly via SQL
    # to bypass workflow state-transition rules.
    doc.flags.ignore_validate = True
    doc.flags.ignore_mandatory = True
    doc.flags.ignore_workflow = True
    doc.insert(ignore_permissions=True, ignore_mandatory=True)
    frappe.db.sql(
        "UPDATE `tabContrato` SET docstatus=1, estado_contrato='Activo' WHERE name=%s",
        (doc.name,),
    )
    frappe.db.commit()
    return doc.name


def _seed_cert_bancaria(cedula: str) -> str:
    """Attach a dummy PDF as Person Document of type 'Certificación bancaria...'."""
    # 1. Create a minimal valid PDF (pypdf-parseable) as private File.
    # This is the smallest PDF that satisfies a startxref scan.
    pdf_payload = (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\n"
        b"xref\n0 4\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000052 00000 n \n"
        b"0000000101 00000 n \n"
        b"trailer<</Size 4/Root 1 0 R>>\n"
        b"startxref\n160\n"
        b"%%EOF\n"
    )
    file_doc = frappe.get_doc({
        "doctype": "File",
        "file_name": f"cert_bancaria_{cedula}.pdf",
        "is_private": 1,
        "content": pdf_payload,
    })
    file_doc.flags.ignore_validate = True
    file_doc.insert(ignore_permissions=True)

    existing = frappe.get_all(
        "Person Document",
        filters={"person": cedula, "document_type": BANK_DOC_TYPE},
        fields=["name"],
        limit_page_length=1,
    )
    if existing:
        # Update existing row to point at our PDF and mark as Aprobado.
        pdoc_name = existing[0].name
        frappe.db.set_value(
            "Person Document",
            pdoc_name,
            {
                "file": file_doc.file_url,
                "status": "Aprobado",
                "uploaded_by": "Administrator",
                "uploaded_on": frappe.utils.now_datetime(),
                "approved_by": "Administrator",
                "approved_on": frappe.utils.now_datetime(),
            },
        )
        return pdoc_name

    # 2. Create Person Document
    pdoc = frappe.new_doc("Person Document")
    pdoc.person_type = "Candidato"
    pdoc.person_doctype = "Candidato"
    pdoc.person = cedula
    pdoc.candidate = cedula
    pdoc.document_type = BANK_DOC_TYPE
    pdoc.status = "Aprobado"
    pdoc.file = file_doc.file_url
    pdoc.uploaded_by = "Administrator"
    pdoc.uploaded_on = frappe.utils.now_datetime()
    pdoc.flags.ignore_permissions = True
    pdoc.flags.ignore_mandatory = True
    pdoc.insert(ignore_permissions=True)
    return pdoc.name


def seed() -> None:
    pdv = _pick_first("Punto de Venta") or "1"
    ciudad = _pick_first("Ciudad") or "Barranquilla"

    for email, spec in TEST_USERS.items():
        _seed_user(email, spec)

    cand_pre = _seed_candidato(PRE_CEDULA, "test.pre@hubgh-test.local", "TestPre", pdv, ciudad)
    cand_post = _seed_candidato(POST_CEDULA, "test.post@hubgh-test.local", "TestPost", pdv, ciudad)
    cand_bank = _seed_candidato(BANK_CEDULA, "test.bank@hubgh-test.local", "TestBank", pdv, ciudad)

    # POST: ficha + contrato submitted
    _seed_ficha(POST_CEDULA, pdv)
    _seed_contrato(POST_CEDULA, pdv)
    # Force candidate into a state that surfaces it in bandeja_contratacion
    # (contract_candidates filters by STATE_LISTO_CONTRATAR / STATE_AFILIACION).
    frappe.db.set_value("Candidato", POST_CEDULA, "estado_proceso", "Listo para contratar")
    frappe.db.commit()

    # BANK: attach cert bancaria
    _seed_cert_bancaria(BANK_CEDULA)

    frappe.db.commit()
    print(f"SEEDED pdv={pdv} ciudad={ciudad}")
    print(f"  CAND_PRE={cand_pre}")
    print(f"  CAND_POST={cand_post}")
    print(f"  CAND_BANK={cand_bank}")


def cleanup() -> None:
    # Delete person_documents first (FK to Candidato)
    for cedula in ALL_CEDULAS:
        for pdoc in frappe.get_all("Person Document", filters={"person": cedula}, fields=["name", "file"]):
            try:
                file_url = pdoc.file
                frappe.delete_doc("Person Document", pdoc.name, force=1, ignore_permissions=True)
                if file_url:
                    files = frappe.get_all("File", filters={"file_url": file_url}, fields=["name"])
                    for f in files:
                        try:
                            frappe.delete_doc("File", f.name, force=1, ignore_permissions=True)
                        except Exception as e:
                            print(f"  warn: could not delete File {f.name}: {e}")
            except Exception as e:
                print(f"  warn: pdoc {pdoc.name}: {e}")

        # Contratos
        for contrato in frappe.get_all("Contrato", filters={"candidato": cedula}, fields=["name", "docstatus"]):
            try:
                if contrato.docstatus == 1:
                    frappe.db.set_value("Contrato", contrato.name, "docstatus", 2)
                    frappe.db.commit()
                frappe.delete_doc("Contrato", contrato.name, force=1, ignore_permissions=True)
            except Exception as e:
                print(f"  warn: contrato {contrato.name}: {e}")

        # Corrections referencing the candidato (these are submittable docs)
        for corr in frappe.get_all("Correccion Datos Candidato", filters={"candidato": cedula}, fields=["name", "docstatus"]):
            try:
                if corr.docstatus == 1:
                    frappe.db.set_value("Correccion Datos Candidato", corr.name, "docstatus", 2)
                    frappe.db.commit()
                frappe.delete_doc("Correccion Datos Candidato", corr.name, force=1, ignore_permissions=True)
            except Exception as e:
                print(f"  warn: corr {corr.name}: {e}")

        # Detach Ficha from Candidato (FK guard) then delete Ficha then Candidato
        if frappe.db.exists("Candidato", cedula):
            try:
                frappe.db.set_value("Candidato", cedula, "persona", None)
                frappe.db.commit()
            except Exception:
                pass
        if frappe.db.exists("Ficha Empleado", cedula):
            try:
                frappe.delete_doc("Ficha Empleado", cedula, force=1, ignore_permissions=True)
            except Exception as e:
                print(f"  warn: ficha {cedula}: {e}")
        if frappe.db.exists("Candidato", cedula):
            try:
                frappe.delete_doc("Candidato", cedula, force=1, ignore_permissions=True)
            except Exception as e:
                print(f"  warn: candidato {cedula}: {e}")

    for email in TEST_USERS.keys():
        if frappe.db.exists("User", email):
            try:
                frappe.delete_doc("User", email, force=1, ignore_permissions=True)
            except Exception as e:
                print(f"  warn: user {email}: {e}")

    frappe.db.commit()
    print("CLEANED")
