(() => {
	// ── Branding de HubGH para páginas web (login, web forms, etc.) ──────────
	// Se carga via web_include_js, aplica a todas las páginas web (no solo el desk).
	// El CSS content:url() solo funciona en <img>; este JS cubre SVG, div y span.

	const LOGO_URL = "/assets/hubgh/images/logo-circular-black.png";

	function setFavicon(url) {
		let link = document.querySelector("link[rel~='icon']") ||
		           document.querySelector("link[rel='shortcut icon']");
		if (!link) {
			link = document.createElement("link");
			link.rel = "icon";
			document.head.appendChild(link);
		}
		link.href = url;
	}
	setFavicon(LOGO_URL);

	function injectBrandLogo() {
		// 1. Reemplazar <img> que apunten al logo de Frappe por defecto
		const frappe_img_selectors = [
			'img[src*="frappe-favicon"]',
			'img[src*="frappe-logo"]',
			'img[src*="frappe_logo"]',
			".page-card-head img",
			".frappe-logo img",
			".brand-logo img",
			"img.frappe-logo",
			"img.website-logo",
		];
		frappe_img_selectors.forEach((sel) => {
			document.querySelectorAll(sel).forEach((img) => {
				img.src = LOGO_URL;
				img.style.cssText =
					"width:56px;height:56px;border-radius:0;background:none;box-shadow:none;";
			});
		});

		// 2. Ocultar SVG del icono Frappe e inyectar nuestra imagen al lado
		const svg_containers = [
			".page-card-head svg",
			".page-card-head .icon-container",
			".page-card-head .app-icon",
			".page-card-head .brand-icon",
			".page-card-head .frappe-logo",
		];
		svg_containers.forEach((sel) => {
			document.querySelectorAll(sel).forEach((el) => {
				// Evitar duplicados
				if (el.closest(".hubgh-injected")) return;

				el.style.display = "none";

				const wrapper = el.parentNode;
				if (!wrapper.querySelector(".hubgh-login-logo")) {
					const img = document.createElement("img");
					img.src = LOGO_URL;
					img.alt = "HubGH";
					img.className = "hubgh-login-logo";
					img.style.cssText =
						"width:56px;height:56px;border-radius:0;display:block;margin:0 auto 8px;";
					wrapper.insertBefore(img, el);
				}
			});
		});
	}

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", injectBrandLogo, {
			once: true,
		});
	} else {
		injectBrandLogo();
	}
})();
