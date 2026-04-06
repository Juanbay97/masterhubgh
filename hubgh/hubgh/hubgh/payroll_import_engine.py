"""
Payroll Import Engine - Multi-source file parser and normalizer.

Supports:
- CLONK (3 sheets: Resumen horas, Detalle diario, Ausentismos)
- Payflow (future)
- Fincomercio (future)
- Fondo FONGIGA (future)
- Libranzas (future)
"""

import json
from datetime import datetime
import hashlib

import frappe
from frappe.utils import now_datetime

from hubgh.hubgh.payroll_permissions import enforce_payroll_access


# =============================================================================
# CLONK Parser
# =============================================================================

# Column mappings for CLONK sheets (based on real file analysis)
CLONK_RESUMEN_COLUMNS = {
	"documento": ["cedula", "documento", "doc", "id"],
	"nombre": ["nombre", "empleado", "name"],
	"hd": ["hd", "hora diurna", "horas diurnas"],
	"hn": ["hn", "hora nocturna", "horas nocturnas"],
	"hfd": ["hfd", "hora festivo diurna"],
	"hfn": ["hfn", "hora festivo nocturna"],
	"hed": ["hed", "hora extra diurna", "horas extras diurnas"],
	"hen": ["hen", "hora extra nocturna", "horas extras nocturnas"],
	"hefd": ["hefd", "hora extra festivo diurna"],
	"hefn": ["hefn", "hora extra festivo nocturna"],
	"nr": ["nr", "novedad registrada"],
	"nnr": ["nnr", "novedad no registrada"],
	"dnr": ["dnr", "dia no registrado", "días no registrados"],
}

CLONK_AUSENTISMO_COLUMNS = {
	"documento": ["cedula", "documento", "doc", "id"],
	"nombre": ["nombre", "empleado"],
	"tipo_ausencia": ["tipo", "ausencia", "tipo ausencia", "motivo"],
	"fecha_inicio": ["fecha inicio", "inicio", "desde"],
	"fecha_fin": ["fecha fin", "fin", "hasta"],
	"dias": ["dias", "días", "cantidad"],
}


def normalize_column_name(col):
	"""Normalize column name for matching."""
	if col is None:
		return ""
	return str(col).strip().lower().replace("_", " ")


def find_column_index(headers, possible_names):
	"""Find column index matching any of the possible names."""
	for idx, header in enumerate(headers):
		normalized = normalize_column_name(header)
		for name in possible_names:
			if name in normalized or normalized in name:
				return idx
	return None


def parse_clonk_file(file_path, batch_name):
	"""
	Parse CLONK Excel file with 3 sheets.
	Returns list of normalized PayrollImportLine dicts.
	"""
	try:
		import openpyxl
	except ImportError:
		frappe.throw("openpyxl no está instalado. Ejecute: pip install openpyxl")

	lines = []
	errors = []

	try:
		wb = openpyxl.load_workbook(file_path, data_only=True)
	except Exception as e:
		frappe.throw(f"Error al abrir archivo CLONK: {e}")

	sheet_names = wb.sheetnames

	# Parse each sheet
	for sheet_name in sheet_names:
		sheet = wb[sheet_name]
		sheet_lower = sheet_name.lower()

		if "resumen" in sheet_lower or "horas" in sheet_lower:
			sheet_lines, sheet_errors = parse_clonk_resumen_sheet(sheet, sheet_name, batch_name)
		elif "ausent" in sheet_lower or "novedad" in sheet_lower:
			sheet_lines, sheet_errors = parse_clonk_ausentismo_sheet(sheet, sheet_name, batch_name)
		elif "detalle" in sheet_lower or "diario" in sheet_lower:
			# Detalle diario - skip for now, complex structure
			continue
		else:
			# Unknown sheet, skip
			continue

		lines.extend(sheet_lines)
		errors.extend(sheet_errors)

	wb.close()
	return lines, errors


