import frappe


def run():
	# LMS excluded from current scope — skip workspace setup that references missing DocTypes
	# ensure_lms_single_entrypoint()
	ensure_workflow_states_and_actions()
	ensure_workflows()
	ensure_notifications()
	ensure_dashboards_and_kanban()
	migrate_policies_to_help_articles()
	ensure_form_tours()
	frappe.db.commit()


def ensure_lms_single_entrypoint():
	if frappe.db.exists("Workspace", "Formación y Bienestar"):
		legacy = frappe.get_doc("Workspace", "Formación y Bienestar")
		legacy.is_hidden = 1
		legacy.public = 0
		legacy.save(ignore_permissions=True)

	if frappe.db.exists("Workspace", "Capacitación"):
		ws = frappe.get_doc("Workspace", "Capacitación")
		links = []
		for row in ws.links or []:
			label = (row.label or "").strip().lower()
			link_to = (row.link_to or "").strip()
			if label in {"carpeta documental", "tipos de documento", "comentario bienestar"}:
				continue
			if link_to in {"Comentario Bienestar", "carpeta_documental_empleado"}:
				continue
			links.append(row)
		ws.set("links", links)

		required_shortcuts = [
			{"label": "Cursos", "link_to": "LMS Course", "type": "DocType", "color": "Blue", "format": "{} cursos"},
			{"label": "Estudiantes", "link_to": "LMS Enrollment", "type": "DocType", "color": "Green", "format": "{} enrollados"},
			{"label": "Certificados", "link_to": "LMS Certificate", "type": "DocType", "color": "Purple", "doc_view": "List"},
		]

		ws.set("shortcuts", [])
		for shortcut in required_shortcuts:
			ws.append("shortcuts", shortcut)

		content = (
			'[{"id":"lms","type":"header","data":{"text":"Plataforma LMS","col":12}},'
			'{"id":"gestion","type":"header","data":{"text":"Gestión de Cursos","col":12}},'
			'{"id":"lms-cursos","type":"shortcut","data":{"shortcut_name":"Cursos","col":4}},'
			'{"id":"lms-estudiantes","type":"shortcut","data":{"shortcut_name":"Estudiantes","col":4}},'
			'{"id":"lms-certificados","type":"shortcut","data":{"shortcut_name":"Certificados","col":4}}]'
		)
		ws.content = content
		ws.save(ignore_permissions=True)

	if frappe.db.exists("Workspace", "Bienestar"):
		bienestar = frappe.get_doc("Workspace", "Bienestar")
		bienestar.is_hidden = 0
		bienestar.public = 1
		bienestar_required_shortcuts = [
			{"label": "Periodo de Prueba", "link_to": "Bienestar Evaluacion Periodo Prueba", "type": "DocType", "color": "Orange", "doc_view": "List"},
			{"label": "Bandeja Bienestar", "link_to": "bienestar_bandeja", "type": "Page", "color": "Red", "doc_view": ""},
			{"label": "Seguimientos Ingreso", "link_to": "Bienestar Seguimiento Ingreso", "type": "DocType", "color": "Green", "doc_view": "List"},
			{"label": "Alertas Bienestar", "link_to": "Bienestar Alerta", "type": "DocType", "color": "Red", "doc_view": "List"},
			{"label": "Compromisos", "link_to": "Bienestar Compromiso", "type": "DocType", "color": "Purple", "doc_view": "List"},
			{"label": "Levantamientos Punto", "link_to": "Bienestar Levantamiento Punto", "type": "DocType", "color": "Teal", "doc_view": "List"},
			{"label": "Persona 360", "link_to": "persona_360", "type": "Page", "color": "Blue", "doc_view": ""},
		]
		bienestar.set("shortcuts", [])
		for shortcut in bienestar_required_shortcuts:
			bienestar.append("shortcuts", shortcut)

		bienestar.content = (
			'[{"id":"bienestar","type":"header","data":{"text":"Bienestar Operativo","col":12}},'
			'{"id":"bien-prueba","type":"shortcut","data":{"shortcut_name":"Periodo de Prueba","col":4}},'
			'{"id":"bien-bandeja","type":"shortcut","data":{"shortcut_name":"Bandeja Bienestar","col":4}},'
			'{"id":"bien-seg","type":"shortcut","data":{"shortcut_name":"Seguimientos Ingreso","col":4}},'
			'{"id":"bien-alerta","type":"shortcut","data":{"shortcut_name":"Alertas Bienestar","col":4}},'
			'{"id":"bien-comp","type":"shortcut","data":{"shortcut_name":"Compromisos","col":4}},'
			'{"id":"bien-lev","type":"shortcut","data":{"shortcut_name":"Levantamientos Punto","col":4}},'
			'{"id":"bien-persona360","type":"shortcut","data":{"shortcut_name":"Persona 360","col":4}}]'
		)
		bienestar.save(ignore_permissions=True)


