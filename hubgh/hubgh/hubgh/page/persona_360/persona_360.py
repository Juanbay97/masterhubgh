
import frappe
from frappe import _
from frappe.utils import add_days, getdate, nowdate

from hubgh.hubgh.permissions import evaluate_dimension_permission
from hubgh.hubgh.role_matrix import user_has_any_role
from hubgh.hubgh.payroll_persona360 import get_payroll_block


INCAPACIDAD_TIPOS = {"Incapacidad", "Incapacidad por enfermedad general"}
SENSITIVE_REDACTION = "Contenido restringido por política de sensibilidad."


def _event_entry(date_value, event_type, title, desc, ref, color, module, state=None, severity=None):
    """Normalized timeline envelope (S3.1) with backward-compatible keys."""
    return {
        "date": date_value,
        "type": event_type,
        "title": title,
        "desc": desc,
        "ref": ref,
        "color": color,
        "event_type": event_type,
        "module": module,
        "state": state,
        "severity": severity,
    }


def _coerce_filter_values(value):
    if value in (None, "", []):
        return set()
    if isinstance(value, (list, tuple, set)):
        return {str(v).strip().lower() for v in value if str(v).strip()}
    raw = str(value).strip()
    if not raw:
        return set()
    return {part.strip().lower() for part in raw.split(",") if part.strip()}


def _event_matches_filters(event, module_filter, state_filter, severity_filter, date_from=None, date_to=None):
    if module_filter and str(event.get("module") or "").strip().lower() not in module_filter:
        return False
    if state_filter and str(event.get("state") or "").strip().lower() not in state_filter:
        return False
    if severity_filter and str(event.get("severity") or "").strip().lower() not in severity_filter:
        return False

    event_date = event.get("date")
    if date_from and event_date and getdate(event_date) < getdate(date_from):
        return False
    if date_to and event_date and getdate(event_date) > getdate(date_to):
        return False
    return True


def _group_timeline_by_module(timeline):
    sections = []
    by_module = {}
    for event in timeline:
        module_name = event.get("module") or "Otros"
        by_module.setdefault(module_name, []).append(event)

    for module_name in sorted(by_module.keys()):
        rows = by_module[module_name]
        sections.append(
            {
                "section": module_name,
                "count": len(rows),
                "events": rows,
            }
        )
    return sections


def _row_value(row, key, default=None):
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


def _is_sst_incapacidad(row):
    return bool(_row_value(row, "es_incapacidad", 0)) or str(_row_value(row, "tipo_novedad", "") or "") in INCAPACIDAD_TIPOS


def _has_rrll_handoff(row):
    return _row_value(row, "ref_doctype") == "GH Novedad" and bool(_row_value(row, "ref_docname"))


def _resolve_followup_checkpoint_day(row):
    if isinstance(row, dict):
        tipo = str(row.get("tipo_seguimiento") or "").strip()
        momento = str(row.get("momento_consolidacion") or "").strip()
    else:
        tipo = str(getattr(row, "tipo_seguimiento", "") or "").strip()
        momento = str(getattr(row, "momento_consolidacion", "") or "").strip()

    if tipo in {"5", "10"}:
        return int(tipo)
    if tipo == "30/45":
        if momento in {"30", "45"}:
            return int(momento)
        return 30
    return None


def _build_bienestar_followups(seguimientos):
    """Build deterministic follow-up projection from Bienestar Seguimiento Ingreso."""
    history = []
    for row in seguimientos or []:
        checkpoint_day = _resolve_followup_checkpoint_day(row)
        due_date = row.get("fecha_programada")
        source_date = row.get("fecha_realizacion") or due_date
        raw_status = str(row.get("estado") or "").strip()
        mapped_status = "Completado" if raw_status == "Realizado" else (raw_status or "Pendiente")

        history.append(
            {
                # backward-compatible keys
                "source_comment": row.get("name"),
                "source_date": source_date,
                "checkpoint_day": checkpoint_day,
                "due_date": due_date,
                "status": mapped_status,
                # explicit v2 keys
                "source_followup": row.get("name"),
                "tipo_seguimiento": row.get("tipo_seguimiento"),
                "momento_consolidacion": row.get("momento_consolidacion"),
                "fecha_programada": due_date,
                "fecha_realizacion": row.get("fecha_realizacion"),
                "estado": raw_status or "Pendiente",
                "compromiso_generado": row.get("compromiso_generado"),
                "alerta_generada": row.get("alerta_generada"),
            }
        )

    history.sort(
        key=lambda r: (
            str(r.get("due_date") or ""),
            int(r.get("checkpoint_day") or 0),
        )
    )
    return history