def parse_clonk_resumen_sheet(sheet, sheet_name, batch_name):
	"""Parse CLONK 'Resumen horas' sheet."""
	lines = []
	errors = []

	rows = list(sheet.iter_rows(values_only=True))
	if len(rows) < 2:
		return lines, errors

	# Find header row (first row with data)
	headers = rows[0]
	col_map = {}
	for field, possible_names in CLONK_RESUMEN_COLUMNS.items():
		idx = find_column_index(headers, possible_names)
		if idx is not None:
			col_map[field] = idx

	if "documento" not in col_map:
		errors.append({"sheet": sheet_name, "error": "No se encontró columna de documento"})
		return lines, errors

	# Parse data rows
	for row_num, row in enumerate(rows[1:], start=2):
		doc_value = row[col_map["documento"]] if col_map.get("documento") is not None else None
		if not doc_value:
			continue

		employee_id = str(doc_value).strip()
		employee_name = str(row[col_map.get("nombre", 0)] or "").strip() if col_map.get("nombre") else ""

		# Extract hour types
		hour_types = ["hd", "hn", "hfd", "hfn", "hed", "hen", "hefd", "hefn", "nr", "nnr", "dnr"]
		for hour_type in hour_types:
			if hour_type not in col_map:
				continue
			value = row[col_map[hour_type]]
			if not value or value == 0:
				continue

			try:
				quantity = float(value)
			except (ValueError, TypeError):
				continue

			if quantity <= 0:
				continue

			# Map hour type to novedad code
			novedad_code = hour_type.upper()

			lines.append({
				"batch": batch_name,
				"row_number": row_num,
				"status": "Pendiente",
				"employee_id": employee_id,
				"employee_name": employee_name,
				"novedad_type": novedad_code,
				"quantity": quantity,
				"source_sheet": sheet_name,
				"source_row_data": json.dumps({
					"row": row_num,
					"documento": employee_id,
					"nombre": employee_name,
					"tipo": hour_type,
					"valor": quantity,
				}),
			})

	return lines, errors


