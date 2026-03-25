frappe.pages["relaciones_laborales_contratacion"].on_page_load = function(wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: "Relaciones Laborales - Contratación",
		single_column: true,
	});

	const $root = $("<div class='p-4'></div>").appendTo(page.body);
	$root.html(`
		<div class="alert alert-info" style="max-width: 920px; margin: 12px auto;">
			<h4 style="margin-top:0;">Flujo unificado de contratación</h4>
			<p style="margin-bottom:12px;">Esta página se consolidó en la nueva <b>Bandeja de Contratación</b> para evitar duplicidades.</p>
			<button class="btn btn-primary btn-go">Ir a Bandeja de Contratación</button>
		</div>
	`);

	$root.find(".btn-go").on("click", () => {
		frappe.set_route("bandeja_contratacion");
	});
};
