# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""Endpoints whitelisted para el panel de Corrección de Datos del Candidato.

Reglas:
  - Permission check explícito en cada endpoint (no confiar solo en perms del
	DocType — el panel se invoca desde la ficha del Candidato).
  - El controller `CorreccionDatosCandidato` re-valida fase y rol en
	`validate`/`before_submit`; este módulo es la capa de transporte.
"""

from __future__ import annotations

import frappe
from frappe import _

from hubgh.hubgh.candidate_correction_service import (
	get_bank_certification_file,
	get_correction_phase,
)


_SOLICITAR_ROLES = {
	"HR Selection",
	"Gestión Humana",
	"GH - Bandeja General",
	"Gerente GH",
	"System Manager",
}
_CAMPOS_VALIDOS = {"email", "cedula", "cuenta_bancaria", "datos_personales"}

# Roles habilitados para borrado físico de documentos del candidato.
# Más restrictivo que _SOLICITAR_ROLES: solo GH y System Manager (irreversible).
_DELETE_DOC_ROLES = {
	"Gestión Humana",
	"GH - Bandeja General",
	"System Manager",
}


@frappe.whitelist()
def submit_candidate_correction(candidato: str, campo: str, valor_nuevo, motivo: str):
	"""Crea una `Correccion Datos Candidato`.

	- Fase `pre_contrato`: save + submit (aplica directo).
	- Fase `post_contrato`: solo save (queda pendiente de aprobación).
	"""
	_check_solicitar_permission()
	_validate_inputs(candidato, campo, valor_nuevo, motivo)

	valor_serializado = (
		valor_nuevo if isinstance(valor_nuevo, str) else frappe.as_json(valor_nuevo)
	)

	doc = frappe.get_doc(
		{
			"doctype": "Correccion Datos Candidato",
			"candidato": candidato,
			"campo_corregido": campo,
			"valor_nuevo": valor_serializado,
			"motivo": motivo.strip(),
		}
	)
	doc.insert(ignore_permissions=False)
	doc.reload()

	if doc.fase == "pre_contrato":
		doc.submit()
		return {
			"name": doc.name,
			"status": "applied",
			"afectados": frappe.parse_json(doc.afectados_resumen or "{}"),
		}

	# Fase post_contrato: avanzar el workflow a "Pendiente Aprobación".
	# El Workflow oficial sólo admite Borrador → Pendiente Aprobación vía la
	# acción "Solicitar Aprobación", por lo que debe hacerse acá (post-insert)
	# y no en `before_insert`, donde Frappe rechaza el salto inicial directo.
	if doc.workflow_state == "Borrador":
		from frappe.model.workflow import apply_workflow
		apply_workflow(doc, "Solicitar Aprobación")

	return {"name": doc.name, "status": "pending_approval", "afectados": None}


@frappe.whitelist()
def approve_correction(correccion_name: str):
	"""Aprueba (submit) una corrección post-contrato pendiente.

	El chequeo de rol aprobador lo hace el controller en `before_submit`. Acá
	solo validamos pre-condiciones de estado/fase para dar un error claro.
	"""
	doc = frappe.get_doc("Correccion Datos Candidato", correccion_name)
	if doc.docstatus != 0:
		frappe.throw(_("Solo se pueden aprobar correcciones en estado borrador"))
	if doc.fase != "post_contrato":
		frappe.throw(_("Solo correcciones post-contrato requieren aprobación"))
	doc.submit()  # before_submit valida el rol del aprobador
	return {
		"name": doc.name,
		"status": "applied",
		"afectados": frappe.parse_json(doc.afectados_resumen or "{}"),
	}


@frappe.whitelist()
def get_correction_phase_api(candidato: str):
	"""Le dice al UI si mostrar `Aplicar` o `Solicitar aprobación`."""
	_check_solicitar_permission()
	if not candidato:
		frappe.throw(_("Candidato requerido"))
	return {"fase": get_correction_phase(candidato)}


@frappe.whitelist()
def get_bank_cert_url(candidato: str):
	"""Devuelve el `file_url` de la certificación bancaria adjunta al Candidato.

	Permission check obligatorio: el usuario debe poder leer el Candidato.
	"""
	_check_solicitar_permission()
	if not candidato:
		frappe.throw(_("Candidato requerido"))
	if not frappe.has_permission("Candidato", "read", doc=candidato):
		frappe.throw(
			_("No tiene permisos para ver este candidato"), frappe.PermissionError
		)
	url = get_bank_certification_file(candidato)
	return {"file_url": url or None}


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _check_solicitar_permission():
	user_roles = set(frappe.get_roles(frappe.session.user))
	if not (user_roles & _SOLICITAR_ROLES):
		frappe.throw(
			_("No tiene permisos para solicitar correcciones"),
			frappe.PermissionError,
		)


@frappe.whitelist()
def delete_person_document(person_document_name: str, motivo: str):
	"""Elimina PERMANENTEMENTE un Person Document de un Candidato.

	Borra el registro `Person Document`, el `File` doc asociado y el archivo
	físico en disco. Operación irreversible — solo permitida en fase
	`pre_contrato`. Audit en `Comment` sobre el Candidato.

	Roles permitidos: `Gestión Humana`, `GH - Bandeja General`,
	`System Manager`. El motivo es obligatorio.
	"""
	_check_delete_doc_permission()
	_validate_delete_inputs(person_document_name, motivo)

	pdoc = frappe.get_doc("Person Document", person_document_name)
	if (pdoc.person_type or "") != "Candidato":
		frappe.throw(
			_("Solo se pueden eliminar documentos de Candidatos en pre-contratación")
		)
	candidato_name = pdoc.person
	if not candidato_name or not frappe.db.exists("Candidato", candidato_name):
		frappe.throw(_("Candidato no encontrado para el documento"))

	# Solo pre-contrato: si ya hay Ficha + Contrato submitted, bloquear.
	phase = get_correction_phase(candidato_name)
	if phase != "pre_contrato":
		frappe.throw(
			_("No se pueden eliminar documentos de candidatos ya contratados")
		)

	# Snapshot para auditoría (antes del delete).
	file_url = pdoc.file or ""
	audit_info = {
		"person_document": pdoc.name,
		"document_type": pdoc.document_type,
		"person_type": pdoc.person_type,
		"person": pdoc.person,
		"file": file_url,
		"uploaded_by": pdoc.get("uploaded_by"),
		"uploaded_on": str(pdoc.get("uploaded_on")) if pdoc.get("uploaded_on") else None,
	}

	frappe.db.savepoint("delete_person_doc")
	try:
		# 1) Borrar el Person Document (libera la referencia al archivo).
		frappe.delete_doc(
			"Person Document",
			pdoc.name,
			force=1,
			ignore_permissions=True,
		)

		# 2) Borrar el File doc asociado. Frappe elimina el archivo físico
		#    en `File.on_trash` si no hay otras referencias activas.
		file_doc_name = None
		if file_url:
			file_doc_name = frappe.db.get_value("File", {"file_url": file_url}, "name")
			if not file_doc_name:
				# Fallback: buscar por file_name (último segmento de la URL).
				file_name = file_url.rstrip("/").split("/")[-1]
				if file_name:
					file_doc_name = frappe.db.get_value(
						"File", {"file_name": file_name}, "name"
					)
			if file_doc_name:
				frappe.delete_doc(
					"File",
					file_doc_name,
					force=1,
					ignore_permissions=True,
				)

		# 3) Audit Comment en el Candidato.
		comment = frappe.get_doc(
			{
				"doctype": "Comment",
				"comment_type": "Info",
				"reference_doctype": "Candidato",
				"reference_name": candidato_name,
				"content": (
					f"[BORRADO PERMANENTE] Documento eliminado por "
					f"{frappe.session.user}. Tipo: {audit_info['document_type']}. "
					f"Motivo: {motivo.strip()}. "
					f"PersonDocument: {audit_info['person_document']}. "
					f"File: {audit_info['file'] or '(sin archivo)'}"
				),
			}
		).insert(ignore_permissions=True)

		frappe.db.commit()
		return {
			"deleted": audit_info["person_document"],
			"comment_id": comment.name,
			"file_deleted": bool(file_doc_name),
			"audit": audit_info,
		}
	except Exception:
		frappe.db.rollback(save_point="delete_person_doc")
		raise


def _check_delete_doc_permission():
	user_roles = set(frappe.get_roles(frappe.session.user))
	if not (user_roles & _DELETE_DOC_ROLES):
		frappe.throw(
			_("No tiene permisos para eliminar documentos"),
			frappe.PermissionError,
		)


def _validate_delete_inputs(person_document_name, motivo):
	if not person_document_name or not str(person_document_name).strip():
		frappe.throw(_("Documento requerido"))
	if not frappe.db.exists("Person Document", person_document_name):
		frappe.throw(
			_("Person Document no existe: {0}").format(person_document_name)
		)
	if not motivo or not str(motivo).strip():
		frappe.throw(_("Motivo es obligatorio"))


def _validate_inputs(candidato, campo, valor_nuevo, motivo):
	if not candidato:
		frappe.throw(_("Candidato requerido"))
	if not frappe.db.exists("Candidato", candidato):
		frappe.throw(_("Candidato no existe: {0}").format(candidato))
	if campo not in _CAMPOS_VALIDOS:
		frappe.throw(_("Campo no soportado: {0}").format(campo))
	if not motivo or not str(motivo).strip():
		frappe.throw(_("Motivo es obligatorio"))
	if valor_nuevo in (None, "", b""):
		frappe.throw(_("Valor nuevo es obligatorio"))