def ensure_workflow_states_and_actions():
	for state_name, style in {
		"En Proceso": "Warning",
		"Documentación Incompleta": "Warning",
		"Documentación Completa": "Info",
		"En Afiliación": "Primary",
		"Listo para Contratar": "Info",
		"Contratado": "Success",
		"Rechazado": "Danger",
		"Pendiente": "Warning",
		"Activo": "Success",
		"Retirado": "Danger",
		"Cancelado": "Danger",
		"Abierto": "Warning",
		"Cerrado": "Success",
		"Cerrada": "Success",
		"Recibida": "Warning",
		"En gestión": "Info",
		"Pendiente info": "Warning",
		"Abierta": "Warning",
		"En seguimiento": "Info",
	}.items():
		if frappe.db.exists("Workflow State", state_name):
			doc = frappe.get_doc("Workflow State", state_name)
			doc.style = style
			doc.save(ignore_permissions=True)
		else:
			frappe.get_doc(
				{
					"doctype": "Workflow State",
					"workflow_state_name": state_name,
					"style": style,
				}
			).insert(ignore_permissions=True)

	for action in [
		"Solicitar Documentos",
		"Marcar Incompleta",
		"Marcar Completa",
		"Enviar a Afiliación",
		"Listo para Contratar",
		"Contratar",
		"Rechazar",
		"Activar",
		"Retirar",
		"Cancelar",
		"Iniciar Gestión",
		"Cerrar",
		"Pedir Información",
		"Reabrir",
	]:
		if not frappe.db.exists("Workflow Action Master", action):
			frappe.get_doc(
				{
					"doctype": "Workflow Action Master",
					"workflow_action_name": action,
				}
			).insert(ignore_permissions=True)