def _build_contextual_actions(user, employee_id, is_gh, is_jefe, is_emp, can_view_sensitive):
    can_manage_disciplinary = _can_manage_disciplinary(user)
    can_create_novedad = bool(is_gh or is_jefe)
    can_create_disciplinary = bool(can_manage_disciplinary and can_view_sensitive)
    can_create_wellbeing = bool(is_gh or is_jefe)
    can_view_documents = bool(is_gh or is_jefe or is_emp)

    return {
        "can_create_novedad": can_create_novedad,
        "can_create_disciplinary": can_create_disciplinary,
        "can_create_wellbeing": can_create_wellbeing,
        "can_view_documents": can_view_documents,
        "quick_actions": [
            {
                "key": "create_novedad",
                "label": "Crear Novedad",
                "visible": can_create_novedad,
                "doctype": "Novedad SST",
                "route": "/app/novedad-sst/new",
                "prefill": {"empleado": employee_id},
            },
            {
                "key": "create_disciplinary",
                "label": "Registrar Caso Disciplinario",
                "visible": can_create_disciplinary,
                "doctype": "Caso Disciplinario",
                "route": "/app/caso-disciplinario/new",
                "prefill": {"empleado": employee_id},
            },
            {
                "key": "create_wellbeing",
                "label": "Registrar Compromiso Bienestar",
                "visible": can_create_wellbeing,
                "doctype": "Bienestar Compromiso",
                "route": "/app/bienestar-compromiso/new",
                "prefill": {"ficha_empleado": employee_id},
            },
            {
                "key": "create_wellbeing_alert",
                "label": "Registrar Alerta Bienestar",
                "visible": can_create_wellbeing,
                "doctype": "Bienestar Alerta",
                "route": "/app/bienestar-alerta/new",
                "prefill": {"ficha_empleado": employee_id},
            },
            {
                "key": "view_documents",
                "label": "Ver Expediente Documental",
                "visible": can_view_documents,
                "route": "/app/query-report/Person%20Documents",
                "prefill": {"persona": employee_id},
            },
        ],
        "visibility_context": {
            "user": user,
            "is_gh": bool(is_gh),
            "is_jefe": bool(is_jefe),
            "is_emp": bool(is_emp),
            "can_view_sensitive": bool(can_view_sensitive),
        },
    }


def _build_documentary_context(employee_id, contextual_actions):
    document_action = next(
        (
            action
            for action in (contextual_actions or {}).get("quick_actions", [])
            if action.get("key") == "view_documents"
        ),
        None,
    )

    return {
        "preferred_action_key": "view_documents",
        "available": bool(document_action and document_action.get("visible")),
        "route": "/app/query-report/Person%20Documents",
        "route_options": {"persona": employee_id},
        "title": "Carpeta documental",
        "description": "Acceso directo a Person Documents para revisar soportes y trazabilidad documental sin salir del contexto de la persona.",
        "action": document_action,
    }


def _can_access_retirado(user):
    return user_has_any_role(user, "System Manager", "HR Labor Relations", "GH - RRLL", "Gerente GH")


def _can_manage_disciplinary(user):
    return user_has_any_role(user, "System Manager", "HR Labor Relations", "GH - RRLL", "Gerente GH")

