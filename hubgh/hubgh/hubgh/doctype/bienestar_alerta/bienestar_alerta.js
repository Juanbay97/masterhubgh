frappe.ui.form.on("Bienestar Alerta", {
	refresh(frm) {
		syncBienestarAlertaContext(frm);
	},
	tipo_alerta(frm) {
		syncBienestarAlertaContext(frm);
	},
	seguimiento_ingreso(frm) {
		syncBienestarAlertaContext(frm);
	},
	evaluacion_periodo_prueba(frm) {
		syncBienestarAlertaContext(frm);
	},
	levantamiento_punto(frm) {
		syncBienestarAlertaContext(frm);
	},
	gh_novedad(frm) {
		syncBienestarAlertaContext(frm);
	},
});

const ALERTA_SOURCE_FIELDS = ["seguimiento_ingreso", "evaluacion_periodo_prueba", "levantamiento_punto", "gh_novedad"];

const ALERTA_SOURCE_BY_TYPE = {
	Ingreso: "seguimiento_ingreso",
	"Periodo de prueba": "evaluacion_periodo_prueba",
	"Levantamiento de punto": "levantamiento_punto",
};

function resolveActiveContextField(doc, sourceFields, expectedField = null) {
	if (expectedField) {
		return expectedField;
	}

	if (sourceFields.includes(doc.origen_contexto)) {
		return doc.origen_contexto;
	}

	return sourceFields.find(fieldname => !!doc[fieldname]) || null;
}

function syncBienestarAlertaContext(frm) {
	const expectedField = ALERTA_SOURCE_BY_TYPE[frm.doc.tipo_alerta] || null;
	const selectedFields = ALERTA_SOURCE_FIELDS.filter(fieldname => !!frm.doc[fieldname]);
	const activeField = resolveActiveContextField(frm.doc, ALERTA_SOURCE_FIELDS, expectedField);
	const originContext = activeField || "";

	if ((frm.doc.origen_contexto || "") !== originContext) {
		frm.set_value("origen_contexto", originContext);
	}

	ALERTA_SOURCE_FIELDS.forEach(fieldname => {
		frm.toggle_display(fieldname, !activeField || fieldname === activeField);
	});

	if (!activeField && frm.doc.tipo_alerta === "Otro") {
		frm.set_intro("Completá una sola referencia origen para activar el contexto de la alerta.", "blue");
		return;
	}

	if (selectedFields.length > 1) {
		frm.set_intro("Se muestra solo la referencia activa segun origen_contexto; las demas quedan ocultas para trazabilidad.", "blue");
		return;
	}

	frm.set_intro(null);
}
