(() => {
	function isCandidateOnlyUser() {
		if (!window.frappe || !frappe.user || !Array.isArray(frappe.user_roles)) return false;
		const roles = new Set(frappe.user_roles || []);
		return roles.has("Candidato") && !roles.has("System Manager") && !roles.has("HR Selection") && !roles.has("Gestión Humana");
	}

	function patchUserMenu() {
		if (!window.frappe || !frappe.ui || !frappe.ui.toolbar) return;

		if (isCandidateOnlyUser()) {
			const hideSelectors = [
				"a[data-label='Apps']",
				"a[data-label='Valores predeterminados de sesión']",
				"a[data-label='Mis ajustes']",
			];
			hideSelectors.forEach((selector) => {
				const el = document.querySelector(selector);
				if (el) {
					const li = el.closest("li") || el;
					li.style.display = "none";
				}
			});

			const profileLink = document.querySelector("a[data-label='Mi Perfil']");
			if (profileLink) {
				profileLink.setAttribute("href", "/app/mi-postulacion");
				profileLink.onclick = (e) => {
					e.preventDefault();
					window.location.href = "/app/mi-postulacion";
				};
			}
		}
	}

	function bootToolbarPatch() {
		setTimeout(patchUserMenu, 300);
		setTimeout(patchUserMenu, 1200);
	}

	if (window.frappe && typeof frappe.ready === "function") {
		frappe.ready(bootToolbarPatch);
	} else if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", bootToolbarPatch, { once: true });
	} else {
		bootToolbarPatch();
	}
})();
