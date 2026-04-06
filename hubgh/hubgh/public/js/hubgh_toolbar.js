(() => {
	// ── Logo adaptable por tema ──────────────────────────────────────────────
	const LOGOS = {
		navbar: {
			light: "/assets/hubgh/images/logo-home-negro.png",
			dark: "/assets/hubgh/images/logo-home-blanco.png",
		},
		loading: {
			light: "/assets/hubgh/images/logo-circular-black.png",
			dark: "/assets/hubgh/images/logo-circular-white.png",
		},
	};

	function getCurrentTheme() {
		return document.documentElement.getAttribute("data-theme") || "light";
	}

	function applyLogo() {
		const theme = getCurrentTheme();
		const isDark = theme === "dark";

		const navLogo = document.querySelector(
			".navbar-brand img.app-logo, .navbar-header img.app-logo, .navbar img.app-logo"
		);
		if (navLogo) {
			navLogo.src = isDark ? LOGOS.navbar.dark : LOGOS.navbar.light;
			navLogo.alt = "Hub GH";
			navLogo.style.height = "38px";
			navLogo.style.width = "auto";
		}

		const loadingLogo = document.querySelector(
			".page-loading img, #loading img, .frappe-loading img"
		);
		if (loadingLogo) {
			loadingLogo.src = isDark ? LOGOS.loading.dark : LOGOS.loading.light;
		}
	}

	function watchTheme() {
		const observer = new MutationObserver(() => applyLogo());
		observer.observe(document.documentElement, {
			attributes: true,
			attributeFilter: ["data-theme"],
		});
	}

	function bootLogo() {
		applyLogo();
		watchTheme();
		setTimeout(applyLogo, 500);
		setTimeout(applyLogo, 1500);
	}

	// ── User menu patch ──────────────────────────────────────────────────────
	function isCandidateOnlyUser() {
		if (!window.frappe || !frappe.user || !Array.isArray(frappe.user_roles))
			return false;
		const roles = new Set(frappe.user_roles || []);
		return (
			roles.has("Candidato") &&
			!roles.has("System Manager") &&
			!roles.has("HR Selection") &&
			!roles.has("Gestión Humana")
		);
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

			const profileLink = document.querySelector(
				"a[data-label='Mi Perfil']"
			);
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

	// ── Boot ─────────────────────────────────────────────────────────────────
	function boot() {
		bootLogo();
		bootToolbarPatch();
	}

	if (window.frappe && typeof frappe.ready === "function") {
		frappe.ready(boot);
	} else if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", boot, { once: true });
	} else {
		boot();
	}
})();
