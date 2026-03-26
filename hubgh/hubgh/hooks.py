app_name = "hubgh"
app_title = "Home Intranet"
app_publisher = "Antigravity"
app_description = "Hub de GH"
app_email = "user@example.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
add_to_apps_screen = [
	{
		"name": "hubgh",
		"logo": "/assets/hubgh/images/logo-dark.png",
		"title": "Home Intranet",
		"route": "/app",
		# "has_permission": "hubgh.api.permission.has_app_permission"
	}
]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
app_include_css = [
	"/assets/hubgh/css/hubgh_branding.css",
]

app_include_js = [
	"/assets/hubgh/js/hubgh_toolbar.js",
	"/assets/hubgh/js/bandejas_ui_base.js",
	"/assets/hubgh/js/svg_nan_guard.js",
]

# include js, css files in header of web template
web_include_css = "/assets/hubgh/css/hubgh_branding.css"
web_include_js = "/assets/hubgh/js/hubgh_web.js"

# App logo — used by Frappe boot, login page and email templates
app_logo_url = "/assets/hubgh/images/logo-circular-black.png"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "hubgh/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

webform_include_js = {
	"Candidato": "public/js/candidato_webform.js"
}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

doctype_js = {
	"Bienestar Levantamiento Punto": "hubgh/doctype/bienestar_levantamiento_punto/bienestar_levantamiento_punto.js",
	"Bienestar Seguimiento Ingreso": "hubgh/doctype/bienestar_seguimiento_ingreso/bienestar_seguimiento_ingreso.js",
	"Bienestar Evaluacion Periodo Prueba": "hubgh/doctype/bienestar_evaluacion_periodo_prueba/bienestar_evaluacion_periodo_prueba.js",
}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "hubgh/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "hubgh.utils.jinja_methods",
# 	"filters": "hubgh.utils.jinja_filters"
# }

get_website_user_home_page = "hubgh.utils.get_website_user_home_page"

# Installation
# ------------

# before_install = "hubgh.install.before_install"
# after_install = "hubgh.install.after_install"
after_migrate = [
	"hubgh.access_profiles.after_migrate_sync",
	"hubgh.seed_operational_enablement.run",
	"hubgh.hubgh.siesa_reference_matrix.sync_reference_masters",
	"hubgh.user_groups.sync_user_groups_after_migrate",
]

# Uninstallation
# ------------

# before_uninstall = "hubgh.uninstall.before_uninstall"
# after_uninstall = "hubgh.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "hubgh.utils.before_app_install"
# after_app_install = "hubgh.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "hubgh.utils.before_app_uninstall"
# after_app_uninstall = "hubgh.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "hubgh.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

permission_query_conditions = {
	"Ficha Empleado": "hubgh.permissions.get_permission_query_conditions",
	"LMS Enrollment": "hubgh.permissions.get_permission_query_conditions",
	"Novedad SST": "hubgh.permissions.get_permission_query_conditions",
	"Candidato": "hubgh.hubgh.permissions.get_candidato_permission_query",
	"Person Document": "hubgh.hubgh.permissions.get_person_document_permission_query",
	"Afiliacion Seguridad Social": "hubgh.hubgh.permissions.get_affiliation_permission_query",
	"Contrato": "hubgh.hubgh.permissions.get_contrato_permission_query",
	"Datos Contratacion": "hubgh.hubgh.permissions.get_datos_contratacion_permission_query",
	"GH Novedad": "hubgh.hubgh.permissions.get_gh_novedad_permission_query",
	"Payroll Import Batch": "hubgh.hubgh.payroll_permissions.get_payroll_import_batch_query",
	"Payroll Import Line": "hubgh.hubgh.payroll_permissions.get_payroll_import_line_query",
	"Payroll Liquidation Case": "hubgh.hubgh.payroll_permissions.get_payroll_liquidation_case_query",
}

