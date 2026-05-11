"""Smoke test del pipeline payroll v2 — para correr con `bench execute`.

NO se ejecuta en producción ni se usa desde la UI. Sirve para validar
end-to-end durante el rewrite. Borrar tras Fase H si querés.
"""

import json
import os
import shutil
import traceback

import frappe

from hubgh.hubgh.payroll import service


# Cédulas reales del CLONK febrero 2026 con sus jornadas conocidas.
SEED_EMPLOYEES = [
	{
		"cedula": "1128478178",
		"nombres": "Fausto Alonso",
		"apellidos": "Torres R",
		"tipo_jornada": "Tiempo Completo",  # CLONK lo trae como TC - Administración
		"salario": 2_400_000,
		"horas_trabajadas_mes": 220,
	},
	{
		"cedula": "1017127331",
		"nombres": "Maria Cenaida",
		"apellidos": "Bernal",
		"tipo_jornada": "Tiempo Completo",
		"salario": 1_750_905,  # SMMLV — elegible auxilio transporte
		"horas_trabajadas_mes": 220,
	},
	{
		"cedula": "1001343508",
		"nombres": "Ivan Camilo",
		"apellidos": "Gonzalez Raigoso",
		"tipo_jornada": "Tiempo Parcial",
		"salario": 1_200_000,
		"horas_trabajadas_mes": 120,
	},
]


def _ensure_seed_employees():
	created = []
	for spec in SEED_EMPLOYEES:
		emp_name = frappe.db.get_value("Ficha Empleado", {"cedula": spec["cedula"]}, "name")
		if not emp_name:
			emp_doc = frappe.get_doc(
				{
					"doctype": "Ficha Empleado",
					"nombres": spec["nombres"],
					"apellidos": spec["apellidos"],
					"cedula": spec["cedula"],
					"tipo_jornada": spec["tipo_jornada"],
					"estado": "Activo",
				}
			).insert(ignore_permissions=True, ignore_mandatory=True)
			emp_name = emp_doc.name
			created.append(emp_name)
		# Contrato activo. El workflow del Contrato NO permite saltar
		# "Pendiente → Activo" en el insert; se crea Pendiente y se
		# fuerza el cambio con db.set_value (sólo apto para smoke).
		if not frappe.db.exists("Contrato", {"empleado": emp_name, "estado_contrato": "Activo"}):
			contract_doc = frappe.get_doc(
				{
					"doctype": "Contrato",
					"empleado": emp_name,
					"numero_documento": spec["cedula"],
					"nombres": spec["nombres"],
					"apellidos": spec["apellidos"],
					"tipo_contrato": "Indefinido",
					"tipo_jornada": spec["tipo_jornada"],
					"fecha_ingreso": "2024-01-01",
					"salario": spec["salario"],
					"horas_trabajadas_mes": spec["horas_trabajadas_mes"],
					"estado_contrato": "Pendiente",
				}
			).insert(ignore_permissions=True, ignore_mandatory=True)
			frappe.db.set_value(
				"Contrato",
				contract_doc.name,
				"estado_contrato",
				"Activo",
				update_modified=False,
			)
			created.append(contract_doc.name)
	return created


def run_full(clonk: str = "/tmp/clonk_feb_2026.xlsx",
             payflow: str = "/tmp/payflow_feb_2026.xlsx",
             fincomercio: str = "/tmp/fincomercio_feb_2026.xlsx",
             fongiga: str = "/tmp/fongiga_feb_2026.xlsx") -> dict:
	"""Audit run con TODOS los archivos del periodo."""
	out = {}
	files_to_attach = [(clonk, "clonk"), (payflow, "payflow"),
	                   (fincomercio, "fincomercio"), (fongiga, "fongiga")]
	missing = [f for f, _ in files_to_attach if not os.path.exists(f)]
	if missing:
		return {"error": f"Faltan archivos: {missing}"}

	try:
		run_name = service.create_run(2026, 2)
		print(f"[audit] run_name = {run_name}")
		for path, label in files_to_attach:
			with open(path, "rb") as fh:
				file_doc = frappe.get_doc({
					"doctype": "File",
					"file_name": os.path.basename(path),
					"is_private": 1,
					"content": fh.read(),
					"attached_to_doctype": "Payroll Run",
					"attached_to_name": run_name,
				}).insert(ignore_permissions=True)
			rf = service.attach_file(run_name, file_doc.file_url, os.path.basename(path))
			detected = frappe.db.get_value("Payroll Run File", rf, "detected_source")
			print(f"[audit] {label}: file={rf} detected={detected}")

		print("[audit] process_run() …")
		result = service.process_run(run_name)
		totals = result.get("totals", {})
		print(f"[audit] totals = {json.dumps(totals, indent=2)}")
		out["run"] = run_name
		out["totals"] = totals

		by_status = dict(
			frappe.db.sql(
				"SELECT calc_status, COUNT(*) FROM `tabPayroll Novedad` WHERE run=%s GROUP BY calc_status",
				(run_name,),
			)
		)
		print(f"[audit] by_status = {by_status}")
		out["by_status"] = by_status

		by_source = dict(
			frappe.db.sql(
				"""SELECT f.detected_source, COUNT(n.name)
				FROM `tabPayroll Novedad` n
				JOIN `tabPayroll Run File` f ON f.name = n.source_file
				WHERE n.run = %s GROUP BY f.detected_source""",
				(run_name,),
			)
		)
		print(f"[audit] novedades_by_source = {by_source}")
		out["by_source"] = by_source

		# Sumas globales
		sums = frappe.db.sql(
			"""SELECT SUM(CASE WHEN computed_amount > 0 THEN computed_amount ELSE 0 END) as devengado,
				SUM(CASE WHEN computed_amount < 0 THEN computed_amount ELSE 0 END) as descontado,
				COUNT(DISTINCT empleado) as empleados_con_match,
				COUNT(DISTINCT documento_identidad) as empleados_total
			FROM `tabPayroll Novedad` WHERE run=%s""",
			(run_name,),
			as_dict=True,
		)
		print(f"[audit] sumas = {sums[0] if sums else 'n/a'}")
		out["sumas"] = sums[0] if sums else None

		print("[audit] export_run() …")
		try:
			export_url = service.export_run(run_name)
			out["export_file"] = export_url
			print(f"[audit] export_file = {export_url}")
		except Exception as exp_exc:
			out["export_error"] = str(exp_exc)
			print(f"[audit] export_run FAILED: {exp_exc}")
			traceback.print_exc()

		frappe.db.commit()
	except Exception as exc:
		out["error"] = str(exc)
		print(f"[audit] FAILED: {exc}")
		traceback.print_exc()

	print(f"[audit] DONE: {json.dumps(out, indent=2, default=str, ensure_ascii=False)}")
	return out


