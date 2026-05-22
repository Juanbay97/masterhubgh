# Copyright (c) 2026, Antigravity and contributors
# For license information, please see license.txt

"""
terminacion_service.py — Orquestador principal del proceso de Terminación Contrato.

Arquitectura: Service-oriented (Design §0, §3.1).
- Todas las mutaciones de Terminacion Contrato pasan por este módulo.
- DocType controllers son anémicos (before_insert snapshot, on_update event).
- La bandeja llama vía thin controllers (Batch C).

Flujo iniciar_terminacion:
1. evaluar_checklist_validaciones — si Bloqueante sin Override → throw
2. Crear TC (estado=Iniciado)
3. _inicializar_checklist + _inicializar_subprocesos (7 áreas)
4. block_user_access(empleado)
5. Si causal.requiere_carta_automatica → generar_carta
6. crear_examen_egreso → asignar tc.examen_egreso
7. _dispatch_notifications_iniciar (fan-out R1-R7)
8. Publish rrll.terminacion.iniciada
9. Return TC.name

Import path: hubgh.hubgh.services.terminacion_service
"""

from __future__ import annotations

import frappe
from frappe.utils import today, now_datetime

from hubgh.hubgh.services.user_access_control import block_user_access, restore_user_access
from hubgh.hubgh.services.carta_terminacion_generator import generar_carta
from hubgh.hubgh.services.examen_egreso_service import crear_examen_egreso, cancelar_si_pendiente
from hubgh.hubgh.services.notification_resolver import resolve_area_subscribers, resolve_employee_email
from hubgh.hubgh.services.email_dispatcher import dispatch_email
from hubgh.hubgh.people_ops_event_publishers import publish_people_ops_event


# ---------------------------------------------------------------------------
# Áreas del proceso (7 total, orden fan-out)
# ---------------------------------------------------------------------------

AREAS_SUBPROCESO = [
    "sistemas",
    "rrll_dotacion",
    "operacion",
    "sst",
    "compensacion",
    "jefe_pdv",
    "nomina",
]

# Mapa área → template email (R1-R6; R4 va directo al empleado vía examen_egreso_service)
AREA_TO_TEMPLATE = {
    "sistemas":       "terminacion_iniciada_sistemas",
    "rrll_dotacion":  "terminacion_iniciada_rrll_dotacion",
    "operacion":      "terminacion_iniciada_operacion",
    "compensacion":   "terminacion_iniciada_compensacion",
    "jefe_pdv":       "terminacion_iniciada_jefe_pdv",
    "nomina":         None,  # No hay template específico para nómina en Batch B
}

# Códigos de validación (CAP-03)
VALIDATION_CODES_BLOCKING = [
    "incapacidad_abierta",
    "caso_disciplinario_abierto",
    "traslado_pendiente",
    "contrato_activo_otro",
]

VALIDATION_CODES_INFO = [
    "dotacion_pendiente",
    "prestamos_libranzas",
    "clonk_marcas_recientes",
    "examen_egreso_programado",
    "bloqueo_acceso",
]

ALL_VALIDATION_CODES = VALIDATION_CODES_BLOCKING + VALIDATION_CODES_INFO


# ---------------------------------------------------------------------------
# Públicas — core lifecycle
# ---------------------------------------------------------------------------

