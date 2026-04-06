frappe.ui.form.on("Bienestar Levantamiento Punto", {
	setup(frm) {
		frm.set_query("ficha_empleado", "participantes", () => {
			if (!frm.doc.punto_venta) {
				return {};
			}
			return {
				filters: {
					pdv: frm.doc.punto_venta,
					estado: "Activo",
				},
			};
		});
	},
});
