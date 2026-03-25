// Copyright (c) 2026, Antigravity and contributors
// For license information, please see license.txt

frappe.ui.form.on("Candidato", {
	refresh: function(frm) {
		if (frm.doc.estado_proceso !== "Contratado") {
			frm.add_custom_button("Convertir a Usuario", function() {
				frm.call("convertir_a_usuario").then(() => {
					frm.reload_doc();
				});
			});
		}
	}
});