def parse_clonk_ausentismo_sheet(sheet, sheet_name, batch_name):
	"""Parse CLONK 'Ausentismos' sheet."""
	lines = []
	errors = []

	rows = list(sheet.iter_rows(values_only=True))
	if len(rows) < 2:
		return lines, errors

	headers = rows[0]
	col_map = {}
	for field, possible_names in CLONK_AUSENTISMO_COLUMNS.items():
		idx = find_column_index(headers, possible_names)
		if idx is not None:
			col_map[field] = idx

	if "documento" not in col_map:
		errors.append({"sheet": sheet_name, "error": "No se encontró columna de documento"})
		return lines, errors

	# Mapping of absence types to novedad codes
	ABSENCE_TYPE_MAP = {
		"descanso": "DESCANSO",
		"vacaciones": "VACACIONES",
		"incapacidad eg": "INC-EG",
		"incapacidad enfermedad general": "INC-EG",
		"incapacidad at": "INC-AT",
		"incapacidad accidente": "INC-AT",
		"enfermedad general": "ENF-GENERAL",
		"ausentismo": "AUSENTISMO",
		"licencia remunerada": "LIC-REM",
		"l. remunerada": "LIC-REM",
		"licencia no remunerada": "LIC-NO-REM",
		"l. no remunerada": "LIC-NO-REM",
		"calamidad": "CALAMIDAD",
		"calamidad doméstica": "CALAMIDAD",
		"maternidad": "MATERNIDAD",
		"licencia maternidad": "MATERNIDAD",
		"día familia": "DIA-FAMILIA",
		"dia familia": "DIA-FAMILIA",
		"cumpleaños": "CUMPLEANOS",
		"cumpleanos": "CUMPLEANOS",
		"inducción": "INDUCCION",
		"induccion": "INDUCCION",
		"luto": "LUTO",
		"licencia luto": "LUTO",
	}

	for row_num, row in enumerate(rows[1:], start=2):
		doc_value = row[col_map["documento"]] if col_map.get("documento") is not None else None
		if not doc_value:
			continue

		employee_id = str(doc_value).strip()
		employee_name = str(row[col_map.get("nombre", 0)] or "").strip() if col_map.get("nombre") else ""

		# Get absence type
		tipo_ausencia_raw = str(row[col_map.get("tipo_ausencia", 0)] or "").strip().lower() if col_map.get("tipo_ausencia") else ""
		novedad_code = ABSENCE_TYPE_MAP.get(tipo_ausencia_raw, "AUSENTISMO")

		# Get dates
		fecha_inicio = row[col_map.get("fecha_inicio")] if col_map.get("fecha_inicio") else None
		fecha_fin = row[col_map.get("fecha_fin")] if col_map.get("fecha_fin") else None
		dias = row[col_map.get("dias")] if col_map.get("dias") else None

		# Parse dates
		novedad_date = None
		if fecha_inicio:
			if isinstance(fecha_inicio, datetime):
				novedad_date = fecha_inicio.strftime("%Y-%m-%d")
			else:
				try:
					novedad_date = str(fecha_inicio)
				except Exception:
					pass

		# Parse days
		quantity = None
		if dias:
			try:
				quantity = float(dias)
			except (ValueError, TypeError):
				quantity = 1

		lines.append({
			"batch": batch_name,
			"row_number": row_num,
			"status": "Pendiente",
			"employee_id": employee_id,
			"employee_name": employee_name,
			"novedad_type": novedad_code,
			"novedad_date": novedad_date,
			"quantity": quantity,
			"source_sheet": sheet_name,
			"source_row_data": json.dumps({
				"row": row_num,
				"documento": employee_id,
				"nombre": employee_name,
				"tipo_ausencia": tipo_ausencia_raw,
				"fecha_inicio": str(fecha_inicio) if fecha_inicio else None,
				"fecha_fin": str(fecha_fin) if fecha_fin else None,
				"dias": dias,
			}),
		})

	return lines, errors


# =============================================================================
# Deduplication Engine
# =============================================================================

def generate_dedup_hash(periodo, employee_id, novelty_type, novelty_date=None):
	"""
	Generate hash key for deduplication check.
	Hash key: (periodo, employee_id, novelty_type, novelty_date)
	"""
	key_parts = [
		str(periodo) if periodo else "",
		str(employee_id) if employee_id else "",
		str(novelty_type) if novelty_type else "",
		str(novelty_date) if novelty_date else ""
	]
	key_string = "|".join(key_parts)
	return hashlib.md5(key_string.encode()).hexdigest()


def check_duplicate_line(periodo, employee_id, novelty_type, novelty_date=None):
	"""
	Check if a line with same hash key already exists.
	Returns existing line name if duplicate found, None otherwise.
	"""
	dedup_hash = generate_dedup_hash(periodo, employee_id, novelty_type, novelty_date)
	
	existing = frappe.db.sql("""
		SELECT name 
		FROM `tabPayroll Import Line` 
		WHERE dedup_hash = %s
		LIMIT 1
	""", [dedup_hash])
	
	return existing[0][0] if existing else None


# =============================================================================
# Import Engine
# =============================================================================

def detect_source_type(file_path):
	"""
	Detect the source type from file content/name.
	Returns source_type string or None.
	"""
	import os
	filename = os.path.basename(file_path).lower()

	# CLONK detection
	if "clonk" in filename or "toda la empresa" in filename:
		return "CLONK"

	# Payflow detection
	if "payflow" in filename:
		return "Payflow Resumen"

	# Fincomercio detection
	if "fincomercio" in filename:
		return "Fincomercio"

	# Fondo detection
	if "fondo" in filename or "fongiga" in filename or "m home" in filename:
		return "Fondo FONGIGA"

	# Libranzas detection
	if "libranza" in filename:
		return "Libranzas Bancolombia"

	return None


