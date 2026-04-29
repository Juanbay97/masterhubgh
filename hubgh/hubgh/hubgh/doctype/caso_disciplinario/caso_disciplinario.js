// Copyright (c) 2026, Antigravity and contributors
// For license information, please see license.txt

frappe.ui.form.on("Caso Disciplinario", {
	before_save(frm) {
		if (frm.is_new()) {
			frm._just_created = true;
		}
	},

	after_save(frm) {
		// Si es la primera vez que se guarda el caso (creación reciente),
		// ofrecer agregar afectados de inmediato.
		if (frm._just_created) {
			delete frm._just_created;
			openAfectadoWizard(frm);
		}
	},

	refresh(frm) {
		if (!frm.is_new()) {
			frm.add_custom_button(__("Agregar afectado"), () => {
				openAfectadoWizard(frm);
			}, __("Acciones"));
		}
	},
});

function openAfectadoWizard(frm) {
	const dialog = new frappe.ui.Dialog({
		title: __("Agregar afectado al caso"),
		fields: [
			{
				fieldtype: "Section Break",
				label: __("Datos del afectado"),
			},
			{
				fieldname: "empleado",
				label: __("Empleado afectado"),
				fieldtype: "Link",
				options: "Ficha Empleado",
				reqd: 1,
				description: __("Buscar por nombre o cédula"),
			},
			{
				fieldtype: "Section Break",
			},
			{
				fieldname: "agregar_otro",
				label: __("Agregar otro afectado al mismo caso"),
				fieldtype: "Check",
				default: 1,
				description: __("Si lo dejás marcado, al guardar se abrirá nuevamente este diálogo para agregar el siguiente afectado con los mismos hechos."),
			},
		],
		primary_action_label: __("Guardar afectado"),
		primary_action(values) {
			if (!frm.doc.name) {
				frappe.msgprint(__("El caso aún no tiene nombre. Guardá el caso primero."));
				return;
			}
			frappe.call({
				method: "frappe.client.insert",
				args: {
					doc: {
						doctype: "Afectado Disciplinario",
						caso: frm.doc.name,
						empleado: values.empleado,
						// estado se setea por defecto en el server controller
					},
				},
				callback(r) {
					if (r.message && !r.exc) {
						frappe.show_alert({
							message: __("Afectado {0} agregado", [r.message.name]),
							indicator: "green",
						});
						if (values.agregar_otro) {
							// Reset solo el campo empleado y reutilizar el mismo dialog
							dialog.set_value("empleado", "");
						} else {
							dialog.hide();
							frm.reload_doc();
						}
					}
				},
				error(_r) {
					// Frappe ya muestra el error; no cerrar el dialog
				},
			});
		},
		secondary_action_label: __("Listo"),
		secondary_action() {
			dialog.hide();
			frm.reload_doc();
		},
	});

	dialog.show();
}