def run(clonk_local_path: str = "/tmp/clonk_feb_2026.xlsx") -> dict:
	"""Crea un Run, sube el CLONK, procesa y exporta. Reporta cada paso."""
	if not os.path.exists(clonk_local_path):
		return {"error": f"No existe el CLONK en {clonk_local_path}"}

	out: dict = {}

	try:
		# Best-effort mode: arrancamos sin sembrar empleados para
		# validar que el pipeline procesa todo lo que viene del archivo.
		print("[smoke] modo best-effort: NO se siembran empleados.")

		run_name = service.create_run(2026, 2)
		print(f"[smoke] run_name = {run_name}")
		out["run"] = run_name

		with open(clonk_local_path, "rb") as fh:
			file_doc = frappe.get_doc(
				{
					"doctype": "File",
					"file_name": "clonk_feb_2026.xlsx",
					"is_private": 1,
					"content": fh.read(),
					"attached_to_doctype": "Payroll Run",
					"attached_to_name": run_name,
				}
			).insert(ignore_permissions=True)

		rf_name = service.attach_file(run_name, file_doc.file_url, "clonk_feb_2026.xlsx")
		print(f"[smoke] run_file = {rf_name}")
		print(f"[smoke] detected_source = {frappe.db.get_value('Payroll Run File', rf_name, 'detected_source')}")

		print("[smoke] process_run() …")
		result = service.process_run(run_name)
		print(f"[smoke] totals = {json.dumps(result.get('totals'), indent=2, ensure_ascii=False)}")
		out["totals"] = result.get("totals")

		by_status = dict(
			frappe.db.sql(
				"SELECT calc_status, COUNT(*) FROM `tabPayroll Novedad` WHERE run=%s GROUP BY calc_status",
				(run_name,),
			)
		)
		print(f"[smoke] novedades por estado: {by_status}")
		out["by_status"] = by_status

		# Detalle de los 3 empleados sembrados
		seeded_summary = frappe.db.sql(
			"""
			SELECT documento_identidad, tipo_novedad, calc_status, computed_amount
			FROM `tabPayroll Novedad`
			WHERE run=%s AND documento_identidad IN ('1128478178', '1017127331', '1001343508')
			ORDER BY documento_identidad, tipo_novedad
			LIMIT 20
			""",
			(run_name,),
			as_dict=True,
		)
		print(f"[smoke] sample_seeded = {len(seeded_summary)} filas:")
		for r in seeded_summary:
			print(
				f"  {r['documento_identidad']} | {r['tipo_novedad']:30s} | "
				f"{r['calc_status']:10s} | ${r['computed_amount'] or 0:.2f}"
			)
		out["sample_seeded_count"] = len(seeded_summary)

		print("[smoke] export_run() …")
		try:
			export_url = service.export_run(run_name)
			out["export_file"] = export_url
			print(f"[smoke] export_file = {export_url}")
		except Exception as exp_exc:
			out["export_error"] = str(exp_exc)
			print(f"[smoke] export_run FAILED: {exp_exc}")
			traceback.print_exc()

		frappe.db.commit()
	except Exception as exc:
		out["error"] = str(exc)
		print(f"[smoke] FAILED: {exc}")
		traceback.print_exc()

	print(f"[smoke] DONE: {json.dumps(out, indent=2, ensure_ascii=False, default=str)}")
	return out
