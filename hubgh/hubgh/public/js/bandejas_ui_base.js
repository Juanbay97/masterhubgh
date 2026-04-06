(() => {
	if (window.hubghBandejasUI) return;

	const BASE_STYLE_ID = "hubgh-bandejas-ui-base-style";

	const baseCss = `
		.hubgh-board-shell { display: grid; gap: 12px; }
		.hubgh-board-hero {
			display: grid;
			gap: 10px;
			background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
			border: 1px solid #e2e8f0;
			border-radius: 14px;
			padding: 14px;
		}
		.hubgh-board-hero-head {
			display: flex;
			justify-content: space-between;
			align-items: flex-start;
			gap: 12px;
			flex-wrap: wrap;
		}
		.hubgh-board-kickers { display: flex; gap: 8px; flex-wrap: wrap; }
		.hubgh-board-kicker {
			display: inline-flex;
			align-items: center;
			gap: 6px;
			border-radius: 999px;
			padding: 4px 10px;
			font-size: 11px;
			font-weight: 700;
			letter-spacing: .02em;
			color: #1e3a8a;
			background: #dbeafe;
		}
		.hubgh-board-title { font-size: 18px; font-weight: 700; color: #0f172a; margin: 0; }
		.hubgh-board-copy { color: #475569; font-size: 13px; margin: 0; max-width: 780px; }
		.hubgh-board-meta { display: flex; gap: 8px; flex-wrap: wrap; }
		.hubgh-meta-pill {
			display: inline-flex;
			align-items: center;
			gap: 6px;
			padding: 5px 10px;
			border-radius: 999px;
			background: #eff6ff;
			color: #1d4ed8;
			font-size: 12px;
			font-weight: 600;
		}
		.hubgh-board-shortcuts { display: flex; gap: 8px; flex-wrap: wrap; }
		.hubgh-board-toolbar {
			display: flex;
			gap: 10px;
			align-items: center;
			flex-wrap: wrap;
			background: #fff;
			border: 1px solid #e2e8f0;
			border-radius: 12px;
			padding: 10px 12px;
		}
		.hubgh-board-toolbar-copy { color: #64748b; font-size: 12px; margin-left: auto; }
		.hubgh-board-toolbar .filter-search { max-width: 520px; min-width: 220px; }
		.hubgh-board-toolbar .filter-status { max-width: 260px; }
		.hubgh-section-head {
			display: flex;
			justify-content: space-between;
			align-items: center;
			gap: 10px;
			flex-wrap: wrap;
		}
		.hubgh-section-title { font-size: 14px; font-weight: 700; color: #0f172a; margin: 0; }
		.hubgh-section-copy { color: #64748b; font-size: 12px; margin: 0; }
		.hubgh-count-pill {
			min-width: 28px;
			padding: 3px 9px;
			text-align: center;
			border-radius: 999px;
			background: #eff6ff;
			color: #1d4ed8;
			font-size: 12px;
			font-weight: 700;
		}
		.hubgh-cards-wrap { display: grid; gap: 12px; }
		.hubgh-card {
			background: #fff;
			border: 1px solid #e2e8f0;
			border-radius: 14px;
			padding: 14px;
			display: grid;
			gap: 12px;
		}
		.hubgh-card-head { display: flex; justify-content: space-between; gap: 14px; align-items: flex-start; }
		.hubgh-main { min-width: 0; }
		.hubgh-title-row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
		.hubgh-name {
			font-size: 15px;
			font-weight: 700;
			color: #1f2937;
			padding: 0;
			margin: 0;
			max-width: 100%;
			overflow: hidden;
			text-overflow: ellipsis;
			white-space: nowrap;
		}
		.hubgh-name:hover, .hubgh-name:focus { color: #2563eb; text-decoration: underline; }
		.hubgh-meta, .hubgh-submeta, .hubgh-time { color: #64748b; font-size: 12px; }
		.hubgh-submeta { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }
		.hubgh-dot { color: #94a3b8; }
		.hubgh-right { text-align: right; }
		.hubgh-badges-grid { display: grid; grid-template-columns: repeat(3, minmax(150px, 1fr)); gap: 8px; }
		.hubgh-badge {
			display: flex;
			justify-content: space-between;
			align-items: center;
			border: 1px solid #e2e8f0;
			border-radius: 10px;
			padding: 8px 10px;
			background: #f8fafc;
			gap: 10px;
		}
		.hubgh-badge.is-complete { border-color: #86efac; background: #f0fdf4; }
		.hubgh-badge.is-pending { border-color: #fed7aa; background: #fff7ed; }
		.hubgh-badge-label { font-size: 12px; font-weight: 600; color: #475569; }
		.hubgh-actions { display: flex; gap: 8px; justify-content: flex-end; flex-wrap: wrap; }
		.hubgh-empty {
			background: #fff;
			border: 1px dashed #cbd5e1;
			border-radius: 12px;
			padding: 16px;
			color: #64748b;
			font-size: 13px;
		}
		.hubgh-empty-title { display: block; font-weight: 700; color: #334155; margin-bottom: 4px; }
		.hubgh-empty-copy { margin: 0; }
		.hubgh-table-shell {
			background: #fff;
			border: 1px solid #e2e8f0;
			border-radius: 14px;
			overflow: hidden;
		}
		.hubgh-table-wrap { overflow: auto; }
		.hubgh-table { margin: 0; font-size: 12px; }
		.hubgh-table thead th {
			background: #f8fafc;
			border-bottom: 1px solid #e2e8f0;
			color: #334155;
			font-weight: 700;
			white-space: nowrap;
		}
		.hubgh-table tbody td { vertical-align: top; padding: 9px 10px; }
		.hubgh-cell-stack { display: grid; gap: 2px; }
		.hubgh-cell-main { color: #0f172a; font-weight: 600; }
		.hubgh-cell-sub { color: #64748b; font-size: 11px; }
		.hubgh-mobile-stack { display: none; }
		@media (max-width: 768px) {
			.hubgh-board-hero,
			.hubgh-board-toolbar,
			.hubgh-card { padding: 12px; }
			.hubgh-badges-grid { grid-template-columns: repeat(2, minmax(120px, 1fr)); }
			.hubgh-board-toolbar .filter-search,
			.hubgh-board-toolbar .filter-status { max-width: 100%; min-width: 0; width: 100%; }
			.hubgh-board-toolbar-copy { margin-left: 0; width: 100%; }
			.hubgh-mobile-stack { display: grid; }
		}
	`;

	const injectStyle = (styleId, css) => {
		if (document.getElementById(styleId)) return;
		const style = document.createElement("style");
		style.id = styleId;
		style.innerHTML = css;
		document.head.appendChild(style);
	};

	const esc = value => frappe.utils.escape_html(value == null ? "" : String(value));

	const indicator = (tone, label) => `<span class='indicator-pill ${esc(tone)}'>${esc(label)}</span>`;

	const yesNoBadge = ok => ok
		? indicator("green", "Completo")
		: indicator("orange", "Pendiente");

	window.hubghBandejasUI = {
		injectBaseStyles() {
			injectStyle(BASE_STYLE_ID, baseCss);
		},
		injectScopedStyles(scope, css) {
			injectStyle(`hubgh-bandejas-ui-${scope}`, css);
		},
		esc,
		indicator,
		yesNoBadge,
	};
})();