@frappe.whitelist()
def get_persona_stats(
    employee_id,
    module_filter=None,
    state_filter=None,
    severity_filter=None,
    date_from=None,
    date_to=None,
):
    if not employee_id:
        return {}

    # 1. Información Básica del Empleado
    try:
        emp = frappe.get_doc("Ficha Empleado", employee_id)
    except frappe.DoesNotExistError:
        return {}

    # Permission Checks
    user = frappe.session.user
    is_gh = user_has_any_role(user, "Gestión Humana", "System Manager")
    is_jefe = user_has_any_role(user, "Jefe_PDV")
    is_emp = user_has_any_role(user, "Empleado")
    is_rrll = user_has_any_role(user, "HR Labor Relations", "GH - RRLL")
    is_gerente_gh = user_has_any_role(user, "Gerente GH")

    if (emp.estado or "") == "Retirado" and not _can_access_retirado(user):
        frappe.throw(_("No tienes permiso para ver personal retirado."))

    # 1. Access Check
    has_access = False
    
    if is_gh:
        has_access = True
    elif is_emp and emp.email == user:
        has_access = True
    elif is_jefe:
         # Check if Jefe has access to the PDV of the employee
         if emp.pdv and frappe.has_permission("Punto de Venta", "read", emp.pdv):
             has_access = True
    
    if not has_access:
        frappe.throw(_("No tienes permiso para ver esta ficha"))

    # 2. Visibility Rules
    sensitive_policy = evaluate_dimension_permission(
        "sensitive",
        user=user,
        surface="persona_360",
        context={"employee_id": employee_id},
    )
    show_disciplinarios = bool(sensitive_policy.get("effective_allowed") or is_rrll or is_gerente_gh)
    if is_emp and not (is_gh or is_jefe):
        # Employee cannot see their own disciplinarios (as per requirement)
        show_disciplinarios = False

    info = {
        "nombres": emp.nombres,
        "apellidos": emp.apellidos,
        "cedula": emp.cedula,
        "cargo": emp.cargo,
        "pdv": emp.pdv,
        "estado": emp.estado,
        "fecha_ingreso": emp.fecha_ingreso,
        "email": emp.email,
        "pdv_nombre": frappe.db.get_value("Punto de Venta", emp.pdv, "nombre_pdv") if emp.pdv else ""
    }

    timeline = []

    # 2. Obtener Novedades
    novedades = frappe.get_all("Novedad SST",
        filters={"empleado": employee_id, "categoria_novedad": "SST"},
        fields=[
            "name",
            "tipo_novedad",
            "fecha_inicio",
            "fecha_fin",
            "descripcion",
            "descripcion_resumen",
            "estado",
            "en_radar",
            "es_incapacidad",
            "proxima_alerta_fecha",
            "recomendaciones_detalle",
            "ref_doctype",
            "ref_docname",
        ]
    )

    clinical_policy = evaluate_dimension_permission(
        "clinical",
        user=user,
        surface="persona_360",
        context={"employee_id": employee_id},
    )
    can_view_sensitive = bool(clinical_policy.get("effective_allowed"))
    at_activos = 0
    incapacidades_activas = 0
    incapacidades_rrll_handoff = 0
    radar = 0
    alertas_pendientes = 0

    for n in novedades:
        desc = n.descripcion_resumen or n.descripcion or ""
        if not can_view_sensitive and (_is_sst_incapacidad(n) or n.recomendaciones_detalle):
            desc = SENSITIVE_REDACTION

        if n.tipo_novedad == "Accidente" and n.estado in ["Abierta", "En seguimiento", "Abierto"]:
            at_activos += 1
        if _is_sst_incapacidad(n) and n.estado in ["Abierta", "En seguimiento", "Abierto"]:
            incapacidades_activas += 1
            if _has_rrll_handoff(n):
                incapacidades_rrll_handoff += 1
        if n.en_radar:
            radar += 1
        if n.proxima_alerta_fecha and getdate(n.proxima_alerta_fecha) <= getdate(nowdate()):
            alertas_pendientes += 1

        timeline.append(
            _event_entry(
                date_value=n.fecha_inicio,
                event_type="Novedad",
                title=f"Novedad: {n.tipo_novedad}",
                desc=f"{desc} ({n.estado})",
                ref=n.name,
                color="blue",
                module="Novedad SST",
                state=n.estado,
                severity=n.tipo_novedad,
            )
        )

    # 2.1 Ingreso events from GH Novedad (S2.4 propagation, additive)
    if frappe.db.exists("DocType", "GH Novedad"):
        gh_rows = frappe.get_all(
            "GH Novedad",
            filters={"persona": employee_id},
            fields=["name", "tipo", "fecha_inicio", "descripcion", "estado"],
            order_by="fecha_inicio desc",
        )
        for g in gh_rows:
            raw_desc = g.descripcion or ""
            is_ingreso = "ingreso formalizado" in raw_desc.lower()
            event_type = "Ingreso" if is_ingreso else "GH Novedad"
            timeline.append(
                _event_entry(
                    date_value=g.fecha_inicio,
                    event_type=event_type,
                    title="Ingreso formalizado" if is_ingreso else f"GH Novedad: {g.tipo}",
                    desc=f"{raw_desc} ({g.estado or 'Sin estado'})",
                    ref=g.name,
                    color="teal" if is_ingreso else "blue",
                    module="GH Novedad",
                    state=g.estado or "Sin estado",
                    severity=g.tipo,
                )
            )

    # 3. Obtener Casos Disciplinarios
    disciplinarios = frappe.get_all(
        "Caso Disciplinario",
        filters={"empleado": employee_id},
        fields=["name", "tipo_falta", "fecha_incidente", "descripcion", "estado"],
    )
    for d in disciplinarios:
        title = f"Falta {d.tipo_falta}" if show_disciplinarios else "Evento disciplinario"
        desc = f"{d.descripcion or ''} ({d.estado})" if show_disciplinarios else SENSITIVE_REDACTION
        severity = d.tipo_falta if show_disciplinarios else "Restringido"
        timeline.append(
            _event_entry(
                date_value=d.fecha_incidente,
                event_type="Disciplinario",
                title=title,
                desc=desc,
                ref=d.name,
                color="red" if show_disciplinarios and d.tipo_falta in ["Grave", "Gravísima"] else "orange",
                module="Caso Disciplinario",
                state=d.estado if show_disciplinarios else "Restringido",
                severity=severity,
            )
        )

    # 4. Bienestar (Workstream 3): new operational sources only
    bienestar_ingreso = frappe.get_all(
        "Bienestar Seguimiento Ingreso",
        filters={"ficha_empleado": employee_id},
        fields=[
            "name",
            "tipo_seguimiento",
            "momento_consolidacion",
            "fecha_programada",
            "fecha_realizacion",
            "estado",
            "score_global",
            "compromiso_generado",
            "alerta_generada",
            "observaciones",
        ],
    )
    for row in bienestar_ingreso:
        checkpoint = _resolve_followup_checkpoint_day(row)
        etiqueta_hito = f"{checkpoint}" if checkpoint else (row.tipo_seguimiento or "")
        timeline.append(
            _event_entry(
                date_value=row.fecha_realizacion or row.fecha_programada,
                event_type="Bienestar",
                title=f"Seguimiento ingreso {etiqueta_hito}",
                desc=(row.observaciones or "") or f"Estado: {row.estado or 'Pendiente'}",
                ref=row.name,
                color="green" if (row.estado == "Realizado") else "orange",
                module="Bienestar Seguimiento Ingreso",
                state=row.estado,
                severity=f"Seguimiento {etiqueta_hito}",
            )
        )

    bienestar_probation = frappe.get_all(
        "Bienestar Evaluacion Periodo Prueba",
        filters={"ficha_empleado": employee_id},
        fields=[
            "name",
            "fecha_evaluacion",
            "estado",
            "dictamen",
            "porcentaje_resultado",
            "requiere_escalamiento_rrll",
            "gh_novedad",
            "observaciones",
        ],
    )
    for row in bienestar_probation:
        dictamen_txt = str(row.dictamen or "").strip().upper()
        timeline.append(
            _event_entry(
                date_value=row.fecha_evaluacion,
                event_type="Bienestar",
                title=f"Periodo de prueba: {dictamen_txt or 'PENDIENTE'}",
                desc=(row.observaciones or "")
                or f"Resultado: {row.porcentaje_resultado or 0}% | Estado: {row.estado or 'Pendiente'}",
                ref=row.name,
                color="red" if dictamen_txt == "NO APRUEBA" else "green",
                module="Bienestar Evaluacion Periodo Prueba",
                state=row.estado,
                severity=dictamen_txt or "PENDIENTE",
            )
        )

    bienestar_alertas = frappe.get_all(
        "Bienestar Alerta",
        filters={"ficha_empleado": employee_id},
        fields=[
            "name",
            "fecha_alerta",
            "tipo_alerta",
            "prioridad",
            "estado",
            "descripcion",
            "fecha_cierre",
        ],
    )
    for row in bienestar_alertas:
        timeline.append(
            _event_entry(
                date_value=row.fecha_alerta or row.fecha_cierre,
                event_type="Bienestar",
                title=f"Alerta bienestar: {row.tipo_alerta or 'Otro'}",
                desc=row.descripcion or "",
                ref=row.name,
                color="red" if row.prioridad == "Alta" else "orange",
                module="Bienestar Alerta",
                state=row.estado,
                severity=row.prioridad or row.tipo_alerta,
            )
        )

    bienestar_compromisos = frappe.get_all(
        "Bienestar Compromiso",
        filters={"ficha_empleado": employee_id},
        fields=[
            "name",
            "fecha_compromiso",
            "fecha_limite",
            "fecha_cierre",
            "estado",
            "sin_mejora",
            "resultado",
            "gh_novedad",
        ],
    )
    for row in bienestar_compromisos:
        timeline.append(
            _event_entry(
                date_value=row.fecha_compromiso or row.fecha_cierre,
                event_type="Bienestar",
                title=f"Compromiso bienestar: {row.estado or 'Activo'}",
                desc=row.resultado or "",
                ref=row.name,
                color="red" if row.sin_mejora else "green",
                module="Bienestar Compromiso",
                state=row.estado,
                severity="Sin mejora" if row.sin_mejora else "Con mejora",
            )
        )

    bienestar_followups = _build_bienestar_followups(
        [
            {
                "name": row.name,
                "tipo_seguimiento": row.tipo_seguimiento,
                "momento_consolidacion": row.momento_consolidacion,
                "fecha_programada": row.fecha_programada,
                "fecha_realizacion": row.fecha_realizacion,
                "estado": row.estado,
                "compromiso_generado": row.compromiso_generado,
                "alerta_generada": row.alerta_generada,
            }
            for row in bienestar_ingreso
        ]
    )
    
    # Get payroll block data for Persona 360 (never break page if payroll isn't migrated)
    try:
        payroll_block = get_payroll_block(employee_id)
    except Exception:
        payroll_block = {
            "employee_id": employee_id,
            "novelty_summary": {},
            "vacation_balance": {"days_remaining": 0},
            "active_incapacidades": {"total_estimated": 0},
            "pending_deductions": {"total_amount": 0, "total_items": 0},
            "payroll_ready": False,
            "note": "Módulo de nómina no disponible en este sitio"
        }
        
    # Sort timeline by date descending
    timeline.sort(key=lambda x: str(x["date"]), reverse=True)

    module_values = _coerce_filter_values(module_filter)
    state_values = _coerce_filter_values(state_filter)
    severity_values = _coerce_filter_values(severity_filter)

    filtered_timeline = [
        event
        for event in timeline
        if _event_matches_filters(
            event,
            module_filter=module_values,
            state_filter=state_values,
            severity_filter=severity_values,
            date_from=date_from,
            date_to=date_to,
        )
    ]

    timeline_sections = _group_timeline_by_module(filtered_timeline)

    contextual_actions = _build_contextual_actions(
        user=user,
        employee_id=employee_id,
        is_gh=is_gh,
        is_jefe=is_jefe,
        is_emp=is_emp,
        can_view_sensitive=show_disciplinarios,
    )
    documentary_context = _build_documentary_context(employee_id, contextual_actions)

    return {
        "info": info,
        "timeline": filtered_timeline,
        "timeline_sections": timeline_sections,
        "sst_cards": {
            "at_activos": at_activos,
            "incapacidades_activas": incapacidades_activas,
            "incapacidades_rrll_handoff": incapacidades_rrll_handoff,
            "casos_radar": radar,
            "alertas_pendientes": alertas_pendientes,
            "fuente_canonica_incapacidad": "Novedad SST",
        },
        "filters_applied": {
            "module": sorted(module_values),
            "state": sorted(state_values),
            "severity": sorted(severity_values),
            "date_from": date_from,
            "date_to": date_to,
        },
        "contextual_actions": contextual_actions,
        "documentary_context": documentary_context,
        "bienestar_followups": bienestar_followups,
        "bienestar_ruta_ingreso": bienestar_followups,
        "bienestar_periodo_prueba": [
            {
                "name": row.name,
                "fecha_evaluacion": row.fecha_evaluacion,
                "estado": row.estado,
                "dictamen": row.dictamen,
                "porcentaje_resultado": row.porcentaje_resultado,
                "requiere_escalamiento_rrll": row.requiere_escalamiento_rrll,
                "gh_novedad": row.gh_novedad,
                "observaciones": row.observaciones,
            }
            for row in bienestar_probation
        ],
        "bienestar_alertas": [
            {
                "name": row.name,
                "fecha_alerta": row.fecha_alerta,
                "tipo_alerta": row.tipo_alerta,
                "prioridad": row.prioridad,
                "estado": row.estado,
                "descripcion": row.descripcion,
                "fecha_cierre": row.fecha_cierre,
            }
            for row in bienestar_alertas
        ],
        "bienestar_compromisos": [
            {
                "name": row.name,
                "fecha_compromiso": row.fecha_compromiso,
                "fecha_limite": row.fecha_limite,
                "fecha_cierre": row.fecha_cierre,
                "estado": row.estado,
                "sin_mejora": row.sin_mejora,
                "resultado": row.resultado,
                "gh_novedad": row.gh_novedad,
            }
            for row in bienestar_compromisos
        ],
        "payroll_block": payroll_block,
    }