def iniciar_terminacion(
    empleado: str,
    causal: str,
    fecha_ultimo_dia: str,
    fecha_terminacion_efectiva: str,
    justificacion: str,
    *,
    contrato_origen: str | None = None,
    caso_disciplinario_origen: str | None = None,
    novedad_sst_origen: str | None = None,
    override_role_block: bool = False,
) -> str:
    """
    Inicia el proceso de Terminación Contrato.

    Flujo completo según design §3.1.

    Returns:
        str: nombre del TC creado (ej. "TC-2026-001").

    Raises:
        frappe.ValidationError: Si hay validaciones bloqueantes sin override.
    """
    # 1. Evaluar checklist — lanza si hay Bloqueante sin override
    checklist = evaluar_checklist_validaciones(empleado)
    _assert_no_blocking_items(checklist)

    # 2. Crear TC
    tc = frappe.get_doc({
        "doctype": "Terminacion Contrato",
        "empleado": empleado,
        "causal": causal,
        "fecha_ultimo_dia": fecha_ultimo_dia,
        "fecha_terminacion_efectiva": fecha_terminacion_efectiva,
        "justificacion": justificacion,
        "estado": "Iniciado",
        "iniciado_por": frappe.session.user or "Administrator",
        "iniciado_en": now_datetime(),
        "contrato_origen": contrato_origen,
        "caso_disciplinario_origen": caso_disciplinario_origen,
        "novedad_sst_origen": novedad_sst_origen,
        "override_role_block": 1 if override_role_block else 0,
    })

    # 3. Snapshot pdv/cargo desde Ficha Empleado (también en before_insert hook)
    emp_data = frappe.db.get_value(
        "Ficha Empleado", empleado, ["pdv", "cargo", "estado"], as_dict=True
    ) or {}
    tc.pdv_al_terminar = emp_data.get("pdv")
    tc.cargo_al_terminar = emp_data.get("cargo")

    tc.insert(ignore_permissions=True)

    # 4. Inicializar checklist y subprocesos
    _inicializar_checklist(tc, checklist)
    _inicializar_subprocesos(tc)
    tc.save(ignore_permissions=True)

    # 5. Bloquear acceso usuario
    block_user_access(
        empleado,
        reason="terminacion_iniciada",
        source_doctype="Terminacion Contrato",
        source_name=tc.name,
        override_role_block=override_role_block,
    )

    # 6. Carta automática si aplica
    try:
        causal_doc = frappe.get_doc("Causal Terminacion", causal)
        if causal_doc.requiere_carta_automatica:
            generar_carta(tc)
    except Exception as exc:
        frappe.log_error(
            message=str(exc),
            title=f"iniciar_terminacion: error en generar_carta para {tc.name}",
        )

    # 7. Crear examen egreso
    try:
        cita_name = crear_examen_egreso(tc)
        tc.db_set("examen_egreso", cita_name, update_modified=False)
    except Exception as exc:
        frappe.log_error(
            message=str(exc),
            title=f"iniciar_terminacion: error en crear_examen_egreso para {tc.name}",
        )

    # 8. Fan-out notificaciones
    try:
        _dispatch_notifications_iniciar(tc)
    except Exception as exc:
        frappe.log_error(
            message=str(exc),
            title=f"iniciar_terminacion: error en _dispatch_notifications_iniciar para {tc.name}",
        )

    # 9. Publicar People Ops Event
    publish_people_ops_event({
        "persona": empleado,
        "area": "rrll",
        "taxonomy": "rrll.terminacion.iniciada",
        "sensitivity": "disciplinary",
        "state": "Iniciado",
        "source_doctype": "Terminacion Contrato",
        "source_name": tc.name,
        "refs": {
            "causal": causal,
            "fecha_terminacion_efectiva": str(fecha_terminacion_efectiva),
        },
        "occurred_on": now_datetime(),
    })

    return tc.name


def aplicar_subproceso(
    terminacion_name: str,
    area: str,
    *,
    evidencia_url: str | None = None,
    notas: str | None = None,
) -> dict:
    """
    Marca el subproceso del área como Completado.

    - Si es el primer subproceso completado, TC pasa de Iniciado a En Curso.
    - Publica People Ops Event rrll.terminacion.subproceso_completado.<area>.

    Returns:
        dict: {area, estado, fecha_completado, total_completados, total_subprocesos}
    """
    tc = frappe.get_doc("Terminacion Contrato", terminacion_name)
    fecha = now_datetime()

    for row in tc.subprocesos:
        if row.area == area:
            row.estado = "Completado"
            row.fecha_completado = fecha
            if evidencia_url:
                row.evidencia = evidencia_url
            if notas:
                row.notas = notas
            break

    # Transición TC: si era Iniciado y al menos uno Completado → En Curso
    completados = [r for r in tc.subprocesos if r.estado in ("Completado", "No Aplica")]
    if tc.estado == "Iniciado" and completados:
        tc.estado = "En Curso"

    tc.save(ignore_permissions=True)

    publish_people_ops_event({
        "persona": tc.empleado,
        "area": "rrll",
        "taxonomy": f"rrll.terminacion.subproceso_completado.{area}",
        "sensitivity": "operational",
        "state": "Completado",
        "source_doctype": "Terminacion Contrato",
        "source_name": tc.name,
        "refs": {"area": area},
        "occurred_on": fecha,
    })

    return {
        "area": area,
        "estado": "Completado",
        "fecha_completado": str(fecha),
        "total_completados": len(completados),
        "total_subprocesos": len(tc.subprocesos),
    }


