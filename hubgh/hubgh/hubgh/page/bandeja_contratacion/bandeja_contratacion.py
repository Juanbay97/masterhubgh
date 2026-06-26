import frappe

from hubgh.hubgh.contratacion_service import (
    contract_candidates,
    create_contract,
    reject_candidate,
    submit_contract,
    validate_hr_access,
)
from hubgh.hubgh.document_service import (
    get_candidate_progress,
    upload_person_document,
)


__all__ = [
    "contract_candidates",
    "create_contract",
    "reject_candidate",
    "submit_contract",
    "upload_contratacion_document",
    "get_candidate_progress",
    "list_upload_document_types",
]


@frappe.whitelist()
def upload_contratacion_document(candidate, document_type, file_url, notes=None):
    """Upload a missing document for an incomplete candidate from the RRLL board.

    Role guard: HR Labor Relations or Gestión Humana only.
    Delegates to the shared upload_person_document core function.
    """
    validate_hr_access()
    numero_documento = frappe.db.get_value("Candidato", candidate, "numero_documento")
    doc = upload_person_document(
        "Candidato",
        candidate,
        document_type,
        file_url,
        notes,
        numero_documento=numero_documento,
    )
    return {"name": doc.name, "status": doc.status}


@frappe.whitelist()
def list_upload_document_types():
    """Return the document type names the RRLL upload picker should offer.

    Returns every active document type applicable to candidates (carnet, hoja de
    vida, EPS, SAGRILAFT, etc.), not just the internal operational subset, so RRLL
    can upload any required candidate document from the contratación board.
    Required-for-hiring types are listed first.
    """
    return frappe.get_all(
        "Document Type",
        filters={"is_active": 1, "applies_to": ["in", ["Candidato", "Ambos"]]},
        order_by="is_required_for_hiring desc, name asc",
        pluck="name",
    )
