import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class PayrollImportBatch(Document):
	def before_insert(self):
		self.uploaded_by = frappe.session.user
		self.uploaded_on = now_datetime()
		self.status = "Pendiente"
		self.export_status = self.export_status or "Pendiente"
		self.run_id = (self.run_id or self.name or "").strip() or None
		self.run_label = (self.run_label or self.run_id or "").strip() or None
		self.run_source_count = int(self.run_source_count or 1)
		
		# Set nomina_period if not provided
		if not self.nomina_period and self.period:
			period_doc = frappe.get_doc("Payroll Period Config", self.period)
			self.nomina_period = period_doc.nombre_periodo or getattr(period_doc, "period_label", None) or period_doc.name

	def validate(self):
		if not self.source_file:
			frappe.throw("Debe adjuntar un archivo fuente.")
		if not self.source_type:
			frappe.throw("Debe seleccionar el tipo de fuente.")
		if not self.run_id:
			self.run_id = self.name or frappe.generate_hash(length=10)
		if not self.run_label:
			period_label = self.nomina_period or self.period or "Sin periodo"
			self.run_label = f"{period_label} · {self.run_id}"
		if not self.run_source_count:
			self.run_source_count = 1

		if self.run_id:
			existing_batches = frappe.get_all(
				"Payroll Import Batch",
				filters={"run_id": self.run_id, "name": ["!=", self.name or ""]},
				fields=["name", "period", "nomina_period"],
			)
			for existing in existing_batches:
				if (existing.get("period") or "") != (self.period or ""):
					frappe.throw("Todos los archivos agrupados en un mismo run deben pertenecer al mismo periodo.")
				if (existing.get("nomina_period") or "") != (self.nomina_period or ""):
					frappe.throw("Todos los lotes del run deben conservar el mismo contexto de nómina.")
			
	def on_update_after_submit(self):
		# Handle TC approval workflow
		if self.status == "Aprobado TC" and not self.aprobado_tc_por:
			self.db_set("aprobado_tc_por", frappe.session.user)
			self.db_set("aprobado_tc_fecha", now_datetime())
			
	def approve_tc(self):
		"""Approve batch for TC processing"""
		if self.status not in ["Completado", "Completado con errores", "Completado con duplicados"]:
			frappe.throw("El lote debe estar completado antes de aprobar TC.")
			
		self.status = "Aprobado TC"
		self.aprobado_tc_por = frappe.session.user
		self.aprobado_tc_fecha = now_datetime()
		self.save()
		
		# Update all lines to TC approved status
		frappe.db.sql("""
			UPDATE `tabPayroll Import Line` 
			SET tc_status = 'Aprobado'
			WHERE batch = %s AND status NOT IN ('Error', 'Duplicado')
		""", [self.name])
		
		return {"status": "success", "message": "Lote aprobado para TC"}
		
	def reject_tc(self, reason=None):
		"""Reject batch from TC processing"""
		self.status = "Rechazado TC"
		self.save()
		
		# Update all lines to TC rejected status
		frappe.db.sql("""
			UPDATE `tabPayroll Import Line` 
			SET tc_status = 'Rechazado', rule_notes = %s
			WHERE batch = %s AND status NOT IN ('Error', 'Duplicado')
		""", [reason or "Rechazado por TC", self.name])
		
		return {"status": "success", "message": "Lote rechazado por TC"}
