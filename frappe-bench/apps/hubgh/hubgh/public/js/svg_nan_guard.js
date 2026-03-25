(() => {
	if (window.hubghSvgNaNGuardInstalled) return;
	window.hubghSvgNaNGuardInstalled = true;

	const TARGET_PATHS = ["/app/candidato", "/app/mi-postulacion", "/candidato"];

	const isTargetRoute = () => {
		const path = window.location.pathname || "";
		return TARGET_PATHS.some((target) => path === target || path.startsWith(`${target}/`));
	};

	if (!isTargetRoute()) return;

	const NUMERIC_ATTRS = new Set([
		"x",
		"x1",
		"x2",
		"y",
		"y1",
		"y2",
		"cx",
		"cy",
		"r",
		"rx",
		"ry",
		"width",
		"height",
	]);

	const sanitizeNumber = (value) => {
		if (value == null) return null;
		const text = String(value).trim();
		if (!text || text.toLowerCase() === "nan") return "0";
		const parsed = Number(text);
		if (Number.isNaN(parsed) || !Number.isFinite(parsed)) return "0";
		return null;
	};

	const sanitizeTranslate = (value) => {
		if (value == null) return null;
		const text = String(value);
		if (!/translate\(/i.test(text) || !/NaN/i.test(text)) return null;
		return text
			.replace(/translate\(([^,\)]+),\s*([^\)]+)\)/gi, (_m, x, y) => {
				const sx = sanitizeNumber(x) === "0" ? "0" : x;
				const sy = sanitizeNumber(y) === "0" ? "0" : y;
				return `translate(${sx}, ${sy})`;
			})
			.replace(/NaN/gi, "0");
	};

	const sanitizePathD = (value) => {
		if (value == null) return null;
		const text = String(value);
		if (!/NaN/i.test(text)) return null;
		return text.replace(/NaN/gi, "0");
	};

	const sanitizeElement = (el) => {
		if (!el || !el.getAttribute || !el.setAttribute) return;
		if (!(el instanceof SVGElement)) return;

		for (const attr of NUMERIC_ATTRS) {
			if (!el.hasAttribute(attr)) continue;
			const current = el.getAttribute(attr);
			const fixed = sanitizeNumber(current);
			if (fixed !== null) {
				el.setAttribute(attr, fixed);
				console.warn("[hubgh][svg-guard] sanitized numeric SVG attribute", {
					attr,
					before: current,
					after: fixed,
					tag: el.tagName,
				});
			}
		}

		if (el.hasAttribute("transform")) {
			const current = el.getAttribute("transform");
			const fixed = sanitizeTranslate(current);
			if (fixed !== null && fixed !== current) {
				el.setAttribute("transform", fixed);
				console.warn("[hubgh][svg-guard] sanitized transform", { before: current, after: fixed, tag: el.tagName });
			}
		}

		if (el.tagName?.toLowerCase() === "path" && el.hasAttribute("d")) {
			const current = el.getAttribute("d");
			const fixed = sanitizePathD(current);
			if (fixed !== null && fixed !== current) {
				el.setAttribute("d", fixed);
				console.warn("[hubgh][svg-guard] sanitized path d", { before: current, after: fixed });
			}
		}
	};

	const walk = (root) => {
		if (!root) return;
		if (root instanceof SVGElement) sanitizeElement(root);
		if (!root.querySelectorAll) return;
		root.querySelectorAll("svg, g, line, path, rect, circle, ellipse").forEach(sanitizeElement);
	};

	const observe = () => {
		walk(document);
		const observer = new MutationObserver((mutations) => {
			for (const mutation of mutations) {
				if (mutation.type === "attributes" && mutation.target instanceof SVGElement) {
					sanitizeElement(mutation.target);
				}
				if (mutation.type === "childList") {
					mutation.addedNodes.forEach((node) => {
						if (node instanceof Element) walk(node);
					});
				}
			}
		});

		observer.observe(document.documentElement, {
			subtree: true,
			childList: true,
			attributes: true,
			attributeFilter: ["width", "height", "x", "x1", "x2", "y", "y1", "y2", "transform", "d"],
		});
	};

	if (document.readyState === "loading") {
		document.addEventListener("DOMContentLoaded", observe, { once: true });
	} else {
		observe();
	}
})();