def ensure_workflows():
	_ensure_workflow(
		"HubGH - Candidato",
		"Candidato",
		"estado_proceso",
		states=[
			("En Proceso", "0", "HR Selection"),
			("Documentación Incompleta", "0", "HR Selection"),
			("Documentación Completa", "0", "HR Selection"),
			("En Afiliación", "0", "GH - Bandeja General"),
			("Listo para Contratar", "0", "HR Labor Relations"),
			("Contratado", "0", "HR Labor Relations"),
			("Rechazado", "0", "HR Selection"),
		],
		transitions=[
			("En Proceso", "Solicitar Documentos", "Documentación Incompleta", "HR Selection"),
			("En Proceso", "Marcar Completa", "Documentación Completa", "HR Selection"),
			("Documentación Incompleta", "Marcar Completa", "Documentación Completa", "HR Selection"),
			("Documentación Completa", "Enviar a Afiliación", "En Afiliación", "GH - Bandeja General"),
			("En Afiliación", "Listo para Contratar", "Listo para Contratar", "HR Labor Relations"),
			("Listo para Contratar", "Contratar", "Contratado", "HR Labor Relations"),
			("En Proceso", "Rechazar", "Rechazado", "HR Selection"),
			("Documentación Incompleta", "Rechazar", "Rechazado", "HR Selection"),
			("Documentación Completa", "Rechazar", "Rechazado", "HR Selection"),
		],
	)

	_ensure_workflow(
		"HubGH - Contrato",
		"Contrato",
		"estado_contrato",
		states=[
			("Pendiente", "0", "Gestión Humana"),
			("Activo", "1", "Gestión Humana"),
			("Retirado", "1", "GH - RRLL"),
			("Cancelado", "0", "GH - RRLL"),
		],
		transitions=[
			("Pendiente", "Activar", "Activo", "Gestión Humana"),
			("Activo", "Retirar", "Retirado", "GH - RRLL"),
			("Pendiente", "Cancelar", "Cancelado", "GH - RRLL"),
		],
	)

	_ensure_workflow(
		"HubGH - Caso Disciplinario",
		"Caso Disciplinario",
		"estado",
		states=[
			("Abierto", "0", "GH - RRLL"),
			("En Proceso", "0", "GH - RRLL"),
			("Cerrado", "0", "GH - RRLL"),
		],
		transitions=[
			("Abierto", "Iniciar Gestión", "En Proceso", "GH - RRLL"),
			("En Proceso", "Cerrar", "Cerrado", "GH - RRLL"),
			("Cerrado", "Reabrir", "Abierto", "GH - RRLL"),
		],
	)

	_ensure_workflow(
		"HubGH - GH Novedad",
		"GH Novedad",
		"estado",
		states=[
			("Recibida", "0", "GH - Bandeja General"),
			("En gestión", "0", "GH - Bandeja General"),
			("Pendiente info", "0", "GH - Bandeja General"),
			("Cerrada", "0", "GH - Bandeja General"),
		],
		transitions=[
			("Recibida", "Iniciar Gestión", "En gestión", "GH - Bandeja General"),
			("En gestión", "Pedir Información", "Pendiente info", "GH - Bandeja General"),
			("Pendiente info", "Iniciar Gestión", "En gestión", "GH - Bandeja General"),
			("En gestión", "Cerrar", "Cerrada", "GH - Bandeja General"),
		],
	)

	_ensure_workflow(
		"HubGH - Caso SST",
		"Caso SST",
		"estado",
		states=[
			("Abierto", "0", "GH - SST"),
			("Cerrado", "0", "GH - SST"),
		],
		transitions=[
			("Abierto", "Cerrar", "Cerrado", "GH - SST"),
			("Cerrado", "Reabrir", "Abierto", "GH - SST"),
		],
	)

	_ensure_workflow(
		"HubGH - Novedad SST",
		"Novedad SST",
		"estado",
		states=[
			("Abierta", "0", "Gestión Humana"),
			("En seguimiento", "0", "Gestión Humana"),
			("Cerrada", "0", "Gestión Humana"),
		],
		transitions=[
			("Abierta", "Iniciar Gestión", "En seguimiento", "Gestión Humana"),
			("En seguimiento", "Cerrar", "Cerrada", "Gestión Humana"),
			("Cerrada", "Reabrir", "Abierta", "Gestión Humana"),
		],
	)


def _ensure_workflow(name, doctype, state_field, states, transitions):
	if not frappe.db.exists("DocType", doctype):
		return

	if frappe.db.exists("Workflow", name):
		doc = frappe.get_doc("Workflow", name)
	else:
		doc = frappe.get_doc({"doctype": "Workflow", "workflow_name": name})

	doc.document_type = doctype
	doc.is_active = 1
	doc.workflow_state_field = state_field
	doc.send_email_alert = 0

	doc.set("states", [])
	for state_name, doc_status, allow_edit in states:
		doc.append(
			"states",
			{
				"state": state_name,
				"doc_status": doc_status,
				"allow_edit": allow_edit,
			},
		)

	doc.set("transitions", [])
	for state, action, next_state, allowed in transitions:
		doc.append(
			"transitions",
			{
				"state": state,
				"action": action,
				"next_state": next_state,
				"allowed": allowed,
				"allow_self_approval": 1,
			},
		)

	if doc.is_new():
		doc.insert(ignore_permissions=True)
	else:
		doc.save(ignore_permissions=True)


