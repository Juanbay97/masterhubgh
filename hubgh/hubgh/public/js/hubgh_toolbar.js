(() => {
	// ── SVG Icon Sprite — iconos custom para workspaces HubGH ─────────────────
	// Frappe usa <use href="#icon-{name}"> para workspace icons.
	// Los symbols deben estar INLINE en el DOM. app_include_icons no es fiable
	// en v15, por eso los inyectamos directamente desde este script.
	const ICON_SPRITE = `<svg xmlns="http://www.w3.org/2000/svg" id="hubgh-icon-sprite"
		aria-hidden="true" style="position:absolute;width:0;height:0;overflow:hidden">
		<defs>
		<symbol id="icon-gh" viewBox="0 0 24 24" fill="none" stroke="currentColor"
			stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
			<path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
			<circle cx="9" cy="7" r="4"/>
			<path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
			<path d="M16 3.13a4 4 0 0 1 0 7.75"/>
		</symbol>
		<symbol id="icon-nomina" viewBox="0 0 24 24" fill="none" stroke="currentColor"
			stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
			<line x1="12" y1="1" x2="12" y2="23"/>
			<path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>
		</symbol>
		<symbol id="icon-operacion" viewBox="0 0 24 24" fill="none" stroke="currentColor"
			stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
			<polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
		</symbol>
		<symbol id="icon-relaciones" viewBox="0 0 24 24" fill="none" stroke="currentColor"
			stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
			<rect x="2" y="7" width="20" height="14" rx="2" ry="2"/>
			<path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/>
		</symbol>
		<symbol id="icon-postulacion" viewBox="0 0 24 24" fill="none" stroke="currentColor"
			stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
			<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
			<polyline points="14 2 14 8 20 8"/>
			<line x1="16" y1="13" x2="8" y2="13"/>
			<line x1="16" y1="17" x2="8" y2="17"/>
		</symbol>
		<symbol id="icon-mi-perfil" viewBox="0 0 24 24" fill="none" stroke="currentColor"
			stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
			<path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/>
			<circle cx="12" cy="7" r="4"/>
		</symbol>
		<symbol id="icon-seleccion" viewBox="0 0 24 24" fill="none" stroke="currentColor"
			stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
			<circle cx="11" cy="11" r="8"/>
			<line x1="21" y1="21" x2="16.65" y2="16.65"/>
			<path d="M11 8a3 3 0 1 0 0 6 3 3 0 0 0 0-6z"/>
		</symbol>
		<symbol id="icon-bienestar" viewBox="0 0 24 24" fill="none" stroke="currentColor"
			stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
			<path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/>
		</symbol>
		<symbol id="icon-hubgh-admin" viewBox="0 0 24 24" fill="none" stroke="currentColor"
			stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
			<circle cx="12" cy="12" r="3"/>
			<path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
		</symbol>
		<symbol id="icon-sst" viewBox="0 0 24 24" fill="none" stroke="currentColor"
			stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
			<path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11z"/>
		</symbol>
		</defs>
	</svg>`;

	function injectIconSprite() {
		if (document.getElementById("hubgh-icon-sprite")) return;
		document.body.insertAdjacentHTML("afterbegin", ICON_SPRITE);
	}

	// ── Logo adaptable por tema ──────────────────────────────────────────────
	const LOGOS = {
		navbar: {
			light: "/assets/hubgh/images/logo-home-negro.png",
			dark:  "/assets/hubgh/images/logo-home-blanco.png",
		},
		loading: {
			light: "/assets/hubgh/images/logo-circular-black.png",
			dark:  "/assets/hubgh/images/logo-circular-white.png",
		},
	};

	function getCurrentTheme() {
		return document.documentElement.getAttribute("data-theme") || "light";
	}

	function applyLogo() {
		const theme = getCurrentTheme();
		const isDark = theme === "dark";

		// Navbar
		const navLogo = document.querySelector(
			".navbar-brand img.app-logo, .navbar-header img.app-logo, .navbar img.app-logo"
		);
		if (navLogo) {
			navLogo.src = isDark ? LOGOS.navbar.dark : LOGOS.navbar.light;
			navLogo.alt = "Hub GH";
			navLogo.style.height = "38px";
			navLogo.style.width = "auto";
		}

		// Loading screen
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
		// Re-aplicar después del render de Frappe
		setTimeout(applyLogo, 500);
		setTimeout(applyLogo, 1500);
	}

	// ── User menu patch ──────────────────────────────────────────────────────
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

	function boot() {
		injectIconSprite(); // ← inyectar SVG primero, antes de cualquier render
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
