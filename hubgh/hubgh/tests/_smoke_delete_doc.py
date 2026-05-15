"""Smoke runtime para verificar que delete_person_document borra el archivo fisico.

Ejecutar via:
    bench --site hubgh.local execute hubgh.tests._smoke_delete_doc.run

NO usa mocks. Toca DB real y filesystem real. Cleanup garantizado al final.
"""
import os
import frappe


CEDULA = "9000099999"
EMAIL = "test.deletedoc@hubgh-test.local"
ROLE_USER = "test.gh@hubgh-test.local"
ROLE_PASS = "Hubgh-E2E-TestGH-2026"


def _make_pdf_bytes() -> bytes:
    # PDF minimal-valido (similar al seeder e2e — necesario para pasar pypdf).
    return (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\n"
        b"xref\n"
        b"0 4\n"
        b"0000000000 65535 f \n"
        b"0000000009 00000 n \n"
        b"0000000052 00000 n \n"
        b"0000000095 00000 n \n"
        b"trailer<</Size 4/Root 1 0 R>>\n"
        b"startxref\n"
        b"140\n"
        b"%%EOF\n"
    )


def _ensure_user_with_gh_role():
    """Crea (si no existe) un User con rol Gestion Humana para impersonar."""
    if not frappe.db.exists("User", ROLE_USER):
        u = frappe.get_doc({
            "doctype": "User",
            "email": ROLE_USER,
            "first_name": "TestGH",
            "last_name": "Smoke",
            "enabled": 1,
            "user_type": "System User",
            "send_welcome_email": 0,
            "new_password": ROLE_PASS,
            "roles": [{"role": "Gestión Humana"}],
        })
        u.flags.ignore_password_policy = True
        u.insert(ignore_permissions=True)
    else:
        u = frappe.get_doc("User", ROLE_USER)
        if not any(r.role == "Gestión Humana" for r in u.roles):
            u.append("roles", {"role": "Gestión Humana"})
            u.save(ignore_permissions=True)
    frappe.db.commit()


def _ensure_candidato():
    """Crea Candidato pre-contrato (sin Ficha, sin Contrato)."""
    if frappe.db.exists("Candidato", CEDULA):
        return CEDULA
    # campos minimos del Candidato — ajustar si validate exige mas
    doc = frappe.get_doc({
        "doctype": "Candidato",
        "tipo_documento": "Cedula",
        "numero_documento": CEDULA,
        "nombres": "Smoke",
        "apellidos": "Delete",
        "primer_apellido": "Delete",
        "email": EMAIL,
    })
    doc.flags.ignore_mandatory = True
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    return CEDULA


def _create_person_document(candidato_name: str):
    """Sube un PDF dummy y crea (o reusa) un Person Document apuntando a él."""
    pdf_bytes = _make_pdf_bytes()
    file_name = f"smoke_delete_{CEDULA}.pdf"

    file_doc = frappe.get_doc({
        "doctype": "File",
        "file_name": file_name,
        "is_private": 1,
        "content": pdf_bytes,
        "decode": False,
    })
    file_doc.insert(ignore_permissions=True)
    file_url = file_doc.file_url
    file_disk_path = file_doc.get_full_path()

    # Buscar Person Document existente para reusar (Person Documents son auto-creados
    # con file vacío al insertar Candidato — set_value en lugar de duplicar).
    existing = frappe.get_all(
        "Person Document",
        filters={
            "person_type": "Candidato",
            "person": candidato_name,
            "document_type": "Examen Médico",
        },
        pluck="name",
        limit=1,
    )
    if existing:
        pdoc_name = existing[0]
        frappe.db.set_value("Person Document", pdoc_name, "file", file_url)
        frappe.db.commit()
    else:
        pdoc = frappe.get_doc({
            "doctype": "Person Document",
            "person_type": "Candidato",
            "person_doctype": "Candidato",
            "person": candidato_name,
            "document_type": "Examen Médico",
            "file": file_url,
        })
        pdoc.flags.ignore_mandatory = True
        pdoc.insert(ignore_permissions=True)
        pdoc_name = pdoc.name
        frappe.db.commit()

    return pdoc_name, file_doc.name, file_url, file_disk_path