def ensure_notifications():
	_ensure_notification(
		"HubGH - Caso Disciplinario Nuevo",
		doctype="Caso Disciplinario",
		event="New",
		subject="Nuevo caso disciplinario {{ doc.name }}",
		message="Se registró un nuevo caso disciplinario para {{ doc.empleado }}.",
		recipient_roles=["GH - RRLL", "Jefe_PDV"],
	)

	_ensure_notification(
		"HubGH - Caso SST Alta Severidad",
		doctype="Caso SST",
		event="New",
		condition="doc.severidad == 'Alta'",
		subject="Caso SST de alta severidad {{ doc.name }}",
		message="El caso SST {{ doc.name }} fue creado con severidad ALTA.",
		recipient_roles=["GH - SST", "System Manager"],
	)

	_ensure_notification(
		"HubGH - Candidato Documentacion Completa",
		doctype="Candidato",
		event="Value Change",
		value_changed="estado_proceso",
		condition="doc.estado_proceso == 'Documentación Completa'",
		subject="Candidato {{ doc.name }} con documentación completa",
		message="El candidato {{ doc.nombres }} {{ doc.apellidos }} quedó en documentación completa.",
		recipient_roles=["HR Selection", "GH - Bandeja General"],
	)

	for queue, role in [
		("GH-Bandeja General", "GH - Bandeja General"),
		("GH-SST", "GH - SST"),
		("GH-RRLL", "GH - RRLL"),
	]:
		_ensure_notification(
			f"HubGH - GH Novedad asignada {queue}",
			doctype="GH Novedad",
			event="Value Change",
			value_changed="cola_destino",
			condition=f"doc.cola_destino == '{queue}'",
			subject="GH Novedad {{ doc.name }} asignada a {{ doc.cola_destino }}",
			message="La novedad {{ doc.name }} fue asignada a {{ doc.cola_destino }}.",
			recipient_roles=[role],
		)

	_ensure_notification(
		"HubGH - Empleado Retirado",
		doctype="Ficha Empleado",
		event="Value Change",
		value_changed="estado",
		condition="doc.estado == 'Retirado'",
		subject="Empleado retirado: {{ doc.nombres }} {{ doc.apellidos }}",
		message="El empleado {{ doc.name }} cambió a estado Retirado.",
		recipient_roles=["Gestión Humana", "Jefe_PDV"],
	)

	_ensure_notification(
		"HubGH - GH Post Publicado",
		doctype="GH Post",
		event="Value Change",
		value_changed="publicado",
		condition="doc.publicado == 1",
		subject="Nuevo comunicado: {{ doc.titulo }}",
		message="Se publicó un nuevo comunicado interno: {{ doc.titulo }}.",
		recipient_roles=["Empleado", "Jefe_PDV", "Gestión Humana"],
	)

	_ensure_notification(
		"HubGH - Contrato por Vencer 7 dias",
		doctype="Contrato",
		event="Days Before",
		date_changed="fecha_fin_contrato",
		days_in_advance=7,
		condition="doc.estado_contrato == 'Activo'",
		subject="Contrato próximo a vencer: {{ doc.name }}",
		message="El contrato {{ doc.name }} vence en 7 días.",
		recipient_roles=["Gestión Humana", "Jefe_PDV", "GH - RRLL"],
	)


def _ensure_notification(
	name,
	doctype,
	event,
	subject,
	message,
	recipient_roles,
	condition=None,
	value_changed=None,
	date_changed=None,
	days_in_advance=None,
):
	if not frappe.db.exists("DocType", doctype):
		return

	exists = frappe.db.exists("Notification", name)
	doc = frappe.get_doc("Notification", name) if exists else frappe.get_doc({"doctype": "Notification"})
	if not exists:
		doc.name = name

	doc.enabled = 1
	doc.channel = "System Notification"
	doc.document_type = doctype
	doc.event = event
	doc.subject = subject
	doc.message = message
	doc.send_system_notification = 1
	doc.condition = condition or ""

	if value_changed:
		doc.value_changed = value_changed
	if date_changed:
		doc.date_changed = date_changed
	if days_in_advance is not None:
		doc.days_in_advance = int(days_in_advance)

	doc.set("recipients", [])
	for role in sorted(set(recipient_roles or [])):
		doc.append("recipients", {"receiver_by_role": role})

	if not exists:
		doc.insert(ignore_permissions=True)
	else:
		doc.save(ignore_permissions=True)