def cerrar_terminacion(terminacion_name: str, resumen_cierre: str) -> dict:
    """
    Cierra formalmente la terminación.

    Requisitos:
    - Todos los subprocesos Completado/No Aplica.
    - resumen_cierre >= 30 chars.

    Returns:
        dict: {ok, name, estado}

    Raises:
        frappe.ValidationError: Si condiciones no se cumplen.
    """
    tc = frappe.get_doc("Terminacion Contrato", terminacion_name)

    # Validar subprocesos
    if not _resolver_subprocesos_completos(tc):
        areas_pendientes = [
            r.area for r in tc.subprocesos
            if r.estado not in ("Completado", "No Aplica")
        ]
        frappe.throw(
            f"SUBPROCESOS_INCOMPLETOS: Las siguientes áreas aún no han completado su subproceso: "
            f"{', '.join(areas_pendientes)}.",
            frappe.ValidationError,
        )

    # Validar resumen_cierre
    resumen = (resumen_cierre or "").strip()
    if len(resumen) < 30:
        frappe.throw(
            "RESUMEN_CIERRE_REQUERIDO: El resumen de cierre debe tener al menos 30 caracteres.",
            frappe.ValidationError,
        )

    tc.estado = "Cerrado"
    tc.resumen_cierre = resumen
    tc.save(ignore_permissions=True)

    # Actualizar Ficha Empleado.estado = Retirado
    frappe.db.set_value("Ficha Empleado", tc.empleado, "estado", "Retirado")

    # Notificaciones R8
    try:
        _dispatch_notifications_cerrar(tc)
    except Exception as exc:
        frappe.log_error(
            message=str(exc),
            title=f"cerrar_terminacion: error en _dispatch_notifications_cerrar para {tc.name}",
        )

    publish_people_ops_event({
        "persona": tc.empleado,
        "area": "rrll",
        "taxonomy": "rrll.terminacion.cerrada",
        "sensitivity": "disciplinary",
        "state": "Cerrado",
        "source_doctype": "Terminacion Contrato",
        "source_name": tc.name,
        "refs": {"resumen_cierre": resumen[:100]},
        "occurred_on": now_datetime(),
    })

    return {"ok": True, "name": tc.name, "estado": "Cerrado"}


def cancelar_terminacion(terminacion_name: str, motivo: str) -> dict:
    """
    Cancela una Terminación en estado Iniciado o En Curso.

    - Restaura acceso del usuario (restore_user_access).
    - Cancela Cita Examen Egreso pendiente.
    - Resetea subprocesos a Pendiente.

    Returns:
        dict: {ok, name, estado}

    Raises:
        frappe.ValidationError: Si estado=Cerrado o motivo vacío.
    """
    motivo = (motivo or "").strip()
    if not motivo:
        frappe.throw(
            "MOTIVO_CANCELACION_REQUERIDO: Se requiere motivo para cancelar la terminación.",
            frappe.ValidationError,
        )

    tc = frappe.get_doc("Terminacion Contrato", terminacion_name)

    if tc.estado == "Cerrado":
        frappe.throw(
            "CANCELACION_BLOQUEADA_CERRADO: No se puede cancelar una terminación ya cerrada.",
            frappe.ValidationError,
        )

    if tc.estado not in ("Iniciado", "En Curso"):
        frappe.throw(
            f"ESTADO_INVALIDO: Solo se puede cancelar desde Iniciado o En Curso. Estado actual: {tc.estado}.",
            frappe.ValidationError,
        )

    # Restaurar acceso
    restore_user_access(
        tc.empleado,
        reason="terminacion_cancelada",
        source_doctype="Terminacion Contrato",
        source_name=tc.name,
    )

    # Cancelar examen egreso pendiente
    if tc.examen_egreso:
        cancelar_si_pendiente(tc.examen_egreso)

    # Resetear subprocesos
    for row in tc.subprocesos:
        row.estado = "Pendiente"

    tc.estado = "Cancelado"
    tc.cancelado_motivo = motivo
    tc.save(ignore_permissions=True)

    publish_people_ops_event({
        "persona": tc.empleado,
        "area": "rrll",
        "taxonomy": "rrll.terminacion.cancelada",
        "sensitivity": "disciplinary",
        "state": "Cancelado",
        "source_doctype": "Terminacion Contrato",
        "source_name": tc.name,
        "refs": {"motivo": motivo[:100]},
        "occurred_on": now_datetime(),
    })

    return {"ok": True, "name": tc.name, "estado": "Cancelado"}


