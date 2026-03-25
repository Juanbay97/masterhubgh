# HubGH Shell – Fase 1 (App Shell global)

## Resumen

Se implementó una base de App Shell persistente para HubGH con:

- Sidebar fija y dinámica según permisos reales de `Page`/`Workspace`.
- Topbar con buscador placeholder, notificaciones placeholder e identidad de usuario.
- Área principal con módulos navegables y selección de módulo activo.
- Contrato backend (`bootstrap`) listo para integración de feed real en Fase 2.
- Redirección de login para roles HubGH al shell sin romper el flujo de apps no HubGH.

## Archivos principales

- Página shell:
  - `frappe-bench/apps/hubgh/hubgh/hubgh/page/hubgh_shell/hubgh_shell.json`
  - `frappe-bench/apps/hubgh/hubgh/hubgh/page/hubgh_shell/hubgh_shell.js`
  - `frappe-bench/apps/hubgh/hubgh/hubgh/page/hubgh_shell/hubgh_shell.py`
- API del shell:
  - `frappe-bench/apps/hubgh/hubgh/api/shell.py`
- Routing/login y assets globales:
  - `frappe-bench/apps/hubgh/hubgh/utils.py`
  - `frappe-bench/apps/hubgh/hubgh/hooks.py`
  - `frappe-bench/apps/hubgh/hubgh/public/css/hubgh_shell.css`
- Prueba base del contrato:
  - `frappe-bench/apps/hubgh/hubgh/tests/test_shell_api.py`

## Validación manual

1. Iniciar sesión con un usuario HubGH (por ejemplo: Empleado/Jefe_PDV/Gestión Humana).
2. Confirmar redirección inicial a `app/hubgh_shell`.
3. En la sidebar del shell, verificar que solo aparecen módulos permitidos para el rol.
4. Cambiar de rol/usuario y validar que el menú visible cambia de forma consistente.
5. Seleccionar un módulo en el shell y abrirlo con el botón **Abrir módulo**.
6. Confirmar que el topbar renderiza placeholders (buscador/notificaciones) e identidad.
7. Validar que usuarios no HubGH mantienen su fallback normal (`app` o flujo existente).

