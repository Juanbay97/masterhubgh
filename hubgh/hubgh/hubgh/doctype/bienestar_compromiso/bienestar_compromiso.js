frappe.ui.form.on("Bienestar Compromiso", {
	refresh(frm) {
		configureCompromisoQueries(frm);
		syncBienestarCompromisoContext(frm);
	},
	ficha_empleado(frm) {
		syncBienestarCompromisoContext(frm);
	},
	estado(frm) {
		syncBienestarCompromisoContext(frm);
	},
	tipo_origen_compromiso(frm) {
		syncBienestarCompromisoContext(frm);
	},
	alerta(frm) {
		syncBienestarCompromisoContext(frm);
	},
	seguimiento_ingreso(frm) {
		syncBienestarCompromisoContext(frm);
	},
	evaluacion_periodo_prueba(frm) {
		syncBienestarCompromisoContext(frm);
	},
	levantamiento_punto(frm) {
		syncBienestarCompromisoContext(frm);
	},
	gh_novedad(frm) {
		syncBienestarCompromisoContext(frm);
	},
});

const COMPROMISO_SOURCE_FIELDS = ["alerta", "seguimiento_ingreso", "evaluacion_periodo_prueba", "levantamiento_punto", "gh_novedad"];
const COMPROMISO_ORIGIN_BY_TYPE = {
	Manual: null,
	Alerta: "alerta",
	"Seguimiento ingreso": "seguimiento_ingreso",
	"Evaluacion periodo prueba": "evaluacion_periodo_prueba",
	Levantamiento: "levantamiento_punto",
	"GH Novedad": "gh_novedad",
};
const COMPROMISO_CLOSING_FIELDS = ["sin_mejora", "bitacora", "fecha_cierre"];

function configureCompromisoQueries(frm) {
	frm.set_query("seguimiento_ingreso", () => {
		const filters = {
			estado: ["in", ["Pendiente", "En gestión", "Realizado", "Vencido"]],
		};

		if (frm.doc.ficha_empleado) {
			filters.ficha_empleado = frm.doc.ficha_empleado;
		}

		return { filters };
	});

	const seguimientoField = frm.get_field("seguimiento_ingreso");
	if (seguimientoField) {
		seguimientoField.df.description = frm.doc.ficha_empleado
			? "Solo muestra seguimientos de la ficha seleccionada y estados utiles; excluye cancelados."
			: "Selecciona primero la ficha para reducir la lista a seguimientos utiles y evitar codigos sin contexto.";
		seguimientoField.refresh();
	}
}

function resolveCompromisoOriginType(doc) {
	if (Object.prototype.hasOwnProperty.call(COMPROMISO_ORIGIN_BY_TYPE, doc.tipo_origen_compromiso || "")) {
		return doc.tipo_origen_compromiso;
	}

	if (doc.origen_contexto && Object.values(COMPROMISO_ORIGIN_BY_TYPE).includes(doc.origen_contexto)) {
		return Object.keys(COMPROMISO_ORIGIN_BY_TYPE).find(label => COMPROMISO_ORIGIN_BY_TYPE[label] === doc.origen_contexto) || "Manual";
	}

	const selectedField = COMPROMISO_SOURCE_FIELDS.find(fieldname => !!doc[fieldname]);
	if (!selectedField) {
		return "Manual";
	}

	return Object.keys(COMPROMISO_ORIGIN_BY_TYPE).find(label => COMPROMISO_ORIGIN_BY_TYPE[label] === selectedField) || "Manual";
}

function sourceFieldFromType(originType) {
	return Object.prototype.hasOwnProperty.call(COMPROMISO_ORIGIN_BY_TYPE, originType || "")
		? COMPROMISO_ORIGIN_BY_TYPE[originType]
		: undefined;
}

function resolveActiveContextField(doc, originType) {
	const selectedField = sourceFieldFromType(originType);
	if (selectedField !== undefined) {
		return selectedField;
	}

	if (COMPROMISO_SOURCE_FIELDS.includes(doc.origen_contexto)) {
		return doc.origen_contexto;
	}

	return COMPROMISO_SOURCE_FIELDS.find(fieldname => !!doc[fieldname]) || null;
}

function toggleCompromisoLifecycleFields(frm) {
	const showTrackingFields = ["En seguimiento", "Cerrado", "Escalado RRLL"].includes(frm.doc.estado);
	const showClosureFields = ["Cerrado", "Escalado RRLL"].includes(frm.doc.estado);

	frm.toggle_display("punto_venta", !frm.is_new() || !!frm.doc.punto_venta);
	frm.toggle_display("sin_mejora", frm.doc.estado === "En seguimiento" || frm.doc.estado === "Escalado RRLL");
	frm.toggle_display("bitacora", showTrackingFields);
	frm.toggle_display("fecha_cierre", showClosureFields);

	COMPROMISO_CLOSING_FIELDS.forEach(fieldname => {
		frm.toggle_reqd(fieldname, false);
	});
}

function syncBienestarCompromisoContext(frm) {
	const selectedFields = COMPROMISO_SOURCE_FIELDS.filter(fieldname => !!frm.doc[fieldname]);
	const originType = resolveCompromisoOriginType(frm.doc);
	const activeField = resolveActiveContextField(frm.doc, originType);
	const originContext = activeField || "";
	const expectsOrigin = originType !== "Manual";

	configureCompromisoQueries(frm);
	toggleCompromisoLifecycleFields(frm);

	if ((frm.doc.tipo_origen_compromiso || "") !== originType) {
		frm.set_value("tipo_origen_compromiso", originType);
	}

	if ((frm.doc.origen_contexto || "") !== originContext) {
		frm.set_value("origen_contexto", originContext);
	}

	COMPROMISO_SOURCE_FIELDS.forEach(fieldname => {
		frm.toggle_display(fieldname, expectsOrigin && fieldname === activeField);
	});

	if (!expectsOrigin) {
		frm.set_intro(null);
		return;
	}

	if (!activeField || !frm.doc[activeField]) {
		frm.set_intro("Selecciona el origen y completa una sola referencia activa para crear el compromiso.", "blue");
		return;
	}

	if (selectedFields.length > 1) {
		frm.set_intro("Se muestra solo la referencia activa segun origen_contexto; las demas quedan ocultas para trazabilidad.", "blue");
		return;
	}

	frm.set_intro(null);
}
