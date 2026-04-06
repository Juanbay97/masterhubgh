frappe.ui.form.on("Persona Documento", {
	refresh(frm) {
		frm.set_df_property("archivo", "is_private", 1);
	}
});
