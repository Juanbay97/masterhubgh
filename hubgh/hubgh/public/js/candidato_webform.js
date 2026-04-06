frappe.web_form.after_load = () => {
	if (frappe.session && frappe.session.user === "Guest") {
		console.info("candidato_webform:guest_user");
		return;
	}
	console.info("candidato_webform:after_load", {
		route: window.location.pathname,
		user: frappe.session && frappe.session.user
	});
	frappe.call("hubgh.hubgh.page.seleccion_documentos.seleccion_documentos.get_current_candidate")
		.then(r => {
			console.info("candidato_webform:get_current_candidate", r.message);
			if (r.message) {
				frappe.web_form.docname = r.message;
				frappe.web_form.load();
			}
		});
};

frappe.web_form.after_save = () => {
	if (frappe.session && frappe.session.user !== "Guest") {
		window.location.href = "/app/seleccion_documentos";
	}
};
