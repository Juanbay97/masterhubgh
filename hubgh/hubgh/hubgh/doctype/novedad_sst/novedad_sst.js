// Copyright (c) 2026, Antigravity and contributors
// For license information, please see license.txt

const PRORROGA_INCAPACIDAD = "Prórroga incapacidad";

frappe.ui.form.on("Novedad SST", {
	refresh(frm) {
		sync_incapacidad_ui(frm);
		sync_prorroga_rows(frm);
		add_prorroga_action(frm);
	},
	es_incapacidad(frm) {
		if (frm.doc.es_incapacidad) {
			if (!["Incapacidad", "Incapacidad por enfermedad general"].includes(frm.doc.tipo_novedad)) {
				frm.set_value("tipo_novedad", "Incapacidad por enfermedad general");
			}
		}
		sync_incapacidad_ui(frm);
	},
	tipo_novedad(frm) {
		const isIncapacidad = ["Incapacidad", "Incapacidad por enfermedad general"].includes(frm.doc.tipo_novedad);
		frm.set_value("es_incapacidad", isIncapacidad ? 1 : 0);
		sync_incapacidad_ui(frm);
	},
	prorroga(frm) {
		sync_incapacidad_ui(frm);
	},
	prorrogas_incapacidad_add(frm, cdt, cdn) {
		frappe.model.set_value(cdt, cdn, "tipo_seguimiento", PRORROGA_INCAPACIDAD);
	},
});

function sync_incapacidad_ui(frm) {
	const isIncapacidad = !!frm.doc.es_incapacidad || ["Incapacidad", "Incapacidad por enfermedad general"].includes(frm.doc.tipo_novedad);
	const showProrroga = isIncapacidad || (frm.doc.tipo_novedad === "Accidente" && !!frm.doc.accidente_tuvo_incapacidad);

	frm.toggle_display("section_incapacidad", showProrroga);
	frm.toggle_display("origen_incapacidad", showProrroga);
	frm.toggle_display("diagnostico_corto", showProrroga);
	frm.toggle_display("evidencia_incapacidad", showProrroga);
	frm.toggle_display("fecha_inicio", showProrroga || frm.doc.tipo_novedad === "Recomendación Médica");
	frm.toggle_display("fecha_fin", showProrroga || frm.doc.tipo_novedad === "Recomendación Médica");
	frm.toggle_display("prorroga", showProrroga);
	frm.toggle_display("prorrogas_incapacidad", showProrroga && !!frm.doc.prorroga);
}

function sync_prorroga_rows(frm) {
	(frm.doc.prorrogas_incapacidad || []).forEach((row) => {
		if (row.tipo_seguimiento !== PRORROGA_INCAPACIDAD) {
			frappe.model.set_value(row.doctype, row.name, "tipo_seguimiento", PRORROGA_INCAPACIDAD);
		}
	});
}

function add_prorroga_action(frm) {
	const canAddProrroga = !!frm.doc.es_incapacidad || ["Incapacidad", "Incapacidad por enfermedad general"].includes(frm.doc.tipo_novedad) || (frm.doc.tipo_novedad === "Accidente" && !!frm.doc.accidente_tuvo_incapacidad);
	if (!canAddProrroga || frm.is_new()) {
		return;
	}

	frm.add_custom_button("Agregar prórroga", () => {
		frm.set_value("prorroga", 1);
		const row = frm.add_child("prorrogas_incapacidad", {
			tipo_seguimiento: PRORROGA_INCAPACIDAD,
		});
		frm.refresh_field("prorrogas_incapacidad");
		frm.scroll_to_field("prorrogas_incapacidad");
		if (row?.doctype && row?.name) {
			frappe.model.set_value(row.doctype, row.name, "tipo_seguimiento", PRORROGA_INCAPACIDAD);
		}
	}, __("Acciones"));
}