def ensure_dashboards_and_kanban():
	_ensure_number_card("HubGH Empleados Activos", "Ficha Empleado", [["Ficha Empleado", "estado", "=", "Activo", False]])
	_ensure_number_card("HubGH Contratos por Vencer", "Contrato", [["Contrato", "estado_contrato", "=", "Activo", False]])
	_ensure_number_card("HubGH Candidatos en Proceso", "Candidato", [["Candidato", "estado_proceso", "in", ["En Proceso", "Documentación Incompleta", "Documentación Completa", "En Afiliación", "Listo para Contratar"], False]])
	_ensure_number_card("HubGH Casos SST Abiertos", "Caso SST", [["Caso SST", "estado", "=", "Abierto", False]])

	_ensure_chart_group_by("HubGH Candidatos por Estado", "Candidato", "estado_proceso", "Bar")
	_ensure_chart_group_by("HubGH Empleados por Punto", "Ficha Empleado", "pdv", "Bar")
	_ensure_chart_group_by("HubGH Casos SST por Severidad", "Caso SST", "severidad", "Pie")

	_attach_workspace_cards(
		"Gestión Humana",
		cards=[
			"HubGH Empleados Activos",
			"HubGH Contratos por Vencer",
			"HubGH Candidatos en Proceso",
			"HubGH Casos SST Abiertos",
		],
		charts=["HubGH Candidatos por Estado", "HubGH Empleados por Punto"],
	)

	_attach_workspace_cards(
		"SST",
		cards=["HubGH Casos SST Abiertos"],
		charts=["HubGH Casos SST por Severidad"],
	)

	_ensure_kanban(
		"HubGH Candidato Pipeline",
		"Candidato",
		"estado_proceso",
		[
			"En Proceso",
			"Documentación Incompleta",
			"Documentación Completa",
			"En Afiliación",
			"Listo para Contratar",
			"Contratado",
			"Rechazado",
		],
	)

	_ensure_kanban(
		"HubGH GH Novedades",
		"GH Novedad",
		"estado",
		["Recibida", "En gestión", "Pendiente info", "Cerrada"],
	)


def _ensure_number_card(name, doctype, filters):
	if not frappe.db.exists("DocType", doctype):
		return

	doc = frappe.get_doc("Number Card", name) if frappe.db.exists("Number Card", name) else frappe.get_doc(
		{"doctype": "Number Card", "name": name}
	)

	doc.label = name
	doc.type = "Document Type"
	doc.document_type = doctype
	doc.function = "Count"
	doc.is_public = 0
	doc.show_percentage_stats = 0
	doc.filters_json = frappe.as_json(filters)

	if doc.is_new():
		doc.insert(ignore_permissions=True)
	else:
		doc.save(ignore_permissions=True)


def _ensure_chart_group_by(name, doctype, fieldname, chart_type):
	if not frappe.db.exists("DocType", doctype):
		return

	doc = frappe.get_doc("Dashboard Chart", name) if frappe.db.exists("Dashboard Chart", name) else frappe.get_doc(
		{"doctype": "Dashboard Chart", "name": name}
	)

	doc.chart_name = name
	doc.chart_type = "Group By"
	doc.document_type = doctype
	doc.group_by_based_on = fieldname
	doc.group_by_type = "Count"
	doc.number_of_groups = 10
	doc.type = chart_type
	doc.is_public = 0
	doc.filters_json = "[]"

	if doc.is_new():
		doc.insert(ignore_permissions=True)
	else:
		doc.save(ignore_permissions=True)


def _attach_workspace_cards(workspace_name, cards, charts):
	if not frappe.db.exists("Workspace", workspace_name):
		return

	doc = frappe.get_doc("Workspace", workspace_name)

	doc.set("number_cards", [])
	for card in cards:
		if frappe.db.exists("Number Card", card):
			doc.append("number_cards", {"number_card_name": card, "label": card})

	doc.set("charts", [])
	for chart in charts:
		if frappe.db.exists("Dashboard Chart", chart):
			doc.append("charts", {"chart_name": chart, "label": chart})

	doc.save(ignore_permissions=True)


def _ensure_kanban(name, doctype, field_name, columns):
	if not frappe.db.exists("DocType", doctype):
		return

	doc = frappe.get_doc("Kanban Board", name) if frappe.db.exists("Kanban Board", name) else frappe.get_doc(
		{"doctype": "Kanban Board", "kanban_board_name": name}
	)

	doc.reference_doctype = doctype
	doc.field_name = field_name
	doc.show_labels = 1
	doc.private = 0
	doc.filters = "[]"
	doc.fields = "[]"

	doc.set("columns", [])
	for idx, column in enumerate(columns):
		doc.append(
			"columns",
			{
				"column_name": column,
				"status": "Active",
				"indicator": "Blue" if idx == 0 else "Gray",
				"order": "asc",
			},
		)

	if doc.is_new():
		doc.insert(ignore_permissions=True)
	else:
		doc.save(ignore_permissions=True)


