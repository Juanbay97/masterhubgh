frappe.ui.form.on("Bienestar Evaluacion Periodo Prueba", {
	onload(frm) {
		frm.trigger("hubgh_precargar_criterios");
	},

	refresh(frm) {
		frm.trigger("hubgh_precargar_criterios");
	},

	hubgh_precargar_criterios(frm) {
		if (!frm.is_new()) {
			return;
		}

		frappe.call({
			method: "hubgh.hubgh.bienestar_automation.get_probation_questionnaire_template",
			callback: ({ message }) => {
				const template = message || {};
				const escala = template.escala || [];
				const abiertas = template.abiertas || [];

				if (!escala.length && !abiertas.length) {
					return;
				}

				const hasRows = (frm.doc.respuestas_escala || []).length || (frm.doc.respuestas_abiertas || []).length;
				if (hasRows) {
					return;
				}

				escala.forEach((row) => {
					frm.add_child("respuestas_escala", {
						dimension: row.dimension,
						pregunta: row.pregunta,
						tipo_respuesta: row.tipo_respuesta || "1-3",
						peso: row.peso || 1,
					});
				});

				abiertas.forEach((row) => {
					frm.add_child("respuestas_abiertas", {
						categoria: row.categoria,
						pregunta: row.pregunta,
					});
				});

				frm.refresh_field("respuestas_escala");
				frm.refresh_field("respuestas_abiertas");
			},
		});
	},
});
