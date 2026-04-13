import os

import frappe
from frappe.utils import cint, getdate


TIPOS_NOVEDAD_INCAPACIDAD = [
	"Incapacidad",
	"Incapacidad por enfermedad general",
]


class PayrollIncapacityTrayService:
	"""Operational tray for payroll incapacity recobro follow-up."""

	def get_tray_data(self, search=None, status=None, limit=200):
		rows = self._query_rows(search=search, status=status, limit=limit)
		items = [self._serialize_row(row) for row in rows]
		return {
			"status": "success",
			"items": items,
			"summary": {
				"total": len(items),
				"with_evidence": sum(1 for item in items if item.get("evidence_url")),
				"without_evidence": sum(1 for item in items if not item.get("evidence_url")),
			},
			"filters": {
				"search": search or None,
				"status": status or None,
				"limit": cint(limit or 200),
			},
			"attachment_policy": {
				"canonical_source": "Novedad SST.evidencia_incapacidad",
				"fallback_sources": [
					"Novedad SST.prorrogas_incapacidad[].adjunto",
					"File adjunto directamente a Novedad SST",
				],
			},
		}

	def _query_rows(self, search=None, status=None, limit=200):
		tipos_sql = ", ".join("'{}'".format((tipo or "").replace("'", "''")) for tipo in TIPOS_NOVEDAD_INCAPACIDAD)
		conditions = [
			"n.docstatus < 2",
			"n.fecha_inicio is not null",
			"n.fecha_fin is not null",
			f"(n.es_incapacidad = 1 or n.tipo_novedad in ({tipos_sql}) or (n.tipo_novedad = 'Accidente' and ifnull(n.accidente_tuvo_incapacidad, 0) = 1))",
		]
		params = {
			"limit": cint(limit or 200),
		}

		if status:
			conditions.append("n.estado = %(status)s")
			params["status"] = status

		search_value = (search or "").strip()
		if search_value:
			params["search"] = f"%{search_value}%"
			conditions.append("(" + " or ".join([
				"n.name like %(search)s",
				"n.empleado like %(search)s",
				"ifnull(fe.cedula, '') like %(search)s",
				"ifnull(fe.nombres, '') like %(search)s",
				"ifnull(fe.apellidos, '') like %(search)s",
			]) + ")")

		return frappe.db.sql(
			f"""
				select
					n.name,
					n.empleado,
					n.tipo_novedad,
					n.estado,
					n.fecha_inicio,
					n.fecha_fin,
					n.dias_incapacidad,
					n.diagnostico_corto,
					n.evidencia_incapacidad,
					fe.cedula,
					fe.nombres,
					fe.apellidos
				from `tabNovedad SST` n
				left join `tabFicha Empleado` fe on fe.name = n.empleado
				where {' and '.join(conditions)}
				order by n.fecha_inicio desc, n.modified desc
				limit %(limit)s
			""",
			params,
			as_dict=True,
		)

	def _serialize_row(self, row):
		evidence = self._resolve_evidence(row)
		persona = self._build_persona_label(row)
		return {
			"name": row.get("name"),
			"persona": persona,
			"cedula": row.get("cedula") or "",
			"empleado": row.get("empleado"),
			"tipo_novedad": row.get("tipo_novedad"),
			"estado": row.get("estado"),
			"fecha_inicio": row.get("fecha_inicio"),
			"fecha_fin": row.get("fecha_fin"),
			"dias_incapacidad": self._resolve_days(row),
			"diagnostico_corto": row.get("diagnostico_corto") or "",
			"evidence_url": evidence.get("file_url"),
			"evidence_label": evidence.get("label"),
			"evidence_source": evidence.get("source"),
		}

	def _build_persona_label(self, row):
		nombres = (row.get("nombres") or "").strip()
		apellidos = (row.get("apellidos") or "").strip()
		full_name = " ".join(part for part in [nombres, apellidos] if part).strip()
		return full_name or row.get("empleado") or "Sin persona"

	def _resolve_days(self, row):
		days = cint(row.get("dias_incapacidad") or 0)
		if days > 0:
			return days
		if row.get("fecha_inicio") and row.get("fecha_fin"):
			start = getdate(row.get("fecha_inicio"))
			end = getdate(row.get("fecha_fin"))
			return max((end - start).days + 1, 0)
		return 0

	def _resolve_evidence(self, row):
		principal = (row.get("evidencia_incapacidad") or "").strip()
		if principal:
			return {
				"file_url": principal,
				"label": self._build_file_label(principal),
				"source": "Novedad SST.evidencia_incapacidad",
			}

		prorroga = frappe.db.sql(
			"""
				select adjunto, fecha_seguimiento
				from `tabSST Seguimiento`
				where parent = %s
					and parenttype = 'Novedad SST'
					and parentfield = 'prorrogas_incapacidad'
					and ifnull(adjunto, '') != ''
				order by fecha_seguimiento desc, idx desc
				limit 1
			""",
			row.get("name"),
			as_dict=True,
		)
		if prorroga:
			file_url = (prorroga[0].get("adjunto") or "").strip()
			if file_url:
				return {
					"file_url": file_url,
					"label": self._build_file_label(file_url),
					"source": "Novedad SST.prorrogas_incapacidad[].adjunto",
				}

		attached_file = frappe.get_all(
			"File",
			filters={
				"attached_to_doctype": "Novedad SST",
				"attached_to_name": row.get("name"),
				"file_url": ["!=", ""],
			},
			fields=["file_url", "file_name"],
			order_by="creation desc",
			limit=1,
		)
		if attached_file:
			return {
				"file_url": attached_file[0].get("file_url"),
				"label": attached_file[0].get("file_name") or self._build_file_label(attached_file[0].get("file_url")),
				"source": "File adjunto directamente a Novedad SST",
			}

		return {"file_url": None, "label": None, "source": None}

	def _build_file_label(self, file_url):
		filename = os.path.basename((file_url or "").split("?")[0])
		return filename or "Descargar soporte"


def get_payroll_incapacity_tray_service():
	return PayrollIncapacityTrayService()