def cancelar_terminacion_si_activa(empleado: str, *, source_name: str) -> dict | None:
    """
    Helper: cancela la TC activa para un empleado con un source_name dado.

    Busca TCs en estado Iniciado/En Curso para el empleado. Si encuentra una,
    la cancela. Si no hay TC activa, retorna None.

    Args:
        empleado: Nombre de la Ficha Empleado.
        source_name: Identificador de la fuente (usado en motivo).

    Returns:
        dict result de cancelar_terminacion, o None si no hay TC activa.
    """
    activas = frappe.get_all(
        "Terminacion Contrato",
        filters={
            "empleado": empleado,
            "estado": ["in", ["Iniciado", "En Curso"]],
        },
        fields=["name"],
        limit=1,
    )
    if not activas:
        return None

    tc_name = activas[0].name
    motivo = f"Cancelación automática por reversión de {source_name}"
    return cancelar_terminacion(tc_name, motivo)


# ---------------------------------------------------------------------------
# Factories desde integraciones externas
# ---------------------------------------------------------------------------

def crear_terminacion_desde_caso_disciplinario(case_doc) -> str:
    """
    Factory: crea TC desde un Caso Disciplinario cerrado con decisión Terminación.

    CAP-11. Causal = justa_causa.
    """
    fecha = str(getattr(case_doc, "fecha_cierre", None) or today())
    justificacion = (
        getattr(case_doc, "descripcion_final", None)
        or getattr(case_doc, "justificacion", None)
        or f"Terminación derivada de Caso Disciplinario {case_doc.name}"
    )
    return iniciar_terminacion(
        empleado=case_doc.empleado,
        causal="justa_causa",
        fecha_ultimo_dia=fecha,
        fecha_terminacion_efectiva=fecha,
        justificacion=justificacion,
        caso_disciplinario_origen=case_doc.name,
    )


def crear_terminacion_desde_novedad_sst(novedad_doc) -> str:
    """
    Factory: crea TC desde Novedad SST tipo Retiro.

    CAP-12. Causal = otros.
    """
    fecha = str(getattr(novedad_doc, "fecha_inicio", None) or today())
    justificacion = (
        getattr(novedad_doc, "descripcion", None)
        or f"Terminación derivada de Novedad SST {novedad_doc.name}"
    )
    return iniciar_terminacion(
        empleado=novedad_doc.empleado,
        causal="otros",
        fecha_ultimo_dia=fecha,
        fecha_terminacion_efectiva=fecha,
        justificacion=justificacion,
        novedad_sst_origen=novedad_doc.name,
    )


# ---------------------------------------------------------------------------
# Validaciones (pura — sin persistir)
# ---------------------------------------------------------------------------

def evaluar_checklist_validaciones(empleado: str) -> list[dict]:
    """
    Ejecuta los 9 códigos de validación para el empleado.

    Función pura: no persiste, no lanza excepciones en casos informativos.
    Solo los códigos bloqueantes pueden tener resultado='Bloqueante'.

    Returns:
        Lista de 9 dicts con: codigo_validacion, descripcion, resultado, detalle.
    """
    results = []

    # ---- Bloqueantes ----

    # 1. incapacidad_abierta
    results.append(_check_incapacidad_abierta(empleado))

    # 2. caso_disciplinario_abierto
    results.append(_check_caso_disciplinario_abierto(empleado))

    # 3. traslado_pendiente
    results.append(_check_traslado_pendiente(empleado))

    # 4. contrato_activo_otro (D7 verificado: Contrato.empleado Link → Ficha Empleado)
    results.append(_check_contrato_activo_otro(empleado))

    # ---- Informativas ----

    # 5. dotacion_pendiente (campo libre — placeholder)
    results.append({
        "codigo_validacion": "dotacion_pendiente",
        "descripcion": "Devolución de dotación pendiente",
        "resultado": "No Aplica",
        "detalle": "Verificación manual — sin DocType fuente.",
    })

    # 6. prestamos_libranzas (campo libre — placeholder)
    results.append({
        "codigo_validacion": "prestamos_libranzas",
        "descripcion": "Préstamos y libranzas pendientes",
        "resultado": "No Aplica",
        "detalle": "Verificación manual — sin DocType fuente.",
    })

    # 7. clonk_marcas_recientes (informativo — link externo)
    results.append({
        "codigo_validacion": "clonk_marcas_recientes",
        "descripcion": "Marcas recientes en Clonk",
        "resultado": "No Aplica",
        "detalle": "Verificación manual — link a sistema externo.",
    })

    # 8. examen_egreso_programado
    results.append(_check_examen_egreso_programado(empleado))

    # 9. bloqueo_acceso
    results.append(_check_bloqueo_acceso(empleado))

    return results