@frappe.whitelist()
def get_all_personas_overview():
    filters = {}
    if not _can_access_retirado(frappe.session.user):
        filters["estado"] = ["!=", "Retirado"]
    empleados = frappe.get_all(
        "Ficha Empleado",
        filters=filters,
        fields=["name", "nombres", "apellidos", "cedula", "cargo", "pdv", "email", "estado", "fecha_ingreso"],
    )

    summary_list = []
    for e in empleados:
        if not frappe.has_permission("Ficha Empleado", "read", e.name):
            continue

        pdv_nombre = ""
        if e.pdv:
            pdv_nombre = frappe.db.get_value("Punto de Venta", e.pdv, "nombre_pdv") or ""

        # Novedades abiertas
        novedades_count = frappe.db.count("Novedad SST", {
            "empleado": e.name,
            "estado": "Abierto"
        })

        # Resumen bienestar operativo (WS1-WS4): seguimiento ingreso
        feedback_count = frappe.db.count("Bienestar Seguimiento Ingreso", {"ficha_empleado": e.name})
        feedback_last = ""
        feedback_rows = frappe.get_all(
            "Bienestar Seguimiento Ingreso",
            filters={"ficha_empleado": e.name},
            fields=["observaciones"],
            order_by="fecha_programada desc",
            limit=1
        )
        if feedback_rows:
            feedback_last = _row_value(feedback_rows[0], "observaciones", "") or ""

        summary_list.append({
            "name": e.name,
            "full_name": f"{e.nombres} {e.apellidos}",
            "cedula": e.cedula,
            "cargo": e.cargo,
            "pdv": e.pdv,
            "pdv_nombre": pdv_nombre,
            "novedades": novedades_count,
            "feedback_count": feedback_count,
            "feedback_last": feedback_last
        })

    return summary_list