def migrate_policies_to_help_articles():
	if not frappe.db.exists("DocType", "GH Policy"):
		return

	for row in frappe.get_all(
		"GH Policy",
		fields=["name", "titulo", "categoria", "version", "archivo", "fecha_vigencia", "vigente"],
	):
		category_name = (row.get("categoria") or "General").strip() or "General"
		_ensure_help_category(category_name)

		article_name = f"HubGH Policy - {row.get('name')}"
		content = (
			f"<h3>{row.get('titulo') or row.get('name')}</h3>"
			f"<p><b>Versión:</b> {row.get('version') or 'N/A'}</p>"
			f"<p><b>Fecha de vigencia:</b> {row.get('fecha_vigencia') or 'N/A'}</p>"
		)
		if row.get("archivo"):
			content += f"<p><a href='{row.get('archivo')}' target='_blank'>Ver documento adjunto</a></p>"

		if frappe.db.exists("Help Article", article_name):
			article = frappe.get_doc("Help Article", article_name)
		else:
			article = frappe.get_doc({"doctype": "Help Article", "name": article_name})

		article.title = row.get("titulo") or row.get("name")
		article.category = category_name
		article.published = 1 if row.get("vigente") else 0
		article.author = "Gestión Humana"
		article.level = "Beginner"
		article.content = content

		if article.is_new():
			article.insert(ignore_permissions=True)
		else:
			article.save(ignore_permissions=True)

	_ensure_policy_link_in_workspace()


def _ensure_help_category(category_name):
	if frappe.db.exists("Help Category", category_name):
		doc = frappe.get_doc("Help Category", category_name)
		doc.published = 1
		doc.save(ignore_permissions=True)
		return

	frappe.get_doc(
		{
			"doctype": "Help Category",
			"category_name": category_name,
			"published": 1,
		}
	).insert(ignore_permissions=True)


def _ensure_policy_link_in_workspace():
	if not frappe.db.exists("Workspace", "Gestión Humana"):
		return

	doc = frappe.get_doc("Workspace", "Gestión Humana")
	exists = any((row.label == "Políticas GH" and row.link_to == "Help Article") for row in (doc.links or []))
	if exists:
		return

	doc.append(
		"links",
		{
			"type": "Link",
			"label": "Políticas GH",
			"link_type": "DocType",
			"link_to": "Help Article",
			"hidden": 0,
		},
	)
	doc.save(ignore_permissions=True)


def ensure_form_tours():
	_ensure_workspace_tour(
		title="HubGH Tour Operario - Mi Perfil",
		workspace="Mi Perfil",
		steps=[
			("Bienvenido a Mi Perfil", ".layout-main-section .page-head h3", "Aquí verás tu información principal y accesos rápidos."),
			("Accesos rápidos", ".layout-main-section .widget.shortcut-widget-box", "Usa estos accesos para navegar sin complicaciones."),
		],
	)

	_ensure_workspace_tour(
		title="HubGH Tour Jefe PDV - Mi Punto",
		workspace="Mi Punto",
		steps=[
			("Vista del Punto", ".layout-main-section .page-head h3", "Este es el resumen de tu punto de venta."),
			("Links de gestión", ".layout-main-section .widget.links-widget-box", "Desde aquí accedes a equipo, documentos y operación."),
		],
	)

	_ensure_workspace_tour(
		title="HubGH Tour LMS - Capacitación",
		workspace="Capacitación",
		steps=[
			("Zona de Capacitación", ".layout-main-section .page-head h3", "Aquí encuentras cursos y seguimiento de aprendizaje."),
			("Shortcuts de LMS", ".layout-main-section .widget.shortcut-widget-box", "Ingresa por estos botones al LMS y tus contenidos."),
		],
	)


def _ensure_workspace_tour(title, workspace, steps):
	if not frappe.db.exists("Workspace", workspace):
		return

	doc = frappe.get_doc("Form Tour", title) if frappe.db.exists("Form Tour", title) else frappe.get_doc(
		{"doctype": "Form Tour", "title": title}
	)

	doc.ui_tour = 1
	doc.view_name = "Workspaces"
	doc.workspace_name = workspace
	doc.track_steps = 1
	doc.is_standard = 0

	doc.set("steps", [])
	for step_title, selector, description in steps:
		doc.append(
			"steps",
			{
				"ui_tour": 1,
				"title": step_title,
				"element_selector": selector,
				"description": f"<p>{description}</p>",
				"position": "Bottom",
			},
		)

	if doc.is_new():
		doc.insert(ignore_permissions=True)
	else:
		doc.save(ignore_permissions=True)