has_permission = {
	"Ficha Empleado": "hubgh.permissions.has_permission",
	"LMS Enrollment": "hubgh.permissions.has_permission",
	"Candidato": "hubgh.hubgh.permissions.candidato_has_permission",
	"Person Document": "hubgh.hubgh.permissions.person_document_has_permission",
	"Afiliacion Seguridad Social": "hubgh.hubgh.permissions.affiliation_has_permission",
	"Contrato": "hubgh.hubgh.permissions.contrato_has_permission",
	"Datos Contratacion": "hubgh.hubgh.permissions.datos_contratacion_has_permission",
	"GH Novedad": "hubgh.hubgh.permissions.gh_novedad_has_permission",
	"Payroll Import Batch": "hubgh.hubgh.payroll_permissions.payroll_import_batch_has_permission",
	"Payroll Import Line": "hubgh.hubgh.payroll_permissions.payroll_import_line_has_permission",
	"Payroll Liquidation Case": "hubgh.hubgh.payroll_permissions.payroll_liquidation_case_has_permission",
}

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

doc_events = {
	"User": {
		"after_insert": "hubgh.lifecycle.on_user_create",
		"on_update": "hubgh.lifecycle.on_user_update",
	},
	"Ficha Empleado": {
		"after_insert": "hubgh.lifecycle.on_ficha_empleado_insert",
		"on_update": "hubgh.lifecycle.on_ficha_empleado_update",
	},
	"GH Novedad": {
		"after_insert": "hubgh.hubgh.people_ops_event_publishers.publish_from_gh_novedad",
		"on_update": "hubgh.hubgh.people_ops_event_publishers.publish_from_gh_novedad",
	},
	"Novedad SST": {
		"after_insert": "hubgh.hubgh.people_ops_event_publishers.publish_from_novedad_sst",
		"on_update": "hubgh.hubgh.people_ops_event_publishers.publish_from_novedad_sst",
	},
	"Caso Disciplinario": {
		"after_insert": "hubgh.hubgh.people_ops_event_publishers.publish_from_caso_disciplinario",
		"on_update": "hubgh.hubgh.people_ops_event_publishers.publish_from_caso_disciplinario",
	},
	"Bienestar Compromiso": {
		"after_insert": "hubgh.hubgh.people_ops_event_publishers.publish_from_bienestar_compromiso",
		"on_update": "hubgh.hubgh.people_ops_event_publishers.publish_from_bienestar_compromiso",
	},
	"Bienestar Alerta": {
		"after_insert": "hubgh.hubgh.people_ops_event_publishers.publish_from_bienestar_alerta",
		"on_update": "hubgh.hubgh.people_ops_event_publishers.publish_from_bienestar_alerta",
	},
	"Person Document": {
		"after_insert": "hubgh.hubgh.people_ops_event_publishers.publish_from_person_document",
		"on_update": "hubgh.hubgh.people_ops_event_publishers.publish_from_person_document",
	},
}

before_request = ["hubgh.www_hooks.check_page_permissions"]

# Scheduled Tasks
# ---------------

scheduler_events = {
	"daily": [
		"hubgh.tasks.revertir_novedades_expiradas",
		"hubgh.tasks.dispatch_sst_alertas_diarias",
		"hubgh.tasks.bienestar_generar_seguimientos_ingreso_diarios",
		"hubgh.tasks.bienestar_marcar_vencidos_diario",
		"hubgh.hubgh.people_ops_event_publishers.reconcile_people_ops_events_warn",
		"hubgh.user_groups.sync_all_user_groups",
	]
}

# scheduler_events = {
# 	"all": [
# 		"hubgh.tasks.all"
# 	],
# 	"daily": [
# 		"hubgh.tasks.daily"
# 	],
# 	"hourly": [
# 		"hubgh.tasks.hourly"
# 	],
# 	"weekly": [
# 		"hubgh.tasks.weekly"
# 	],
# 	"monthly": [
# 		"hubgh.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "hubgh.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "hubgh.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "hubgh.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["hubgh.utils.before_request"]
# after_request = ["hubgh.utils.after_request"]

# Job Events
# ----------
# before_job = ["hubgh.utils.before_job"]
# after_job = ["hubgh.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"hubgh.auth.validate"
# ]

on_login = [
	"hubgh.hubgh.onboarding_security.enforce_password_reset_on_login",
	"hubgh.setup_user_defaults.apply_login_home_page_redirect",
]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []
