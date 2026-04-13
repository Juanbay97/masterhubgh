class PayrollImportUploader {
	constructor() {
		this.currentRun = null;
		this.currentRunMeta = null;
		this.formOptions = { sources: [], periods: [] };
		this.catalogLinks = {
			sources: "/app/payroll-source-catalog",
			periods: "/app/payroll-period-config",
		};

		this.initializeElements();
		this.bindEvents();
		void this.loadFormData();
	}

	initializeElements() {
		this.uploadForm = document.getElementById("uploadForm");
		this.loadingState = document.getElementById("loadingState");
		this.previewSection = document.getElementById("previewSection");
		this.successSection = document.getElementById("successSection");
		this.alertContainer = document.getElementById("alertContainer");

		this.sourceFile = document.getElementById("sourceFile");
		this.sourceType = document.getElementById("sourceType");
		this.period = document.getElementById("period");
		this.previewBtn = document.getElementById("previewBtn");
		this.commitBtn = document.getElementById("commitBtn");
		this.cancelBtn = document.getElementById("cancelBtn");

		this.totalRows = document.getElementById("totalRows");
		this.validRows = document.getElementById("validRows");
		this.errorRows = document.getElementById("errorRows");
		this.duplicateRows = document.getElementById("duplicateRows");
		this.previewMeta = document.getElementById("previewMeta");
		this.previewTableBody = document.getElementById("previewTableBody");
		this.previewEmptyState = document.getElementById("previewEmptyState");

		this.formStatusChip = document.getElementById("formStatusChip");
		this.previewStatusChip = document.getElementById("previewStatusChip");
		this.sourceHelper = document.getElementById("sourceHelper");
		this.periodHelper = document.getElementById("periodHelper");
		this.sourceBadge = document.getElementById("sourceBadge");
		this.periodBadge = document.getElementById("periodBadge");
		this.sourceEmptyState = document.getElementById("sourceEmptyState");
		this.periodEmptyState = document.getElementById("periodEmptyState");
		this.sourceCatalogLink = document.getElementById("sourceCatalogLink");
		this.periodCatalogLink = document.getElementById("periodCatalogLink");
		this.sourcesAvailableCount = document.getElementById("sourcesAvailableCount");
		this.periodsAvailableCount = document.getElementById("periodsAvailableCount");
		this.sourcesAvailableNote = document.getElementById("sourcesAvailableNote");
		this.periodsAvailableNote = document.getElementById("periodsAvailableNote");
		this.formAvailabilityHeadline = document.getElementById("formAvailabilityHeadline");
		this.formAvailabilityNote = document.getElementById("formAvailabilityNote");
	}

	bindEvents() {
		this.uploadForm.addEventListener("submit", this.handleUpload.bind(this));
		this.commitBtn.addEventListener("click", this.handleCommit.bind(this));
		this.cancelBtn.addEventListener("click", this.handleCancel.bind(this));
		this.sourceFile.addEventListener("change", this.autoDetectSource.bind(this));
		this.sourceFile.addEventListener("change", this.refreshPreviewButtonState.bind(this));
		this.sourceType.addEventListener("change", this.refreshPreviewButtonState.bind(this));
		this.period.addEventListener("change", this.refreshPreviewButtonState.bind(this));
	}

	async loadFormData() {
		this.setFormStatus("Cargando catalogos...");
		try {
			const response = await frappe.call({
				method: "hubgh.hubgh.payroll_import_upload_api.get_upload_form_options",
			});
			const payload = response.message || {};
			this.formOptions.sources = payload.sources || [];
			this.formOptions.periods = payload.periods || [];
			this.catalogLinks = {
				sources: payload.catalog_links?.sources || this.catalogLinks.sources,
				periods: payload.catalog_links?.periods || this.catalogLinks.periods,
			};

			this.sourceCatalogLink.href = this.catalogLinks.sources;
			this.periodCatalogLink.href = this.catalogLinks.periods;

			this.renderSelectOptions(this.sourceType, this.formOptions.sources, "Seleccionar fuente...");
			this.renderSelectOptions(this.period, this.formOptions.periods, "Seleccionar periodo...");
			this.renderAvailability(payload.empty_states || {});
		} catch (error) {
			this.renderAvailability({ sources: true, periods: true });
			this.showAlert(this.getErrorMessage(error, "No se pudieron cargar los catalogos del formulario."), "error", "Error cargando formulario");
		}
	}

	renderSelectOptions(selectElement, options, placeholder) {
		selectElement.innerHTML = "";
		const placeholderOption = document.createElement("option");
		placeholderOption.value = "";
		placeholderOption.textContent = placeholder;
		selectElement.appendChild(placeholderOption);

		options.forEach((optionData) => {
			const option = document.createElement("option");
			option.value = optionData.value;
			option.textContent = this.formatOptionLabel(selectElement.id, optionData);
			selectElement.appendChild(option);
		});
	}

	formatOptionLabel(selectId, optionData) {
		if (selectId === "period") {
			const periodParts = [optionData.nombre_periodo || optionData.label || optionData.value];
			if (optionData.ano && optionData.mes) {
				periodParts.push(`${optionData.ano}-${String(optionData.mes).padStart(2, "0")}`);
			}
			return periodParts.join(" · ");
		}

		const sourceParts = [optionData.label || optionData.value];
		if (optionData.periodicidad) {
			sourceParts.push(optionData.periodicidad);
		}
		return sourceParts.join(" · ");
	}

	renderAvailability(emptyStates) {
		const hasSources = this.formOptions.sources.length > 0 && !emptyStates.sources;
		const hasPeriods = this.formOptions.periods.length > 0 && !emptyStates.periods;

		this.sourceEmptyState.classList.toggle("hidden", hasSources);
		this.periodEmptyState.classList.toggle("hidden", hasPeriods);
		this.sourceType.disabled = !hasSources;
		this.period.disabled = !hasPeriods;
		this.updateAvailabilitySummary(hasSources, hasPeriods);
		this.refreshPreviewButtonState();

		this.sourceHelper.textContent = hasSources
			? `${this.formOptions.sources.length} fuente${this.formOptions.sources.length === 1 ? "" : "s"} activa${this.formOptions.sources.length === 1 ? "" : "s"} disponible${this.formOptions.sources.length === 1 ? "" : "s"}.`
			: "No hay fuentes activas. Usa el CTA para completar el catalogo.";
		this.periodHelper.textContent = hasPeriods
			? `${this.formOptions.periods.length} periodo${this.formOptions.periods.length === 1 ? "" : "s"} activo${this.formOptions.periods.length === 1 ? "" : "s"} disponible${this.formOptions.periods.length === 1 ? "" : "s"}.`
			: "No hay periodos activos. Activa o crea uno desde el catalogo.";

		if (hasSources && hasPeriods) {
			this.setFormStatus("Formulario listo para cargar");
		} else {
			this.setFormStatus("Faltan catalogos obligatorios");
		}
	}

	updateAvailabilitySummary(hasSources, hasPeriods) {
		const latestPeriod = this.formOptions.periods[0];
		const latestPeriodLabel = latestPeriod ? this.formatOptionLabel("period", latestPeriod) : "Sin periodos activos";

		this.sourcesAvailableCount.textContent = this.formOptions.sources.length;
		this.periodsAvailableCount.textContent = this.formOptions.periods.length;
		this.sourcesAvailableNote.textContent = hasSources
			? "Combo cargado desde Payroll Source Catalog con status Active."
			: "No hay fuentes activas para el combo.";
		this.periodsAvailableNote.textContent = hasPeriods
			? `Ultimo periodo detectado: ${latestPeriodLabel}.`
			: "No hay periodos activos para el combo.";

		this.sourceBadge.textContent = hasSources ? `${this.formOptions.sources.length} activas` : "Sin datos";
		this.periodBadge.textContent = hasPeriods ? `${this.formOptions.periods.length} activos` : "Sin datos";

		if (hasSources && hasPeriods) {
			this.formAvailabilityHeadline.textContent = "Listo";
			this.formAvailabilityNote.textContent = "Ya puedes elegir archivo, fuente y periodo para generar la vista previa.";
			return;
		}

		if (!hasSources && !hasPeriods) {
			this.formAvailabilityHeadline.textContent = "Pendiente";
			this.formAvailabilityNote.textContent = "Faltan ambos catalogos obligatorios. Usa los CTA laterales para completarlos.";
			return;
		}

		this.formAvailabilityHeadline.textContent = "Parcial";
		this.formAvailabilityNote.textContent = !hasSources
			? "Solo falta activar una fuente para habilitar el formulario completo."
			: "Solo falta activar un periodo para habilitar el formulario completo.";
	}

	refreshPreviewButtonState() {
		const hasCatalogs = !this.sourceType.disabled && !this.period.disabled;
		const hasFile = Boolean(this.sourceFile.files?.length);
		this.previewBtn.disabled = !(hasCatalogs && hasFile && this.sourceType.value && this.period.value);
	}

	setFormStatus(message) {
		this.formStatusChip.textContent = message;
	}

	autoDetectSource() {
		const files = Array.from(this.sourceFile.files || []);
		if (!files.length || !this.formOptions.sources.length) {
			return;
		}

		const filename = files[0].name.toLowerCase();
		const matchers = [
			{ match: ["clonk", "toda la empresa"], value: "clonk" },
			{ match: ["payflow"], value: "payflow" },
			{ match: ["fincomercio"], value: "fincomercio" },
			{ match: ["fondo", "fongiga"], value: "fondo" },
			{ match: ["libranza"], value: "libranza" },
		];

		const detected = matchers.find((entry) => entry.match.some((token) => filename.includes(token)));
		if (!detected) {
			return;
		}

		const source = this.formOptions.sources.find((option) => {
			const label = (option.label || "").toLowerCase();
			const type = (option.tipo_fuente || "").toLowerCase();
			return label.includes(detected.value) || type.includes(detected.value);
		});

		if (source) {
			this.sourceType.value = source.value;
			this.refreshPreviewButtonState();
			this.showAlert(`Se selecciono automaticamente la fuente ${source.label}.`, "info", "Fuente detectada");
		}
	}

	async handleUpload(event) {
		event.preventDefault();
		this.alertContainer.innerHTML = "";

		const files = Array.from(this.sourceFile.files || []);
		if (!files.length) {
			this.showAlert("Selecciona al menos un archivo Excel antes de continuar.", "warning", "Archivo requerido");
			return;
		}
		if (!this.sourceType.value) {
			this.showAlert("Selecciona una fuente activa para identificar el origen del archivo.", "warning", "Fuente requerida");
			return;
		}
		if (!this.period.value) {
			this.showAlert("Selecciona un periodo activo para crear el lote.", "warning", "Periodo requerido");
			return;
		}

		try {
			this.showLoading();
			const fileUrls = await Promise.all(files.map((file) => this.uploadFile(file)));
			const run = await this.createRun(fileUrls);
			this.currentRun = run.run_id;
			this.currentRunMeta = run;
			const result = await this.processPreview();
			await this.showPreview(result, run);
		} catch (error) {
			this.hideLoading();
			this.showAlert(this.getErrorMessage(error, "Ocurrio un problema procesando el archivo."), "error", "Error procesando archivo");
		}
	}

	async uploadFile(file) {
		const formData = new FormData();
		formData.append("file", file);
		formData.append("is_private", 1);
		formData.append("folder", "Home/Attachments");

		const response = await window.fetch("/api/method/upload_file", {
			method: "POST",
			body: formData,
			credentials: "same-origin",
			headers: {
				"X-Frappe-CSRF-Token": frappe.csrf_token,
			},
		});
		const payload = await response.json();
		const fileUrl = payload?.message?.file_url;
		if (!response.ok || !fileUrl) {
			throw new Error(payload?._server_messages || payload?.exc || "No se pudo subir el archivo.");
		}
		return fileUrl;
	}

	async createRun(fileUrls) {
		const response = await frappe.call({
			method: "hubgh.hubgh.payroll_import_upload_api.create_import_run",
			args: {
				file_urls_json: JSON.stringify(fileUrls),
				source_type: this.sourceType.value,
				period: this.period.value,
			},
		});
		return response.message;
	}

	async processPreview() {
		const response = await frappe.call({
			method: "hubgh.hubgh.payroll_import_upload_api.get_import_run_preview",
			args: {
				run_id: this.currentRun,
			},
		});
		return response.message;
	}

	showLoading() {
		this.uploadForm.closest(".panel").classList.add("hidden");
		this.previewSection.classList.add("hidden");
		this.successSection.classList.add("hidden");
		this.loadingState.classList.remove("hidden");
	}

	hideLoading() {
		this.loadingState.classList.add("hidden");
		this.uploadForm.closest(".panel").classList.remove("hidden");
	}

	async showPreview(result, run) {
		this.hideLoading();
		this.previewSection.classList.remove("hidden");

		this.totalRows.textContent = result.total_rows || 0;
		this.validRows.textContent = result.valid_rows || 0;
		this.errorRows.textContent = result.error_rows || 0;
		this.duplicateRows.textContent = result.duplicate_rows || 0;
		this.previewMeta.textContent = `Run ${run.run_id} · ${result.source_count || run.source_count || 0} archivo(s) · ${run.run_label || this.period.options[this.period.selectedIndex].textContent}. Revisa la conciliacion antes de confirmar.`;
		this.previewStatusChip.textContent = result.status || "Pendiente";

		const statusConfig = this.resolveStatusConfig(result.status);
		this.commitBtn.disabled = !statusConfig.allowCommit;
		this.previewStatusChip.className = `status-chip ${statusConfig.className}`;
		this.showAlert(statusConfig.message, statusConfig.type, statusConfig.title);

		await this.loadPreviewLines();
	}

	resolveStatusConfig(status) {
		if (status === "Completado") {
			return {
				allowCommit: true,
				className: "status-completado",
				type: "success",
				title: "Vista previa lista",
				message: "Todas las filas del run quedaron listas para confirmar.",
			};
		}
		if (status === "Completado con errores") {
			return {
				allowCommit: true,
				className: "status-completado-con-errores",
				type: "warning",
				title: "Vista previa con observaciones",
				message: "Hay filas con error. Puedes revisar y decidir si confirmas el run para seguimiento posterior.",
			};
		}
		if (status === "Completado con duplicados") {
			return {
				allowCommit: true,
				className: "status-completado-con-duplicados",
				type: "warning",
				title: "Duplicados detectados",
				message: "Se detectaron novedades repetidas. Revisa las observaciones antes de confirmar.",
			};
		}
		return {
			allowCommit: false,
			className: "status-fallido",
			type: "error",
			title: "Procesamiento fallido",
			message: "El run no pudo procesarse correctamente. Corrige los archivos o revisa los catalogos y vuelve a intentar.",
		};
	}

	async loadPreviewLines() {
		try {
			const response = await frappe.call({
				method: "hubgh.hubgh.payroll_import_upload_api.get_import_preview_lines",
				args: {
					run_id: this.currentRun,
					limit_page_length: 200,
				},
			});
			this.renderPreviewTable(response.message || []);
		} catch (error) {
			this.showAlert(this.getErrorMessage(error, "No se pudo cargar la vista previa del run."), "error", "Error cargando vista previa");
		}
	}

	renderPreviewTable(lines) {
		this.previewTableBody.innerHTML = "";
		this.previewEmptyState.classList.toggle("hidden", lines.length > 0);

		lines.forEach((line) => {
			const row = document.createElement("tr");
			const statusSlug = this.toStatusSlug(line.status);
			const employeeDisplay = [line.employee_id || "-", line.employee_name ? `(${line.employee_name})` : ""]
				.filter(Boolean)
				.join(" ");
			const fichaLabel = line.matched_employee
				? `${line.matched_employee_doctype || "Ficha Empleado"}: ${line.matched_employee}`
				: "Sin match en Ficha Empleado";
			const observations = line.validation_errors || fichaLabel;

			row.innerHTML = `
				<td>${this.escapeHtml(line.row_number || "-")}</td>
				<td><span class="status-pill ${statusSlug}">${this.escapeHtml(line.status || "Pendiente")}</span></td>
				<td>
					<div>${this.escapeHtml(employeeDisplay)}</div>
					<div class="muted-note">${this.escapeHtml(fichaLabel)}</div>
				</td>
				<td>${this.escapeHtml(line.novedad_type || "-")}</td>
				<td>${this.escapeHtml(line.quantity || "-")}</td>
				<td>${this.escapeHtml(line.novedad_date || "-")}</td>
				<td>${this.escapeHtml(observations)}</td>
			`;
			this.previewTableBody.appendChild(row);
		});
	}

	async handleCommit() {
		if (!this.currentRun) {
			return;
		}

		try {
			this.commitBtn.disabled = true;
			this.commitBtn.textContent = "Confirmando...";
			await frappe.call({
				method: "hubgh.hubgh.payroll_import_upload_api.confirm_import_run",
				args: { run_id: this.currentRun },
			});
			this.showSuccess();
		} catch (error) {
			this.commitBtn.disabled = false;
			this.commitBtn.textContent = "Confirmar importacion agrupada";
			this.showAlert(this.getErrorMessage(error, "No se pudo confirmar el run."), "error", "Error confirmando run");
		}
	}

	async handleCancel() {
		if (this.currentRun) {
			try {
				await frappe.call({
					method: "hubgh.hubgh.payroll_import_upload_api.delete_import_run",
					args: { run_id: this.currentRun },
				});
			} catch (error) {
				this.showAlert(this.getErrorMessage(error, "No se pudo cancelar el run actual."), "error", "Error cancelando run");
				return;
			}
		}

		this.currentRun = null;
		this.currentRunMeta = null;
		this.uploadForm.reset();
		this.previewSection.classList.add("hidden");
		this.successSection.classList.add("hidden");
		this.alertContainer.innerHTML = "";
		this.commitBtn.disabled = true;
		this.commitBtn.textContent = "Confirmar importacion agrupada";
		this.previewStatusChip.textContent = "Pendiente";
		this.previewStatusChip.className = "status-chip";
		this.previewTableBody.innerHTML = "";
		this.previewEmptyState.classList.add("hidden");
		this.refreshPreviewButtonState();
	}

	showSuccess() {
		this.previewSection.classList.add("hidden");
		this.successSection.classList.remove("hidden");
		this.commitBtn.textContent = "Confirmar importacion agrupada";
	}

	showAlert(message, type = "info", title = "Aviso") {
		this.alertContainer.innerHTML = `
			<div class="alert alert-${type}">
				<strong>${this.escapeHtml(title)}</strong>
				<div>${this.escapeHtml(message)}</div>
			</div>
		`;
	}

	toStatusSlug(status) {
		return `status-${String(status || "pendiente").trim().toLowerCase().replace(/\s+/g, "-")}`;
	}

	escapeHtml(value) {
		return String(value == null ? "" : value)
			.replaceAll("&", "&amp;")
			.replaceAll("<", "&lt;")
			.replaceAll(">", "&gt;")
			.replaceAll('"', "&quot;")
			.replaceAll("'", "&#39;");
	}

	getErrorMessage(error, fallbackMessage) {
		const serverMessages = error?._server_messages;
		if (serverMessages) {
			try {
				const parsed = JSON.parse(serverMessages);
				if (parsed.length) {
					return JSON.parse(parsed[0]).message || fallbackMessage;
				}
			} catch (parseError) {
				return fallbackMessage;
			}
		}
		if (error?.message) {
			return error.message;
		}
		return fallbackMessage;
	}
}

document.addEventListener("DOMContentLoaded", () => {
	new PayrollImportUploader();
});