# ---------------------------------------------------------------------------
# Hooks (registrados en hooks.py — Batch E)
# ---------------------------------------------------------------------------

def before_insert_terminacion(doc, method=None):
    """
    Hook before_insert de Terminacion Contrato.

    Responsabilidades:
    1. Snapshot pdv_al_terminar desde Ficha Empleado.pdv.
    2. Snapshot cargo_al_terminar desde Ficha Empleado.cargo.
    3. Set iniciado_por = frappe.session.user.
    4. Set iniciado_en = now_datetime().
    """
    emp_data = frappe.db.get_value(
        "Ficha Empleado",
        doc.empleado,
        ["pdv", "cargo", "estado"],
    )
    if emp_data:
        pdv, cargo, _estado = emp_data
        doc.pdv_al_terminar = pdv
        doc.cargo_al_terminar = cargo

    doc.iniciado_por = frappe.session.user or "Administrator"
    doc.iniciado_en = now_datetime()


def on_update_terminacion(doc, method=None):
    """
    Hook on_update de Terminacion Contrato.

    Publica People Ops Event solo cuando el estado cambia.
    """
    before = getattr(doc, "_doc_before_save", None)
    estado_antes = getattr(before, "estado", None) if before else None
    estado_actual = doc.estado

    if estado_antes == estado_actual:
        return

    taxonomy = f"rrll.terminacion.{estado_actual.lower().replace(' ', '_')}"
    publish_people_ops_event({
        "persona": doc.empleado,
        "area": "rrll",
        "taxonomy": taxonomy,
        "sensitivity": "disciplinary",
        "state": estado_actual,
        "source_doctype": "Terminacion Contrato",
        "source_name": doc.name,
        "refs": {
            "causal": doc.get("causal"),
            "estado_antes": estado_antes,
        },
        "occurred_on": now_datetime(),
    })


# ---------------------------------------------------------------------------
# Privadas
# ---------------------------------------------------------------------------

def _assert_no_blocking_items(checklist: list[dict]) -> None:
    """Lanza ValidationError si hay items con resultado=Bloqueante."""
    blocking = [
        item for item in checklist
        if item.get("resultado") == "Bloqueante"
    ]
    if blocking:
        codes = ", ".join(item["codigo_validacion"] for item in blocking)
        details = "; ".join(
            f"{item['codigo_validacion']}: {item.get('detalle', '')}"
            for item in blocking
        )
        frappe.throw(
            f"VALIDACION_BLOQUEANTE: No es posible iniciar la terminación. "
            f"Códigos bloqueantes: {codes}. Detalle: {details}",
            frappe.ValidationError,
        )


def _inicializar_subprocesos(tc) -> None:
    """Crea una fila por área en la tabla subprocesos, estado=Pendiente."""
    for area in AREAS_SUBPROCESO:
        tc.append("subprocesos", {
            "area": area,
            "estado": "Pendiente",
        })


def _inicializar_checklist(tc, checklist: list[dict]) -> None:
    """Carga los resultados del checklist en la child table checklist_validaciones."""
    for item in checklist:
        tc.append("checklist_validaciones", {
            "codigo_validacion": item.get("codigo_validacion"),
            "descripcion": item.get("descripcion", ""),
            "resultado": item.get("resultado", "No Aplica"),
            "detalle": item.get("detalle", ""),
        })