def process_import_batch(batch_name):
	"""
	Process a Payroll Import Batch:
	1. Read the source file
	2. Detect/validate source type
	3. Parse file using appropriate parser
	4. Create Payroll Import Line records
	5. Update batch status
	"""
	batch = frappe.get_doc("Payroll Import Batch", batch_name)

	if batch.status not in ("Pendiente", "Fallido"):
		frappe.throw(f"El lote {batch_name} ya fue procesado.")

	batch.status = "Procesando"
	batch.save(ignore_permissions=True)
	frappe.db.commit()

	try:
		# Get file path
		file_url = batch.source_file
		if not file_url:
			raise ValueError("No se encontró archivo fuente.")

		# Get actual file path
		file_doc = frappe.get_doc("File", {"file_url": file_url})
		file_path = file_doc.get_full_path()

		# Get source type
		source_type = batch.source_type
		source_doc = frappe.get_doc("Payroll Source Catalog", source_type)
		tipo_fuente = source_doc.tipo_fuente

		# Parse based on source type
		lines = []
		errors = []

		if tipo_fuente == "clonk":
			lines, errors = parse_clonk_file(file_path, batch_name)
		else:
			raise ValueError(f"Parser no implementado para fuente: {tipo_fuente}")

		# Create import lines with deduplication check
		valid_count = 0
		error_count = 0
		duplicate_count = 0

		for line_data in lines:
			try:
				# Check for duplicates
				period = batch.nomina_period or batch.period
				duplicate_line = check_duplicate_line(
					period, 
					line_data.get("employee_id"),
					line_data.get("novedad_type"),
					line_data.get("novedad_date")
				)
				
				if duplicate_line:
					# Mark as duplicate
					line_data["status"] = "Duplicado"
					line_data["validation_errors"] = f"Duplicado de línea existente: {duplicate_line}"
					duplicate_count += 1
				
				# Generate dedup hash
				line_data["dedup_hash"] = generate_dedup_hash(
					period,
					line_data.get("employee_id"),
					line_data.get("novedad_type"), 
					line_data.get("novedad_date")
				)
				
				line_doc = frappe.get_doc({
					"doctype": "Payroll Import Line",
					**line_data
				})
				line_doc.insert(ignore_permissions=True)
				valid_count += 1
			except Exception as e:
				error_count += 1
				errors.append({
					"row": line_data.get("row_number"),
					"error": str(e),
				})

		# Update batch
		batch.reload()
		batch.total_rows = len(lines)
		batch.valid_rows = valid_count - duplicate_count  # Only truly valid rows
		batch.error_rows = error_count
		batch.processed_on = now_datetime()
		
		# Include duplicate info in processing log
		processing_info = {
			"errors": errors,
			"duplicates_found": duplicate_count,
			"total_processed": len(lines)
		}
		batch.processing_log = json.dumps(processing_info) if (errors or duplicate_count > 0) else None

		if error_count == 0:
			if duplicate_count > 0:
				batch.status = "Completado con duplicados"
			else:
				batch.status = "Completado"
		elif valid_count > 0:
			batch.status = "Completado con errores"
		else:
			batch.status = "Fallido"

		batch.save(ignore_permissions=True)
		frappe.db.commit()

		return {
			"status": batch.status,
			"total_rows": batch.total_rows,
			"valid_rows": batch.valid_rows,
			"error_rows": batch.error_rows,
			"duplicate_rows": duplicate_count,
			"errors": errors,
		}

	except Exception as e:
		batch.reload()
		batch.status = "Fallido"
		batch.processing_log = json.dumps({"error": str(e)})
		batch.processed_on = now_datetime()
		batch.save(ignore_permissions=True)
		frappe.db.commit()
		raise


@frappe.whitelist()
def process_batch(batch_name):
	"""API endpoint to process a batch."""
	enforce_payroll_access("import_batches")
	return process_import_batch(batch_name)
