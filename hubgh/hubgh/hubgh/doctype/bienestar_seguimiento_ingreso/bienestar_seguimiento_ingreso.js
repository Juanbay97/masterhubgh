frappe.ui.form.on("Bienestar Seguimiento Ingreso", {
	onload(frm) {
		frm.trigger("hubgh_precargar_encuesta");
	},

	refresh(frm) {
		frm.trigger("hubgh_precargar_encuesta");
	},

	tipo_seguimiento(frm) {
		frm.trigger("hubgh_precargar_encuesta");
	},

	momento_consolidacion(frm) {
		frm.trigger("hubgh_precargar_encuesta");
	},

	hubgh_precargar_encuesta(frm) {
		if (!frm.is_new() || !frm.doc.tipo_seguimiento) {
			return;
		}

		frappe.call({
			method: "hubgh.hubgh.bienestar_automation.get_followup_questionnaire_template",
			args: {
				tipo_seguimiento: frm.doc.tipo_seguimiento,
				momento_consolidacion: frm.doc.momento_consolidacion,
			},
			callback: ({ message }) => {
				const template = message || {};
				const key = template.key || "";
				const escala = template.escala || [];
				const abiertas = template.abiertas || [];

				if (!escala.length && !abiertas.length) {
					return;
				}

				const hasRows = (frm.doc.respuestas_escala || []).length || (frm.doc.respuestas_abiertas || []).length;
				if (hasRows && frm.__hubgh_followup_key === key) {
					return;
				}

				frm.clear_table("respuestas_escala");
				frm.clear_table("respuestas_abiertas");

				escala.forEach((row) => {
					frm.add_child("respuestas_escala", {
						dimension: row.dimension,
						pregunta: row.pregunta,
						tipo_respuesta: row.tipo_respuesta || "1-10",
						peso: row.peso || 1,
					});
				});

				abiertas.forEach((row) => {
					frm.add_child("respuestas_abiertas", {
						categoria: row.categoria,
						pregunta: row.pregunta,
					});
				});

				frm.__hubgh_followup_key = key;
				frm.refresh_field("respuestas_escala");
				frm.refresh_field("respuestas_abiertas");
			},
		});
	},
});