def _resolver_subprocesos_completos(tc) -> bool:
    """Retorna True si todos los subprocesos son Completado/No Aplica."""
    return all(
        r.estado in ("Completado", "No Aplica")
        for r in tc.subprocesos
    )


def _resolver_contrato_origen(empleado: str) -> str | None:
    """Busca el contrato activo del empleado."""
    contratos = frappe.get_all(
        "Contrato",
        filters={"empleado": empleado, "estado_contrato": "Activo"},
        fields=["name"],
        limit=1,
    )
    return contratos[0].name if contratos else None


def _dispatch_notifications_iniciar(tc) -> list[dict]:
    """
    Despacha fan-out R1-R6 a las áreas y R7 al empleado.

    R4 (SST/empleado) ya fue enviado por examen_egreso_service al crear la Cita.
    Aquí se envían R1-R3, R5-R6 (áreas) y R7 (empleado con carta si aplica).

    Best-effort: un fallo individual no aborta.
    """
    results = []
    emp_email = resolve_employee_email(tc.empleado)

    context = {
        "empleado": tc.empleado,
        "pdv": tc.pdv_al_terminar,
        "causal": tc.causal,
        "fecha_terminacion_efectiva": str(tc.fecha_terminacion_efectiva or ""),
        "fecha_ultimo_dia": str(tc.fecha_ultimo_dia or ""),
        "link_tc": f"/app/terminacion-contrato/{tc.name}",
        "tc_name": tc.name,
    }

    # R1-R6: fan-out por área (excepto SST que va directo via examen_egreso_service)
    for area, template in AREA_TO_TEMPLATE.items():
        if not template:
            continue
        try:
            recipients = resolve_area_subscribers(area)
            if not recipients:
                frappe.logger("hubgh.terminacion").warning(
                    f"No subscribers for area {area} — skipping {template}",
                    extra={"area": area, "tc": tc.name},
                )
                results.append({"area": area, "status": "skipped", "reason": "no_subscribers"})
                continue
            result = dispatch_email(
                template_name=template,
                recipients=recipients,
                context=context,
            )
            results.append({"area": area, **result})
        except Exception as exc:
            frappe.log_error(
                message=str(exc),
                title=f"_dispatch_notifications_iniciar: fallo R área {area} para {tc.name}",
            )
            results.append({"area": area, "status": "error", "error": str(exc)})

    # R7: empleado con carta adjunta si existe
    try:
        attachments = []
        if tc.carta_terminacion:
            attachments = [{"fid": tc.carta_terminacion}]
        results.append(dispatch_email(
            template_name="terminacion_carta_empleado",
            recipients=[emp_email] if emp_email else [],
            context=context,
            attachments=attachments if attachments else None,
        ))
    except Exception as exc:
        frappe.log_error(
            message=str(exc),
            title=f"_dispatch_notifications_iniciar: fallo R7 para {tc.name}",
        )

    return results


def _dispatch_notifications_cerrar(tc) -> list[dict]:
    """Despacha R8 a RRLL al cerrar la TC."""
    context = {
        "empleado": tc.empleado,
        "causal": tc.causal,
        "resumen_cierre": tc.resumen_cierre or "",
        "tc_name": tc.name,
    }
    rrll_emails = resolve_area_subscribers("rrll_dotacion")
    return [dispatch_email(
        template_name="terminacion_cerrada_rrll",
        recipients=rrll_emails,
        context=context,
    )]


# ---------------------------------------------------------------------------
# Validaciones individuales (pure functions)
# ---------------------------------------------------------------------------

def _check_incapacidad_abierta(empleado: str) -> dict:
    codigo = "incapacidad_abierta"
    descripcion = "Incapacidad médica abierta"
    try:
        if not frappe.db.exists("DocType", "Novedad SST"):
            return _no_aplica(codigo, descripcion)
        count = frappe.db.count(
            "Novedad SST",
            {"empleado": empleado, "tipo_novedad": "Incapacidad", "estado": ["!=", "Cerrada"]},
        )
        if count:
            return {"codigo_validacion": codigo, "descripcion": descripcion,
                    "resultado": "Bloqueante", "detalle": f"{count} incapacidad(es) abierta(s)."}
        return _ok(codigo, descripcion)
    except Exception:
        return _no_aplica(codigo, descripcion)


