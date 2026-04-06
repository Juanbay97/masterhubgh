import frappe
from frappe.model.document import Document

from hubgh.hubgh.candidate_states import STATE_AFILIACION, STATE_LISTO_CONTRATAR


AFFILIATION_DOCUMENT_TYPE_MAP = {
	"arl_certificado": "Afiliación ARL",
	"eps_certificado": "Afiliación EPS",
	"afp_certificado": "Afiliación AFP",
	"cesantias_certificado": "Afiliación Cesantías",
	"caja_certificado": "Afiliación Caja Compensación",
}


def ensure_affiliation_document_types():
	for document_name in AFFILIATION_DOCUMENT_TYPE_MAP.values():
		if frappe.db.exists("Document Type", document_name):
			frappe.db.set_value("Document Type", document_name, "is_active", 1, update_modified=False)
			continue

		doc_type = frappe.get_doc(
			{
				"doctype": "Document Type",
				"document_name": document_name,
				"is_active": 1,
				"applies_to": "Ambos",
				"is_required_for_hiring": 0,
				"is_optional": 1,
				"requires_approval": 0,
				"allowed_areas": [
					{"area_role": "HR Labor Relations"},
				],
			}
		)
		doc_type.insert(ignore_permissions=True)


class AfiliacionSeguridadSocial(Document):
	def validate(self):
		ensure_affiliation_document_types()
		self._sync_status_from_flags()

	def _sync_status_from_flags(self):
		required = [
			bool(self.eps_afiliado),
			bool(self.afp_afiliado),
			bool(self.cesantias_afiliado),
			bool(self.caja_afiliado),
			bool(self.arl_afiliado),
		]
		if bool(self.requiere_migracion):
			required.append(bool(self.migracion_completado))

		if all(required):
			self.estado_general = "Completado"
		elif any(required):
			self.estado_general = "En Proceso"
		else:
			self.estado_general = "Pendiente"

	def on_update(self):
		if not self.candidato:
			return

		self._sync_person_documents_from_certificates()

		if self.estado_general == "Completado":
			frappe.db.set_value("Candidato", self.candidato, "estado_proceso", STATE_LISTO_CONTRATAR)
		elif self.estado_general == "En Proceso":
			frappe.db.set_value("Candidato", self.candidato, "estado_proceso", STATE_AFILIACION)

	def _sync_person_documents_from_certificates(self):
		from hubgh.hubgh.document_service import ensure_person_document

		for cert_field, document_type in AFFILIATION_DOCUMENT_TYPE_MAP.items():
			file_url = self.get(cert_field)
			if not file_url:
				continue

			person_doc = ensure_person_document("Candidato", self.candidato, document_type)
			person_doc.file = file_url
			person_doc.status = "Aprobado"
			person_doc.save(ignore_permissions=True)