def _cleanup():
    """Borrar todo lo creado por el smoke (idempotente)."""
    # Person Documents del candidato
    if frappe.db.exists("Candidato", CEDULA):
        for pd in frappe.get_all("Person Document", filters={"person": CEDULA}, pluck="name"):
            try:
                frappe.delete_doc("Person Document", pd, force=1, ignore_permissions=True)
            except Exception as e:
                print(f"skip PD {pd}: {e}")
        # Files huérfanos del candidato
        for f in frappe.get_all("File", filters={"file_name": ["like", f"smoke_delete_{CEDULA}%"]}, pluck="name"):
            try:
                frappe.delete_doc("File", f, force=1, ignore_permissions=True)
            except Exception as e:
                print(f"skip File {f}: {e}")
        try:
            frappe.delete_doc("Candidato", CEDULA, force=1, ignore_permissions=True)
        except Exception as e:
            print(f"skip Candidato: {e}")
    if frappe.db.exists("User", ROLE_USER):
        try:
            frappe.delete_doc("User", ROLE_USER, force=1, ignore_permissions=True)
        except Exception as e:
            print(f"skip User: {e}")
    frappe.db.commit()


def run():
    """Smoke completo: setup → verificar → borrar → reverificar → cleanup."""
    print("=" * 60)
    print("SMOKE: delete_person_document — borrado físico real")
    print("=" * 60)
    _cleanup()  # idempotencia

    # 1) Setup
    _ensure_user_with_gh_role()
    candidato_name = _ensure_candidato()
    pdoc_name, file_doc_name, file_url, file_disk_path = _create_person_document(candidato_name)
    print(f"[SETUP] Candidato={candidato_name}")
    print(f"[SETUP] PersonDocument={pdoc_name}")
    print(f"[SETUP] File doc={file_doc_name}  url={file_url}")
    print(f"[SETUP] Archivo en disco={file_disk_path}")

    # 2) Verificar archivo físico existe ANTES del borrado
    exists_before = os.path.exists(file_disk_path)
    print(f"[BEFORE] archivo físico existe en disco: {exists_before}")
    assert exists_before, f"El archivo {file_disk_path} no se creó — setup falló"

    # 3) Impersonar Gestión Humana y llamar el endpoint
    from hubgh.hubgh.api.correcciones import delete_person_document
    frappe.set_user(ROLE_USER)
    try:
        result = delete_person_document(
            person_document_name=pdoc_name,
            motivo="Smoke test: documento subido por error",
        )
        print(f"[DELETE] resultado: {result}")
    finally:
        frappe.set_user("Administrator")

    # 4) Verificar archivo físico NO existe DESPUÉS del borrado
    exists_after = os.path.exists(file_disk_path)
    print(f"[AFTER]  archivo físico existe en disco: {exists_after}")

    # 5) Verificar que el Person Document y el File ya no están en DB
    pdoc_in_db = frappe.db.exists("Person Document", pdoc_name)
    file_in_db = frappe.db.exists("File", file_doc_name)
    print(f"[AFTER]  Person Document en DB: {pdoc_in_db}")
    print(f"[AFTER]  File doc en DB: {file_in_db}")

    # 6) Verificar Comment auditable
    comments = frappe.get_all(
        "Comment",
        filters={
            "reference_doctype": "Candidato",
            "reference_name": candidato_name,
            "content": ["like", "%BORRADO PERMANENTE%"],
        },
        fields=["name", "content"],
        order_by="creation desc",
        limit=1,
    )
    audit_logged = bool(comments)
    print(f"[AFTER]  Audit Comment registrado: {audit_logged}")
    if audit_logged:
        print(f"[AUDIT]  {comments[0]['content'][:200]}")

    # 7) Cleanup
    _cleanup()

    # 8) Resultado
    ok = (not exists_after) and (not pdoc_in_db) and (not file_in_db) and audit_logged
    print("=" * 60)
    if ok:
        print("✅ SMOKE PASS — archivo borrado del disco + DB + audit registrado")
    else:
        print("❌ SMOKE FAIL — algo no se borró correctamente")
        print(f"   archivo_borrado={not exists_after}")
        print(f"   pdoc_borrado={not pdoc_in_db}")
        print(f"   file_doc_borrado={not file_in_db}")
        print(f"   audit_registrado={audit_logged}")
    print("=" * 60)
    return ok