def _check_caso_disciplinario_abierto(empleado: str) -> dict:
    codigo = "caso_disciplinario_abierto"
    descripcion = "Caso disciplinario abierto"
    try:
        if not frappe.db.exists("DocType", "Caso Disciplinario"):
            return _no_aplica(codigo, descripcion)
        count = frappe.db.count(
            "Caso Disciplinario",
            {"empleado": empleado, "estado": ["!=", "Cerrado"]},
        )
        if count:
            return {"codigo_validacion": codigo, "descripcion": descripcion,
                    "resultado": "Bloqueante", "detalle": f"{count} caso(s) disciplinario(s) abierto(s)."}
        return _ok(codigo, descripcion)
    except Exception:
        return _no_aplica(codigo, descripcion)


def _check_traslado_pendiente(empleado: str) -> dict:
    codigo = "traslado_pendiente"
    descripcion = "Traslado PDV programado"
    try:
        if not frappe.db.exists("DocType", "Traslado PDV"):
            return _no_aplica(codigo, descripcion)
        count = frappe.db.count(
            "Traslado PDV",
            {"empleado": empleado, "estado": "Programado"},
        )
        if count:
            return {"codigo_validacion": codigo, "descripcion": descripcion,
                    "resultado": "Bloqueante", "detalle": f"{count} traslado(s) programado(s) pendiente(s)."}
        return _ok(codigo, descripcion)
    except Exception:
        return _no_aplica(codigo, descripcion)


def _check_contrato_activo_otro(empleado: str) -> dict:
    """D7 VERIFICADO: Contrato.empleado es Link → Ficha Empleado."""
    codigo = "contrato_activo_otro"
    descripcion = "Contrato activo adicional"
    try:
        if not frappe.db.exists("DocType", "Contrato"):
            return _no_aplica(codigo, descripcion)
        contrato_origen = _resolver_contrato_origen(empleado)
        count = frappe.db.count(
            "Contrato",
            {
                "empleado": empleado,
                "estado_contrato": "Activo",
                **({"name": ["!=", contrato_origen]} if contrato_origen else {}),
            },
        )
        if count:
            return {"codigo_validacion": codigo, "descripcion": descripcion,
                    "resultado": "Bloqueante", "detalle": f"{count} contrato(s) adicional(es) activo(s)."}
        return _ok(codigo, descripcion)
    except Exception:
        return _no_aplica(codigo, descripcion)


def _check_examen_egreso_programado(empleado: str) -> dict:
    codigo = "examen_egreso_programado"
    descripcion = "Examen de egreso programado previo"
    try:
        if not frappe.db.exists("DocType", "Cita Examen Egreso"):
            return _no_aplica(codigo, descripcion)
        count = frappe.db.count(
            "Cita Examen Egreso",
            {"empleado": empleado, "estado": "Pendiente Agendamiento"},
        )
        if count:
            return {"codigo_validacion": codigo, "descripcion": descripcion,
                    "resultado": "Alerta", "detalle": f"{count} cita(s) de examen egreso pendiente(s)."}
        return _ok(codigo, descripcion)
    except Exception:
        return _no_aplica(codigo, descripcion)


def _check_bloqueo_acceso(empleado: str) -> dict:
    codigo = "bloqueo_acceso"
    descripcion = "Estado de acceso del usuario"
    try:
        from hubgh.person_identity import resolve_user_for_employee
        identity = resolve_user_for_employee(empleado)
        if not identity or not identity.user:
            return {"codigo_validacion": codigo, "descripcion": descripcion,
                    "resultado": "No Aplica", "detalle": "Sin User vinculado."}
        enabled = frappe.db.get_value("User", identity.user, "enabled")
        if not enabled:
            return {"codigo_validacion": codigo, "descripcion": descripcion,
                    "resultado": "Alerta", "detalle": f"Usuario {identity.user} ya está deshabilitado."}
        return _ok(codigo, descripcion)
    except Exception:
        return _no_aplica(codigo, descripcion)


def _ok(codigo: str, descripcion: str) -> dict:
    return {"codigo_validacion": codigo, "descripcion": descripcion, "resultado": "OK", "detalle": ""}


def _no_aplica(codigo: str, descripcion: str) -> dict:
    return {"codigo_validacion": codigo, "descripcion": descripcion,
            "resultado": "No Aplica", "detalle": "DocType fuente no disponible."}
