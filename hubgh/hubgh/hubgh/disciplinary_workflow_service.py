# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt
"""
disciplinary_workflow_service.py — Phase 2 Service Layer

Implements the disciplinary process state machine for Caso Disciplinario
and Afectado Disciplinario. All public functions are transaction-safe:
they modify Frappe Documents directly and call doc.save().

State order (for sync_case_state_from_afectados):
  Pendiente Triage < Citado < En Descargos < En Deliberación < Cerrado

Design reference: obs #863 (engram sdd/disciplinary-flow-refactor/design)
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Optional

import frappe
from frappe import _
from frappe.utils import getdate, nowdate, today as frappe_today, now as frappe_now

try:
    from docxtpl import DocxTemplate
except ImportError:
    DocxTemplate = None  # type: ignore[assignment,misc]

# ---------------------------------------------------------------------------
# Template registry
# ---------------------------------------------------------------------------

TEMPLATE_DIR = Path(frappe.get_app_path("hubgh")) / "public" / "templates" / "disciplinary"

TEMPLATE_MAP: dict[str, str] = {
    "citacion": "citacion.docx",
    "diligencia_descargos": "diligencia_descargos.docx",
    "acta_cierre_sancion": "acta_cierre_sancion.docx",
    "terminacion_justa_causa": "terminacion_justa_causa.docx",
    "acta_cierre_llamado": "acta_cierre_llamado.docx",
    "recordatorio_funciones": "recordatorio_funciones.docx",
}

# ---------------------------------------------------------------------------
# State ordering for sync_case_state_from_afectados
# ---------------------------------------------------------------------------

_AFECTADO_STATE_ORDER: dict[str, int] = {
    "Pendiente Triage": 0,
    "Citado": 1,
    "En Descargos": 2,
    "En Deliberación": 3,
    "Cerrado": 4,
}

_AFECTADO_STATE_TO_CASO_STATE: dict[str, str] = {
    "Pendiente Triage": "En Triage",
    "Citado": "Citado",
    "En Descargos": "En Descargos",
    "En Deliberación": "En Deliberación",
    "Cerrado": "Cerrado",
}


# ===========================================================================
# Feature flag helper — CCR-18/19
# ===========================================================================


def is_v2_enabled() -> bool:
	"""Returns True when disciplinary workflow v2 is active (default=True)."""
	return frappe.conf.get("disciplinary_workflow_v2_enabled", True)


# ===========================================================================
# Audit trail helper — CCR-01/02/03/04
# ===========================================================================


def _append_transition_log(
	doctype: str,
	name: str,
	transition_name: str,
	from_state: str,
	to_state: str,
	actor: str = None,
	comment: str = "",
) -> None:
	"""
	Appends one entry to the transition_log child table of the target doc.

	Args:
	    doctype: "Caso Disciplinario" or "Afectado Disciplinario".
	    name: Document name.
	    transition_name: Machine-readable name of the transition (e.g. "apertura_caso").
	    from_state: Previous state (empty string for new docs).
	    to_state: New state after the transition.
	    actor: User who triggered the transition (defaults to frappe.session.user).
	    comment: Optional human-readable detail.
	"""
	if not name:
		return
	actor = actor or (getattr(frappe.session, "user", None) or "system")
	try:
		timestamp = frappe_now()
	except Exception:
		import datetime
		timestamp = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")
	doc = frappe.get_doc(doctype, name)
	doc.append(
		"transition_log",
		{
			"transition_name": transition_name,
			"from_state": from_state or "",
			"to_state": to_state or "",
			"actor": actor,
			"timestamp": timestamp,
			"comment": comment or "",
		},
	)
	doc.save(ignore_permissions=True)


# ===========================================================================
# render_document — T015
# ===========================================================================


def render_document(tipo: str, context: dict) -> tuple[str, bytes]:
    """
    Renders a DOCX template with the given context.

    Args:
        tipo: One of the keys in TEMPLATE_MAP.
        context: Jinja2 context dict.

    Returns:
        (filename, docx_bytes)

    Raises:
        ValueError: if tipo is not in TEMPLATE_MAP.
        frappe.ValidationError: if template file is missing or render fails.
    """
    if tipo not in TEMPLATE_MAP:
        raise ValueError(
            f"Tipo de documento desconocido: '{tipo}'. "
            f"Valores aceptados: {list(TEMPLATE_MAP.keys())}"
        )

    # GROUP F-10: validate mandatory context keys
    _REQUIRED_CONTEXT_KEYS = {"datos_empleado", "datos_empresa", "firmante"}
    # Use lenient check: only validate if caller passed these explicitly structured keys.
    # Legacy callers use "empleado" key instead of "datos_empleado" — tolerate both.
    has_new_style = any(k in context for k in _REQUIRED_CONTEXT_KEYS)
    has_legacy_style = "empleado" in context
    if has_new_style and not has_legacy_style:
        for req_key in _REQUIRED_CONTEXT_KEYS:
            if req_key not in context:
                frappe.throw(
                    _(
                        "El contexto de render_document debe incluir '{0}'."
                    ).format(req_key),
                    frappe.ValidationError,
                )

    template_path = TEMPLATE_DIR / TEMPLATE_MAP[tipo]

    try:
        tpl = DocxTemplate(str(template_path))
        tpl.render(context)
        buf = BytesIO()
        tpl.save(buf)
        buf.seek(0)
        content = buf.read()
    except FileNotFoundError as exc:
        frappe.throw(
            _(
                "No se pudo generar el documento '{0}'. Plantilla no encontrada. "
                "Contacte al administrador técnico."
            ).format(tipo),
            frappe.ValidationError,
        )
        raise  # unreachable but satisfies type checkers
    except Exception as exc:
        frappe.throw(
            _("Error al renderizar el documento '{0}': {1}").format(tipo, str(exc)),
            frappe.ValidationError,
        )
        raise

    # GROUP F-11: use doc_name when available (spec REQ-14-07)
    doc_name = context.get("doc_name") or ""
    cedula = (context.get("empleado") or {}).get("cedula", "sincedula")
    fecha_iso = context.get("fecha_iso", frappe_today())
    name_part = doc_name if doc_name else cedula
    filename = f"{tipo}_{name_part}_{fecha_iso}.docx"
    return filename, content


def _save_as_private_file(
    filename: str,
    content: bytes,
    attached_to_doctype: str,
    attached_to_name: str,
) -> str:
    """
    Saves bytes as a private File in Frappe.

    Returns:
        file_url (str)
    """
    file_doc = frappe.get_doc(
        {
            "doctype": "File",
            "file_name": filename,
            "attached_to_doctype": attached_to_doctype,
            "attached_to_name": attached_to_name,
            "is_private": 1,
            "content": content,
        }
    )
    file_doc.insert(ignore_permissions=True)
    return file_doc.file_url


# ===========================================================================
# open_case — T017
# ===========================================================================


def open_case(payload: dict) -> str:
    """
    Creates a Caso Disciplinario + 1..N Afectados Disciplinarios.

    payload shape:
        {
            "origen": "Apertura RRLL" | "Solicitud Jefe PDV",
            "solicitante": str | None,
            "fecha_incidente": str,
            "tipo_falta": "Leve" | "Grave" | "Gravísima",
            "descripcion": str,
            "hechos_detallados": str,
            "ciudad_emision": str,
            "empresa": str,
            "afectados": [{"empleado": str}, ...],
            "articulos_rit": [{"articulo": int, "literales_aplicables": str | None}, ...],
        }

    Returns:
        caso_name (e.g. "CD-2026-00001")

    Raises:
        frappe.ValidationError: on invalid payload.
    """
    origen = (payload.get("origen") or "Apertura RRLL").strip()
    solicitante = (payload.get("solicitante") or "").strip() or None
    hechos_detallados = (payload.get("hechos_detallados") or "").strip()
    afectados_payload = payload.get("afectados") or []

    # Validations
    if not hechos_detallados:
        frappe.throw(
            _("El campo 'hechos_detallados' es obligatorio para abrir un caso."),
            frappe.ValidationError,
        )

    # GROUP F-1: minimum 20 characters
    if len(hechos_detallados) < 20:
        frappe.throw(
            _(
                "El campo 'hechos_detallados' debe tener al menos 20 caracteres "
                "({0} ingresados)."
            ).format(len(hechos_detallados)),
            frappe.ValidationError,
        )

    if not afectados_payload:
        frappe.throw(
            _("Se requiere al menos un afectado para abrir un caso disciplinario."),
            frappe.ValidationError,
        )

    if origen == "Solicitud Jefe PDV" and not solicitante:
        frappe.throw(
            _("Cuando el origen es 'Solicitud Jefe PDV', el campo 'solicitante' es obligatorio."),
            frappe.ValidationError,
        )

    # Determine initial estado
    estado_inicial = "En Triage" if origen == "Apertura RRLL" else "Solicitado"

    # Build articulos_rit child rows
    articulos_rit_rows = []
    for art in (payload.get("articulos_rit") or []):
        articulos_rit_rows.append(
            {
                "articulo": art.get("articulo"),
                "literales_aplicables": art.get("literales_aplicables") or "",
            }
        )

    # Create Caso
    caso_doc = frappe.get_doc(
        {
            "doctype": "Caso Disciplinario",
            "origen": origen,
            "solicitante": solicitante,
            "fecha_incidente": payload.get("fecha_incidente"),
            "tipo_falta": payload.get("tipo_falta"),
            "descripcion": payload.get("descripcion") or "",
            "hechos_detallados": hechos_detallados,
            "ciudad_emision": payload.get("ciudad_emision") or "Bogotá D.C.",
            "empresa": payload.get("empresa") or "COMIDAS VARPEL S.A.S.",
            "estado": estado_inicial,
            "fecha_inicio_proceso": frappe_today(),  # GROUP B-1: REQ-01-05
            "articulos_rit": articulos_rit_rows,
        }
    )
    caso_doc.insert(ignore_permissions=True)
    caso_name = caso_doc.name

    # GROUP A: log apertura_caso transition on the caso
    _append_transition_log(
        doctype="Caso Disciplinario",
        name=caso_name,
        transition_name="apertura_caso",
        from_state="",
        to_state=estado_inicial,
        comment="Apertura de caso disciplinario.",
    )

    # Create Afectados
    created_afectado_names = []
    for item in afectados_payload:
        empleado = (item.get("empleado") or "").strip()
        if not empleado:
            continue
        afectado_doc = frappe.get_doc(
            {
                "doctype": "Afectado Disciplinario",
                "caso": caso_name,
                "empleado": empleado,
                "estado": "Pendiente Triage",
            }
        )
        afectado_doc.insert(ignore_permissions=True)
        created_afectado_names.append(afectado_doc.name)

        # GROUP A: log apertura on each afectado
        _append_transition_log(
            doctype="Afectado Disciplinario",
            name=afectado_doc.name,
            transition_name="apertura_caso",
            from_state="",
            to_state="Pendiente Triage",
            comment=f"Afectado creado para caso {caso_name}.",
        )

    return caso_name


# ===========================================================================
# triage_programar_descargos — T021
# ===========================================================================


def triage_programar_descargos(
    caso_name: str,
    afectados: list[str],
    fecha_descargos: str,
    hora: str,
    articulos_rit: list[int],
) -> list[str]:
    """
    Transitions: En Triage → Descargos Programados.

    For each afectado, creates a Citacion Disciplinaria (ronda=1, estado=Borrador),
    calls render_document("citacion", ctx), attaches DOCX, sets estado=Emitida.

    Returns:
        List of citacion names.

    Raises:
        frappe.ValidationError: on precondition violations.
    """
    from hubgh.hubgh.doctype.citacion_disciplinaria.citacion_disciplinaria import (
        _count_business_days,
    )

    # Validations
    if not afectados:
        frappe.throw(
            _("Se requiere al menos un afectado para programar descargos."),
            frappe.ValidationError,
        )

    if not articulos_rit:
        frappe.throw(
            _("Se requiere al menos un artículo RIT para programar descargos."),
            frappe.ValidationError,
        )

    today = frappe_today()
    dias_habiles = _count_business_days(today, fecha_descargos)
    if dias_habiles < 5:
        frappe.throw(
            _(
                "La fecha de descargos debe ser ≥5 días hábiles desde hoy "
                "(Art. 29 CN + RIT). Días hábiles calculados: {0}."
            ).format(dias_habiles),
            frappe.ValidationError,
        )

    caso_doc = frappe.get_doc("Caso Disciplinario", caso_name)

    # GROUP C: pre-transition state check
    if caso_doc.estado != "En Triage":
        frappe.throw(
            _(
                "El caso '{0}' no está en estado 'En Triage' (estado actual: {1}). "
                "No se puede programar descargos."
            ).format(caso_name, caso_doc.estado),
            frappe.ValidationError,
        )

    citacion_names = []

    for afectado_name in afectados:
        afectado_doc = frappe.get_doc("Afectado Disciplinario", afectado_name)

        # Build articulos_rit child rows for the citacion
        articulos_rows = [
            {"articulo": art_num, "literales_aplicables": ""}
            for art_num in articulos_rit
        ]

        # Get hechos from caso
        hechos = getattr(caso_doc, "hechos_detallados", "") or ""

        # Create Citacion (estado=Borrador)
        citacion_doc = frappe.get_doc(
            {
                "doctype": "Citacion Disciplinaria",
                "afectado": afectado_name,
                "numero_ronda": 1,
                "fecha_citacion": today,
                "fecha_programada_descargos": fecha_descargos,
                "hora_descargos": hora,
                "lugar": "Oficina Administrativa — Bogotá D.C.",
                "hechos_narrados": hechos,
                "estado": "Borrador",
                "articulos_rit": articulos_rows,
            }
        )
        citacion_doc.insert(ignore_permissions=True)

        # Render DOCX and attach
        try:
            context = _build_citacion_context(caso_doc, afectado_doc, citacion_doc)
            filename, docx_bytes = render_document("citacion", context)
            file_url = _save_as_private_file(
                filename=filename,
                content=docx_bytes,
                attached_to_doctype="Citacion Disciplinaria",
                attached_to_name=citacion_doc.name,
            )
            citacion_doc.archivo_citacion = file_url
        except frappe.ValidationError:
            # Template not instrumented yet — continue without DOCX (known blocker)
            pass

        citacion_doc.estado = "Emitida"
        citacion_doc.save(ignore_permissions=True)
        citacion_names.append(citacion_doc.name)

        # REQ-03-05: afectado transitions to "Citado" immediately on emission
        # (spec assumes immediate delivery by default; marcar_citacion_entregada
        #  only updates the real delivery date afterwards, no longer changes estado).
        prev_afectado_estado = afectado_doc.estado
        afectado_doc.estado = "Citado"
        afectado_doc.save(ignore_permissions=True)
        _append_transition_log(
            doctype="Afectado Disciplinario",
            name=afectado_name,
            transition_name="citacion_emitida",
            from_state=prev_afectado_estado,
            to_state="Citado",
            comment=f"Citación {citacion_doc.name} emitida — afectado pasa a Citado automáticamente.",
        )

    # Advance caso state
    caso_doc.estado = "Descargos Programados"
    caso_doc.save(ignore_permissions=True)

    # GROUP A: log transition on caso
    _append_transition_log(
        doctype="Caso Disciplinario",
        name=caso_name,
        transition_name="triage_programar_descargos",
        from_state="En Triage",
        to_state="Descargos Programados",
        comment=f"Descargos programados para {fecha_descargos}. Citaciones: {citacion_names}",
    )

    return citacion_names


def _build_citacion_context(caso_doc, afectado_doc, citacion_doc) -> dict:
    """Builds the Jinja2 context dict for a citacion.docx render."""
    empleado_name = getattr(afectado_doc, "empleado", None)
    empleado_data = {}
    if empleado_name:
        emp = frappe.db.get_value(
            "Ficha Empleado",
            empleado_name,
            ["nombres", "apellidos", "cedula", "cargo", "pdv"],
            as_dict=True,
        ) or {}
        nombre_completo = " ".join(
            filter(None, [emp.get("nombres"), emp.get("apellidos")])
        ).upper()
        empleado_data = {
            "nombre": nombre_completo,
            "cedula": emp.get("cedula") or "",
            "cargo": emp.get("cargo") or "",
            "pdv": emp.get("pdv") or "",
            "direccion_residencia": "",
        }

    return {
        "ciudad_emision": getattr(caso_doc, "ciudad_emision", "Bogotá D.C.") or "Bogotá D.C.",
        "fecha_citacion": str(citacion_doc.fecha_citacion or ""),
        "fecha_iso": str(citacion_doc.fecha_citacion or frappe_today()),
        "empleado": empleado_data,
        "empresa": {
            "razon_social": getattr(caso_doc, "empresa", "COMIDAS VARPEL S.A.S.") or "COMIDAS VARPEL S.A.S.",
            "nit": "",
        },
        "fecha_programada_descargos": str(citacion_doc.fecha_programada_descargos or ""),
        "hora_descargos": str(citacion_doc.hora_descargos or ""),
        "lugar": citacion_doc.lugar or "Oficina Administrativa — Bogotá D.C.",
        "articulos": sorted(
            [
                {"numero": row.articulo, "literales": row.literales_aplicables or "", "texto": ""}
                for row in (citacion_doc.articulos_rit or [])
            ],
            key=lambda a: a.get("numero") or 0,
        ),
        "hechos_narrados": citacion_doc.hechos_narrados or "",
        "firmante": {
            "nombre": "MÓNICA ALEJANDRA NUDELMAN ESPINEL",
            "cargo": "COORDINADORA ADMINISTRACIÓN DE PERSONAL",
        },
    }


# ===========================================================================
# triage_cerrar_recordatorio — T023
# ===========================================================================


def triage_cerrar_recordatorio(
    caso_name: str,
    afectado_name: str,
    fundamentos: str,
) -> str:
    """
    Transition: En Triage → Cerrado with outcome Recordatorio de Funciones.

    Creates Comunicado Sancion, renders DOCX, closes afectado.
    If all afectados are now closed, closes the caso.

    Returns:
        comunicado_name
    """
    return _triage_cerrar_directo(
        caso_name=caso_name,
        afectado_name=afectado_name,
        fundamentos=fundamentos,
        tipo_comunicado="Recordatorio de Funciones",
        decision="Recordatorio de Funciones",
        render_tipo="recordatorio_funciones",
    )


def triage_cerrar_llamado_directo(
    caso_name: str,
    afectado_name: str,
    fundamentos: str,
) -> str:
    """
    Transition: En Triage → Cerrado with outcome Llamado de Atención Directo.

    Returns:
        comunicado_name
    """
    return _triage_cerrar_directo(
        caso_name=caso_name,
        afectado_name=afectado_name,
        fundamentos=fundamentos,
        tipo_comunicado="Llamado de Atención Directo",
        decision="Llamado de Atención Directo",
        render_tipo="acta_cierre_llamado",
    )


def _triage_cerrar_directo(
    *,
    caso_name: str,
    afectado_name: str,
    fundamentos: str,
    tipo_comunicado: str,
    decision: str,
    render_tipo: str,
) -> str:
    """Shared implementation for direct triage closures (no descargos)."""
    caso_doc = frappe.get_doc("Caso Disciplinario", caso_name)
    afectado_doc = frappe.get_doc("Afectado Disciplinario", afectado_name)

    # GROUP C: pre-transition state check
    if caso_doc.estado != "En Triage":
        frappe.throw(
            _(
                "El caso '{0}' no está en estado 'En Triage' (estado actual: {1}). "
                "Esta transición solo es válida desde 'En Triage'."
            ).format(caso_name, caso_doc.estado),
            frappe.ValidationError,
        )

    # Create Comunicado Sancion
    comunicado_doc = frappe.get_doc(
        {
            "doctype": "Comunicado Sancion",
            "afectado": afectado_name,
            "tipo_comunicado": tipo_comunicado,
            "fecha_emision": frappe_today(),
            "fundamentos": fundamentos,
        }
    )
    comunicado_doc.insert(ignore_permissions=True)

    # Render DOCX
    try:
        empleado_name = getattr(afectado_doc, "empleado", None)
        context = _build_comunicado_context(
            caso_doc=caso_doc,
            afectado_doc=afectado_doc,
            tipo_comunicado=tipo_comunicado,
            fundamentos=fundamentos,
        )
        filename, docx_bytes = render_document(render_tipo, context)
        file_url = _save_as_private_file(
            filename=filename,
            content=docx_bytes,
            attached_to_doctype="Comunicado Sancion",
            attached_to_name=comunicado_doc.name,
        )
        comunicado_doc.archivo_comunicado = file_url
        comunicado_doc.save(ignore_permissions=True)
    except frappe.ValidationError:
        # Template not instrumented — continue without DOCX
        pass

    # REQ-02-02/03: create Evidencia Disciplinaria record for traceability
    # Map tipo_comunicado to tipo_documento for Evidencia Disciplinaria
    _TIPO_TO_EVIDENCIA = {
        "Recordatorio de Funciones": "Recordatorio Funciones",
        "Llamado de Atención Directo": "Comunicado Sanción",
    }
    _evidencia_tipo = _TIPO_TO_EVIDENCIA.get(tipo_comunicado, "Comunicado Sanción")
    _file_url_for_evidencia = ""
    try:
        _file_url_for_evidencia = getattr(comunicado_doc, "archivo_comunicado", "") or ""
    except Exception:
        _file_url_for_evidencia = ""

    try:
        evidencia_doc = frappe.get_doc(
            {
                "doctype": "Evidencia Disciplinaria",
                "afectado": afectado_name,
                "tipo_documento": _evidencia_tipo,
                "cargado_por": getattr(frappe.session, "user", None) or "system",
                "archivo": _file_url_for_evidencia or None,
            }
        )
        evidencia_doc.insert(ignore_permissions=True)
    except Exception:
        # If Evidencia Disciplinaria insert fails (e.g. schema not migrated),
        # log silently and continue — the Comunicado Sancion is the canonical record.
        frappe.log_error(
            title="_triage_cerrar_directo: Evidencia Disciplinaria insert failed",
            message=frappe.get_traceback(),
        )

    # Close afectado
    afectado_doc.decision_final_afectado = decision
    afectado_doc.estado = "Cerrado"
    afectado_doc.fecha_cierre_afectado = frappe_today()
    afectado_doc.resumen_cierre_afectado = fundamentos
    # GROUP B-2: persist conclusion_publica
    from hubgh.hubgh.page.persona_360.persona_360 import CONCLUSION_PUBLICA_MAP
    afectado_doc.conclusion_publica = CONCLUSION_PUBLICA_MAP.get(decision, "En proceso")
    afectado_doc.save(ignore_permissions=True)

    # GROUP A: log triage transition
    _transition_name = {
        "Recordatorio de Funciones": "triage_recordatorio",
        "Llamado de Atención Directo": "triage_llamado_directo",
    }.get(tipo_comunicado, "triage_cerrar")
    _append_transition_log(
        doctype="Afectado Disciplinario",
        name=afectado_name,
        transition_name=_transition_name,
        from_state="Pendiente Triage",
        to_state="Cerrado",
        comment=f"Cierre de triage: {tipo_comunicado}.",
    )

    # Sync caso state (may close caso if all afectados are closed)
    sync_case_state_from_afectados(caso_name)

    return comunicado_doc.name


def _build_comunicado_context(
    *, caso_doc, afectado_doc, tipo_comunicado: str, fundamentos: str
) -> dict:
    """Builds Jinja2 context for comunicado/recordatorio templates."""
    empleado_name = getattr(afectado_doc, "empleado", None)
    empleado_data: dict = {}
    if empleado_name:
        emp = frappe.db.get_value(
            "Ficha Empleado",
            empleado_name,
            ["nombres", "apellidos", "cedula", "cargo", "pdv"],
            as_dict=True,
        ) or {}
        nombre_completo = " ".join(
            filter(None, [emp.get("nombres"), emp.get("apellidos")])
        ).upper()
        empleado_data = {
            "nombre": nombre_completo,
            "cedula": emp.get("cedula") or "",
            "cargo": emp.get("cargo") or "",
            "pdv": emp.get("pdv") or "",
        }

    return {
        "ciudad_emision": getattr(caso_doc, "ciudad_emision", "Bogotá D.C.") or "Bogotá D.C.",
        "fecha_emision": frappe_today(),
        "fecha_iso": frappe_today(),
        "para": f"{empleado_data.get('nombre', '')} — {empleado_data.get('cargo', '')}",
        "de": "MÓNICA NUDELMAN — Coord. AP",
        "asunto": tipo_comunicado,
        "cuerpo": fundamentos,
        "empleado": empleado_data,
        "empresa": {
            "razon_social": getattr(caso_doc, "empresa", "COMIDAS VARPEL S.A.S.") or "COMIDAS VARPEL S.A.S.",
            "nit": "",
        },
        "tipo_llamado": tipo_comunicado,
        "fundamentos": fundamentos,
        "articulos": [],
        "firmante": {
            "nombre": "MÓNICA ALEJANDRA NUDELMAN ESPINEL",
            "cargo": "COORDINADORA ADMINISTRACIÓN DE PERSONAL",
        },
    }


# ===========================================================================
# sync_case_state_from_afectados — T025
# ===========================================================================


def sync_case_state_from_afectados(caso_name: str) -> None:
    """
    Recalculates the state of the parent Caso from its Afectados.

    Rule: the caso state = minimum state among all afectados, EXCEPT:
      - All Cerrado → caso = Cerrado (requires ALL).

    Also computes decision_final synthesis (GROUP B-4) and logs transition (GROUP A).

    Idempotent. Safe to call multiple times.
    """
    if not caso_name:
        return

    caso_doc = frappe.get_doc("Caso Disciplinario", caso_name)
    prev_estado = caso_doc.estado

    afectados = frappe.get_all(
        "Afectado Disciplinario",
        filters={"caso": caso_name},
        fields=["estado", "decision_final_afectado"],
        limit_page_length=0,
    )

    if not afectados:
        # No afectados — no state change
        return

    states = [
        (row.get("estado") if isinstance(row, dict) else getattr(row, "estado", None)) or "Pendiente Triage"
        for row in afectados
    ]
    state_orders = [_AFECTADO_STATE_ORDER.get(s, 0) for s in states]

    # Special rule: "Cerrado" requires ALL afectados to be Cerrado
    if all(o == _AFECTADO_STATE_ORDER["Cerrado"] for o in state_orders):
        new_caso_state = "Cerrado"

        # GROUP B-4: compute decision_final synthesis
        outcomes = [
            (row.get("decision_final_afectado") if isinstance(row, dict) else getattr(row, "decision_final_afectado", None))
            for row in afectados
        ]
        non_null_outcomes = [o for o in outcomes if o]
        unique_outcomes = set(non_null_outcomes)

        if not non_null_outcomes:
            decision_final = None
        elif len(unique_outcomes) == 1:
            decision_final = unique_outcomes.pop()
        else:
            decision_final = "Mixto"

        # Persist via db.set_value (avoid recursive save loops)
        if decision_final is not None:
            frappe.db.set_value("Caso Disciplinario", caso_name, "decision_final", decision_final)

    else:
        # Case state = MINIMUM state among all afectados (the most behind afectado limits the case).
        # This means the caso can only reach state X if ALL afectados are at X or beyond.
        min_order = min(state_orders)
        min_state = next(s for s in states if _AFECTADO_STATE_ORDER.get(s, 0) == min_order)
        new_caso_state = _AFECTADO_STATE_TO_CASO_STATE.get(min_state, "En Triage")
        decision_final = None

    if caso_doc.estado != new_caso_state:
        caso_doc.estado = new_caso_state
        caso_doc.save(ignore_permissions=True)

        # GROUP A: log state change
        _append_transition_log(
            doctype="Caso Disciplinario",
            name=caso_name,
            transition_name="sync_caso",
            from_state=prev_estado or "",
            to_state=new_caso_state,
            actor="system",
            comment=f"Sincronización automática. decision_final={decision_final}",
        )
    else:
        # Estado unchanged but still call save to keep modified timestamp consistent
        caso_doc.save(ignore_permissions=True)


# ===========================================================================
# marcar_citacion_entregada — T027
# ===========================================================================


def marcar_citacion_entregada(citacion_name: str, fecha_entrega: str) -> None:
    """
    Marks a Citacion as Entregada and records the real delivery date.

    REQ-03-05 update: afectado already transitions to "Citado" at emission time
    (triage_programar_descargos). This function ONLY updates estado_citacion to
    "Entregada" and optionally sets fecha_entrega — it no longer changes afectado.estado.
    """
    citacion_doc = frappe.get_doc("Citacion Disciplinaria", citacion_name)

    # GROUP C: validate citacion is in "Emitida" state
    if citacion_doc.estado != "Emitida":
        frappe.throw(
            _(
                "La citación '{0}' no está en estado 'Emitida' (estado actual: {1}). "
                "Solo citaciones en estado 'Emitida' pueden marcarse como entregadas."
            ).format(citacion_name, citacion_doc.estado),
            frappe.ValidationError,
        )

    citacion_doc.estado = "Entregada"
    if fecha_entrega:
        citacion_doc.fecha_entrega = fecha_entrega
    citacion_doc.save(ignore_permissions=True)

    # Log delivery on afectado for traceability (estado does not change here)
    afectado_name = citacion_doc.afectado
    _append_transition_log(
        doctype="Afectado Disciplinario",
        name=afectado_name,
        transition_name="citacion_entregada",
        from_state="Citado",
        to_state="Citado",
        comment=f"Citación {citacion_name} entregada en fecha {fecha_entrega or '(no registrada)'}.",
    )


def _mark_afectado_citado(afectado_name: str) -> None:
    """Internal helper: transition afectado to Citado and sync caso state."""
    afectado_doc = frappe.get_doc("Afectado Disciplinario", afectado_name)
    if afectado_doc.estado != "Citado":
        afectado_doc.estado = "Citado"
        afectado_doc.save(ignore_permissions=True)

    sync_case_state_from_afectados(afectado_doc.caso)


# ===========================================================================
# iniciar_descargos — T037
# ===========================================================================

_VALID_OUTCOMES = frozenset(
    {"Archivo", "Llamado de Atención", "Suspensión", "Terminación"}
)

_OUTCOME_TO_COMUNICADO_TIPO: dict[str, str] = {
    "Llamado de Atención": "Llamado de Atención",
    "Suspensión": "Suspensión",
    "Terminación": "Terminación",
}

_OUTCOME_TO_RENDER_TIPO: dict[str, str] = {
    "Llamado de Atención": "acta_cierre_llamado",
    "Suspensión": "acta_cierre_sancion",
    "Terminación": "terminacion_justa_causa",
}


def iniciar_descargos(afectado_name: str, citacion_name: str) -> str:
    """
    Transition: Afectado.estado Citado → En Descargos.

    Creates Acta Descargos in Borrador state linked to the given citacion.
    Pre-fills numero_ronda from citacion.

    Returns:
        acta_name (str)

    Raises:
        frappe.ValidationError: if afectado is not in Citado state.
    """
    afectado_doc = frappe.get_doc("Afectado Disciplinario", afectado_name)
    citacion_doc = frappe.get_doc("Citacion Disciplinaria", citacion_name)

    if afectado_doc.estado != "Citado":
        frappe.throw(
            _(
                "El afectado '{0}' debe estar en estado 'Citado' para iniciar descargos "
                "(estado actual: {1})."
            ).format(afectado_name, afectado_doc.estado),
            frappe.ValidationError,
        )

    numero_ronda = getattr(citacion_doc, "numero_ronda", 1) or 1

    acta_doc = frappe.get_doc(
        {
            "doctype": "Acta Descargos",
            "afectado": afectado_name,
            "citacion": citacion_name,
            "numero_ronda": numero_ronda,
            "lugar_sesion": "Oficina Administrativa",
            "derechos_informados": 0,
            "firma_empleado": 0,
            "autorizacion_grabacion": 0,
        }
    )
    acta_doc.insert(ignore_permissions=True)

    # Transition afectado
    afectado_doc.estado = "En Descargos"
    afectado_doc.save(ignore_permissions=True)

    # GROUP A: log iniciar_descargos transition
    _append_transition_log(
        doctype="Afectado Disciplinario",
        name=afectado_name,
        transition_name="iniciar_descargos",
        from_state="Citado",
        to_state="En Descargos",
        comment=f"Sesión de descargos iniciada. Acta: {acta_doc.name}.",
    )

    # Sync caso state
    sync_case_state_from_afectados(afectado_doc.caso)

    return acta_doc.name


# ===========================================================================
# guardar_acta_descargos — T031
# ===========================================================================


def guardar_acta_descargos(acta_name: str, datos: dict) -> None:
    """
    Transition: Acta borrador → finalizada. Afectado.estado En Descargos → En Deliberación.

    Effects:
        1. Validates derechos_informados=1 and (firma OR 2 testigos).
        2. Renders DOCX via render_document("diligencia_descargos", ctx) — fallback on missing template.
        3. Attaches private File → acta.archivo_acta.
        4. afectado.estado = "En Deliberación".
        5. Syncs caso state.

    Raises:
        frappe.ValidationError: on validation failures.
    """
    acta_doc = frappe.get_doc("Acta Descargos", acta_name)

    # Apply datos overrides for validation (from service call, not necessarily saved yet)
    derechos_informados = datos.get("derechos_informados", acta_doc.derechos_informados)
    firma_empleado = datos.get("firma_empleado", acta_doc.firma_empleado)
    testigo_1 = datos.get("testigo_1", acta_doc.testigo_1)
    testigo_2 = datos.get("testigo_2", acta_doc.testigo_2)

    # GROUP C: validate afectado is in "En Descargos" state
    _afectado_for_check = frappe.get_doc("Afectado Disciplinario", acta_doc.afectado)
    if _afectado_for_check.estado != "En Descargos":
        frappe.throw(
            _(
                "El afectado '{0}' debe estar en estado 'En Descargos' para cerrar el acta "
                "(estado actual: {1})."
            ).format(acta_doc.afectado, _afectado_for_check.estado),
            frappe.ValidationError,
        )

    # GROUP F-3: validate preguntas_respuestas has at least 1 row
    preguntas = datos.get("preguntas_respuestas") or []
    if not preguntas:
        frappe.throw(
            _(
                "El acta debe tener al menos una pregunta y respuesta registrada "
                "antes de cerrarse (REQ-05-05)."
            ),
            frappe.ValidationError,
        )

    # Validation: derechos_informados must be true
    if not derechos_informados:
        frappe.throw(
            _(
                "Debe confirmar que se informaron los derechos al trabajador (Art. 29 CN) "
                "antes de guardar el acta."
            ),
            frappe.ValidationError,
        )

    # Validation: firma or 2 testigos required
    if not firma_empleado:
        if not testigo_1 or not testigo_2:
            frappe.throw(
                _(
                    "Si el empleado no firma el acta, se requieren dos testigos "
                    "(testigo_1 y testigo_2) para dar validez al documento."
                ),
                frappe.ValidationError,
            )

    # Apply datos to acta
    acta_doc.derechos_informados = derechos_informados
    acta_doc.firma_empleado = firma_empleado
    if testigo_1 is not None:
        acta_doc.testigo_1 = testigo_1
    if testigo_2 is not None:
        acta_doc.testigo_2 = testigo_2
    if datos.get("hechos_leidos"):
        acta_doc.hechos_leidos = datos["hechos_leidos"]

    # Render DOCX (fallback swallow if template not instrumented)
    try:
        afectado_doc_for_ctx = frappe.get_doc("Afectado Disciplinario", acta_doc.afectado)
        context = _build_acta_context(acta_doc, afectado_doc_for_ctx, datos)
        filename, docx_bytes = render_document("diligencia_descargos", context)
        file_url = _save_as_private_file(
            filename=filename,
            content=docx_bytes,
            attached_to_doctype="Acta Descargos",
            attached_to_name=acta_name,
        )
        acta_doc.archivo_acta = file_url
    except frappe.ValidationError:
        # Template not instrumented yet — continue without DOCX
        pass

    acta_doc.save(ignore_permissions=True)

    # Transition afectado
    afectado_doc = frappe.get_doc("Afectado Disciplinario", acta_doc.afectado)
    afectado_doc.estado = "En Deliberación"
    afectado_doc.save(ignore_permissions=True)

    # GROUP A: log cerrar_acta_descargos
    _append_transition_log(
        doctype="Afectado Disciplinario",
        name=acta_doc.afectado,
        transition_name="cerrar_acta_descargos",
        from_state="En Descargos",
        to_state="En Deliberación",
        comment=f"Acta {acta_name} cerrada.",
    )

    # Sync caso state
    sync_case_state_from_afectados(afectado_doc.caso)


def _build_acta_context(acta_doc, afectado_doc, datos: dict) -> dict:
    """Builds Jinja2 context dict for diligencia_descargos.docx render."""
    empleado_name = getattr(afectado_doc, "empleado", None)
    empleado_data: dict = {}
    if empleado_name:
        emp = frappe.db.get_value(
            "Ficha Empleado",
            empleado_name,
            ["nombres", "apellidos", "cedula", "cargo", "pdv"],
            as_dict=True,
        ) or {}
        nombre_completo = " ".join(
            filter(None, [emp.get("nombres"), emp.get("apellidos")])
        ).upper()
        empleado_data = {
            "nombre": nombre_completo,
            "cedula": emp.get("cedula") or "",
            "cargo": emp.get("cargo") or "",
            "pdv": emp.get("pdv") or "",
        }

    preguntas_respuestas = datos.get("preguntas_respuestas") or []

    return {
        "fecha_sesion": str(getattr(acta_doc, "fecha_sesion", "") or ""),
        "fecha_iso": frappe_today(),
        "lugar_sesion": getattr(acta_doc, "lugar_sesion", "Oficina Administrativa") or "Oficina Administrativa",
        "empleado": empleado_data,
        "empresa": {"razon_social": "COMIDAS VARPEL S.A.S.", "nit": ""},
        "participantes_empresa": [],
        "testigos_trabajador": getattr(acta_doc, "testigos_trabajador", "") or "",
        "autorizacion_grabacion": bool(getattr(acta_doc, "autorizacion_grabacion", 0)),
        "derechos_informados": bool(getattr(acta_doc, "derechos_informados", 0)),
        "fecha_ingreso_empleado": str(getattr(acta_doc, "fecha_ingreso_empleado", "") or ""),
        "cargo_actual": getattr(acta_doc, "cargo_actual", "") or empleado_data.get("cargo", ""),
        "jefe_inmediato": getattr(acta_doc, "jefe_inmediato", "") or "",
        "hechos_leidos": getattr(acta_doc, "hechos_leidos", "") or datos.get("hechos_leidos", ""),
        "preguntas_respuestas": preguntas_respuestas,
        "firma_empleado": bool(getattr(acta_doc, "firma_empleado", 0)),
        "testigo_1": {"nombre": getattr(acta_doc, "testigo_1", None) or ""} if getattr(acta_doc, "testigo_1", None) else None,
        "testigo_2": {"nombre": getattr(acta_doc, "testigo_2", None) or ""} if getattr(acta_doc, "testigo_2", None) else None,
        "firmante": {
            "nombre": "MÓNICA ALEJANDRA NUDELMAN ESPINEL",
            "cargo": "COORDINADORA ADMINISTRACIÓN DE PERSONAL",
        },
    }


# ===========================================================================
# cerrar_afectado_con_sancion — T035
# ===========================================================================


def cerrar_afectado_con_sancion(
    afectado_name: str,
    outcome: str,
    datos: dict,
) -> str:
    """
    Transition: Afectado.estado En Deliberación → Cerrado.

    outcome ∈ {"Archivo", "Llamado de Atención", "Suspensión", "Terminación"}

    Effects:
        1. Validates outcome is valid.
        2. Validates Suspensión has fechas.
        3. Sets decision_final_afectado, resumen_cierre_afectado, fechas.
        4. Creates Comunicado Sancion + renders DOCX (except outcome=Archivo).
        5. afectado.estado = "Cerrado".
        6. Calls disciplinary_case_service.sync_disciplinary_case_effects(afectado).
        7. Syncs caso state.

    Returns:
        comunicado_name (str), or "" for outcome=Archivo.

    Raises:
        frappe.ValidationError: on invalid outcome or missing required data.
    """
    if outcome not in _VALID_OUTCOMES:
        frappe.throw(
            _(
                "Outcome inválido: '{0}'. Valores permitidos: {1}."
            ).format(outcome, ", ".join(sorted(_VALID_OUTCOMES))),
            frappe.ValidationError,
        )

    afectado_doc = frappe.get_doc("Afectado Disciplinario", afectado_name)

    # GROUP C: pre-transition state check
    if afectado_doc.estado != "En Deliberación":
        frappe.throw(
            _(
                "El afectado '{0}' debe estar en estado 'En Deliberación' para cerrar con sanción "
                "(estado actual: {1})."
            ).format(afectado_name, afectado_doc.estado),
            frappe.ValidationError,
        )

    # Validate suspension dates when required
    if outcome == "Suspensión":
        fecha_inicio = datos.get("fecha_inicio_suspension")
        fecha_fin = datos.get("fecha_fin_suspension")
        if not fecha_inicio or not fecha_fin:
            frappe.throw(
                _("El outcome 'Suspensión' requiere fecha_inicio_suspension y fecha_fin_suspension."),
                frappe.ValidationError,
            )
        # GROUP F-4: fecha_inicio_suspension must be >= today
        if getdate(fecha_inicio) < getdate(frappe_today()):
            frappe.throw(
                _(
                    "La fecha de inicio de suspensión ({0}) no puede ser anterior a hoy ({1})."
                ).format(fecha_inicio, frappe_today()),
                frappe.ValidationError,
            )

    # GROUP F-5: support fecha_efectividad_retiro as canonical name (alias for fecha_ultimo_dia)
    if outcome == "Terminación" and "fecha_efectividad_retiro" in datos and "fecha_ultimo_dia" not in datos:
        datos = dict(datos)  # shallow copy to avoid mutating caller dict
        datos["fecha_ultimo_dia"] = datos["fecha_efectividad_retiro"]

    # Apply fields to afectado
    resumen_cierre = (datos.get("resumen_cierre") or "").strip()
    afectado_doc.decision_final_afectado = outcome
    afectado_doc.resumen_cierre_afectado = resumen_cierre
    afectado_doc.fecha_cierre_afectado = frappe_today()

    # GROUP B-2: persist conclusion_publica
    from hubgh.hubgh.page.persona_360.persona_360 import CONCLUSION_PUBLICA_MAP
    afectado_doc.conclusion_publica = CONCLUSION_PUBLICA_MAP.get(outcome, "En proceso")

    if outcome == "Suspensión":
        afectado_doc.fecha_inicio_suspension = datos.get("fecha_inicio_suspension")
        afectado_doc.fecha_fin_suspension = datos.get("fecha_fin_suspension")

    # Create Comunicado Sancion and render DOCX (except Archivo)
    comunicado_name = ""
    if outcome != "Archivo":
        tipo_comunicado = _OUTCOME_TO_COMUNICADO_TIPO.get(outcome, outcome)
        fundamentos = (datos.get("fundamentos") or "").strip()

        comunicado_doc = frappe.get_doc(
            {
                "doctype": "Comunicado Sancion",
                "afectado": afectado_name,
                "tipo_comunicado": tipo_comunicado,
                "fecha_emision": frappe_today(),
                "fundamentos": fundamentos,
            }
        )
        comunicado_doc.insert(ignore_permissions=True)
        comunicado_name = comunicado_doc.name

        # Render DOCX
        render_tipo = _OUTCOME_TO_RENDER_TIPO.get(outcome, "acta_cierre_llamado")
        try:
            context = _build_sancion_context(
                afectado_doc=afectado_doc,
                tipo_comunicado=tipo_comunicado,
                fundamentos=fundamentos,
                datos=datos,
            )
            filename, docx_bytes = render_document(render_tipo, context)
            file_url = _save_as_private_file(
                filename=filename,
                content=docx_bytes,
                attached_to_doctype="Comunicado Sancion",
                attached_to_name=comunicado_name,
            )
            comunicado_doc.archivo_comunicado = file_url
            comunicado_doc.save(ignore_permissions=True)
        except frappe.ValidationError:
            # Template not instrumented — continue without DOCX
            pass

    # Close afectado
    afectado_doc.estado = "Cerrado"
    afectado_doc.save(ignore_permissions=True)

    # GROUP A: log cierre transition
    outcome_slug = outcome.lower().replace(" ", "_").replace("ó", "o").replace("é", "e")
    _append_transition_log(
        doctype="Afectado Disciplinario",
        name=afectado_name,
        transition_name=f"cierre_{outcome_slug}",
        from_state="En Deliberación",
        to_state="Cerrado",
        comment=f"Cierre con outcome: {outcome}. {resumen_cierre}",
    )

    # Dispatch effects (suspension sync / retirement)
    from hubgh.hubgh import disciplinary_case_service
    disciplinary_case_service.sync_disciplinary_case_effects(afectado_doc)

    # Sync caso state
    sync_case_state_from_afectados(afectado_doc.caso)

    return comunicado_name


def _build_sancion_context(
    *,
    afectado_doc,
    tipo_comunicado: str,
    fundamentos: str,
    datos: dict,
) -> dict:
    """Builds Jinja2 context for sancion/terminacion templates."""
    empleado_name = getattr(afectado_doc, "empleado", None)
    empleado_data: dict = {}
    if empleado_name:
        emp = frappe.db.get_value(
            "Ficha Empleado",
            empleado_name,
            ["nombres", "apellidos", "cedula", "cargo", "pdv"],
            as_dict=True,
        ) or {}
        nombre_completo = " ".join(
            filter(None, [emp.get("nombres"), emp.get("apellidos")])
        ).upper()
        empleado_data = {
            "nombre": nombre_completo,
            "cedula": emp.get("cedula") or "",
            "cargo": emp.get("cargo") or "",
            "pdv": emp.get("pdv") or "",
        }

    articulos = [{"numero": a, "literales": "", "texto": ""} for a in (datos.get("articulos") or [])]

    ctx: dict = {
        "fecha_emision": frappe_today(),
        "fecha_iso": frappe_today(),
        "empleado": empleado_data,
        "empresa": {"razon_social": "COMIDAS VARPEL S.A.S.", "nit": ""},
        "fundamentos": fundamentos,
        "articulos": articulos,
        "tipo_llamado": tipo_comunicado,
        "firmante": {
            "nombre": "MÓNICA ALEJANDRA NUDELMAN ESPINEL",
            "cargo": "COORDINADORA ADMINISTRACIÓN DE PERSONAL",
        },
    }

    # Suspensión-specific fields
    if tipo_comunicado == "Suspensión":
        inicio = datos.get("fecha_inicio_suspension") or ""
        fin = datos.get("fecha_fin_suspension") or ""
        dias = 0
        if inicio and fin:
            try:
                from datetime import date
                d1 = getdate(inicio)
                d2 = getdate(fin)
                dias = (d2 - d1).days
            except Exception:
                dias = 0
        ctx["sancion"] = {
            "tipo": "Suspensión",
            "dias": dias,
            "fecha_inicio": str(inicio),
            "fecha_fin": str(fin),
        }

    # Terminación-specific fields (GROUP F-5: accept both field names)
    if tipo_comunicado == "Terminación":
        ctx["fecha_ultimo_dia"] = (
            datos.get("fecha_ultimo_dia")
            or datos.get("fecha_efectividad_retiro")
            or frappe_today()
        )
        ctx["fecha_efectividad_retiro"] = ctx["fecha_ultimo_dia"]  # canonical alias

    return ctx


# ===========================================================================
# Hook handlers — stubs (Phase 4 will populate)
# ===========================================================================


def publish_from_caso(doc, method=None) -> None:
    """Hook on_update for Caso Disciplinario. Phase 4 stub."""
    pass


def publish_from_afectado(doc, method=None) -> None:
    """Hook on_update for Afectado Disciplinario. Phase 4 stub."""
    pass


def publish_from_citacion(doc, method=None) -> None:
    """Hook on_update for Citacion Disciplinaria. Phase 4 stub."""
    pass


def publish_from_acta(doc, method=None) -> None:
    """Hook on_update for Acta Descargos. Phase 4 stub."""
    pass


def publish_from_comunicado(doc, method=None) -> None:
    """Hook on_update for Comunicado Sancion. Phase 4 stub."""
    pass


# ===========================================================================
# Scheduler tasks — stubs (Phase 4 will populate)
# ===========================================================================


def scheduler_alertar_citaciones_vencidas() -> int:
    """Daily: detect citaciones with fecha_programada_descargos < today and
    linked Afectado still in 'Citado'. Sets estado_citacion='Vencida' on the
    citacion (REQ-13-01) and alerta_citacion_vencida=1 on the afectado (REQ-13-02).
    Also appends a transition_log entry (GROUP A).

    Returns:
        Count of alerts raised.
    """
    today = frappe_today()
    citaciones = frappe.get_all(
        "Citacion Disciplinaria",
        filters=[["fecha_programada_descargos", "<", today]],
        fields=["name", "afectado", "fecha_programada_descargos"],
        as_list=False,
    )

    alerts_raised = 0
    for cit in citaciones:
        cit_name = (cit.name if hasattr(cit, "name") else cit.get("name", "")) or ""
        afectado_name = getattr(cit, "afectado", None) or (cit.get("afectado") if hasattr(cit, "get") else None)
        if not afectado_name:
            continue

        try:
            afectado = frappe.get_doc("Afectado Disciplinario", afectado_name)
        except Exception:
            continue

        if afectado.estado != "Citado":
            # Already moved past Citado — no alert needed
            continue

        # GROUP E-2 / REQ-13-01: set citacion.estado_citacion = "Vencida"
        try:
            citacion_doc = frappe.get_doc("Citacion Disciplinaria", cit_name)
            citacion_doc.estado_citacion = "Vencida"
            citacion_doc.save(ignore_permissions=True)
        except Exception:
            pass

        # GROUP B-3 / REQ-13-02: set alerta_citacion_vencida = 1 on afectado
        afectado.alerta_citacion_vencida = 1

        # GROUP A: append transition log
        afectado.append(
            "transition_log",
            {
                "transition_name": "Alerta Citacion Vencida",
                "from_state": "Citado",
                "to_state": "Citado",
                "actor": "scheduler",
                "timestamp": today,
                "comment": f"Citacion {cit_name} vencida sin descargos.",
            },
        )
        afectado.save(ignore_permissions=True)
        alerts_raised += 1

    return alerts_raised


_FALLBACK_RRLL_EMAIL = "bienestar@homeburgers.com"


def scheduler_enviar_resumen_rrll() -> int:
    """Daily: build a summary of pending disciplinary actions and send to RRLL users.

    Summary includes:
      1. Casos en 'En Triage' > 2 days
      2. Citaciones vencidas (fecha_programada_descargos < today)
      3. Afectados en 'En Deliberación' > 7 days

    Falls back to bienestar@homeburgers.com when no RRLL users found.

    Returns:
        Number of recipients the email was sent to.
    """
    today = frappe_today()

    # --- 1. Casos in Triage for >2 days ---
    from frappe.utils import add_days

    triage_cutoff = add_days(today, -2)
    casos_en_triage = frappe.get_all(
        "Caso Disciplinario",
        filters=[["estado", "=", "En Triage"], ["creation", "<", triage_cutoff]],
        fields=["name", "creation"],
    )

    # --- 2. Citaciones vencidas ---
    citaciones_vencidas = frappe.get_all(
        "Citacion Disciplinaria",
        filters=[["fecha_programada_descargos", "<", today]],
        fields=["name", "afectado", "fecha_programada_descargos"],
    )

    # --- 3. Afectados in deliberacion >7 days ---
    deliberacion_cutoff = add_days(today, -7)
    afectados_en_deliberacion = frappe.get_all(
        "Afectado Disciplinario",
        filters=[["estado", "=", "En Deliberación"], ["modified", "<", deliberacion_cutoff]],
        fields=["name", "empleado", "modified"],
    )

    # --- Resolve recipients ---
    rrll_users_rows = frappe.get_all(
        "Has Role",
        filters={"role": "HR Labor Relations", "parenttype": "User"},
        fields=["parent as name"],
        as_list=False,
    )
    recipients = [getattr(r, "name", None) or r.get("name") for r in rrll_users_rows if r]
    recipients = [r for r in recipients if r]

    if not recipients:
        recipients = [_FALLBACK_RRLL_EMAIL]

    # --- GROUP E-1 / REQ-12-03: skip if all sections empty ---
    total_pending = len(casos_en_triage) + len(citaciones_vencidas) + len(afectados_en_deliberacion)
    if total_pending == 0:
        frappe.log_error(
            title="scheduler_enviar_resumen_rrll",
            message=f"Skipped — no pending disciplinary items on {today}.",
        )
        return 0

    # --- Build email content ---
    lines = [
        f"<h3>Resumen Disciplinario RRLL — {today}</h3>",
        f"<p><b>Casos en Triage &gt; 2 días:</b> {len(casos_en_triage)}</p>",
        f"<p><b>Citaciones vencidas:</b> {len(citaciones_vencidas)}</p>",
        f"<p><b>Deliberaciones &gt; 7 días:</b> {len(afectados_en_deliberacion)}</p>",
    ]

    if casos_en_triage:
        lines.append("<ul>")
        for c in casos_en_triage:
            name = getattr(c, "name", None) or (c.get("name") if hasattr(c, "get") else "")
            lines.append(f"<li>Triage: {name}</li>")
        lines.append("</ul>")

    if citaciones_vencidas:
        lines.append("<ul>")
        for c in citaciones_vencidas:
            name = getattr(c, "name", None) or (c.get("name") if hasattr(c, "get") else "")
            lines.append(f"<li>Citación vencida: {name}</li>")
        lines.append("</ul>")

    message = "\n".join(lines)

    # GROUP F-9 / REQ-12-05: spec subject format with [Hubgh] prefix and count
    subject = f"[Hubgh][RRLL] Resumen disciplinario del {today} — {total_pending} acción(es) pendiente(s)"

    frappe.sendmail(
        recipients=recipients,
        subject=subject,
        message=message,
        delayed=False,
    )

    return len(recipients)
