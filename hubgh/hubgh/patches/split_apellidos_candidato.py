import frappe


def execute():
	if not frappe.db.exists("DocType", "Candidato"):
		return

	required_columns = ["apellidos", "primer_apellido", "segundo_apellido"]
	for column in required_columns:
		if not frappe.db.has_column("Candidato", column):
			return

	rows = frappe.get_all(
		"Candidato",
		filters={"apellidos": ["is", "set"]},
		fields=["name", "apellidos", "primer_apellido", "segundo_apellido"],
		limit_page_length=0,
	)

	for row in rows:
		apellidos = (row.apellidos or "").strip()
		if not apellidos:
			continue

		primer = (row.primer_apellido or "").strip()
		segundo = (row.segundo_apellido or "").strip()
		partes = [p.strip() for p in apellidos.split() if p and p.strip()]

		if not primer and partes:
			primer = partes[0]
		if not segundo and len(partes) >= 2:
			segundo = " ".join(partes[1:]).strip()
		if not segundo and primer:
			segundo = primer

		updates = {
			"primer_apellido": primer,
			"segundo_apellido": segundo,
			"apellidos": " ".join([x for x in [primer, segundo] if x]).strip() or apellidos,
		}
		frappe.db.set_value("Candidato", row.name, updates, update_modified=False)

	frappe.db.commit()
