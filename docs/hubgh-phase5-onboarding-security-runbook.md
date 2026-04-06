# HubGH Fase 5 — Runbook de Hardening de Seguridad (Onboarding Candidatos)

## Alcance

Este runbook cubre únicamente el onboarding de candidatos y la creación de usuario candidato:

- Endpoint web [`create_candidate()`](frappe-bench/apps/hubgh/hubgh/www/candidato.py:18)
- Creación/enlace de credenciales en [`ensure_user_link()`](frappe-bench/apps/hubgh/hubgh/hubgh/doctype/candidato/candidato.py:65)

## Controles implementados

### 1) Rate limit por IP e identificador

Se aplica antes de insertar candidato, desde [`enforce_onboarding_rate_limit()`](frappe-bench/apps/hubgh/hubgh/hubgh/onboarding_security.py:59), usando:

- IP de request
- identificador de onboarding (`numero_documento` o `email`)

Se rechaza con `429` (`TooManyRequestsError`) cuando excede el umbral.

### 2) CAPTCHA configurable

La validación se ejecuta con [`validate_onboarding_captcha()`](frappe-bench/apps/hubgh/hubgh/hubgh/onboarding_security.py:82).

- Si está deshabilitado por configuración, el flujo continúa sin CAPTCHA.
- Si está habilitado y no hay token/secret o la verificación falla, se rechaza la solicitud.

### 3) Duplicidad robusta previa a inserción

Se valida antes de insertar desde [`validate_candidate_duplicates()`](frappe-bench/apps/hubgh/hubgh/hubgh/onboarding_security.py:117):

- Duplicado por `numero_documento`
- Duplicado por `email` (comparación case-insensitive)

Además, se mantiene validación en modelo para robustez ante condiciones de carrera:

- [`validate_unique_documento()`](frappe-bench/apps/hubgh/hubgh/hubgh/doctype/candidato/candidato.py:31)
- [`validate_unique_email()`](frappe-bench/apps/hubgh/hubgh/hubgh/doctype/candidato/candidato.py:40)

### 4) Password temporal segura + forzado de cambio en primer login

En [`ensure_user_link()`](frappe-bench/apps/hubgh/hubgh/hubgh/doctype/candidato/candidato.py:65):

- Ya no se usa contraseña derivada de documento.
- Se genera password temporal aleatoria segura con [`_generate_secure_temp_password()`](frappe-bench/apps/hubgh/hubgh/hubgh/doctype/candidato/candidato.py:131).
- Se marca el usuario para forzar reset en primer login con [`mark_user_for_first_login_password_reset()`](frappe-bench/apps/hubgh/hubgh/hubgh/onboarding_security.py:142).

El forzado ocurre en login vía hook [`on_login`](frappe-bench/apps/hubgh/hubgh/hooks.py:276), ejecutando [`enforce_password_reset_on_login()`](frappe-bench/apps/hubgh/hubgh/hubgh/onboarding_security.py:159), que redirige al flujo de `update-password`.

## Configuración operativa (site config)

Configurar en `sites/<site>/site_config.json`:

```json
{
  "hubgh_onboarding_rate_limit_enabled": 1,
  "hubgh_onboarding_rate_limit_limit": 10,
  "hubgh_onboarding_rate_limit_window_seconds": 60,
  "hubgh_onboarding_captcha_enabled": 0,
  "hubgh_onboarding_captcha_secret_key": "",
  "hubgh_onboarding_captcha_verify_url": "https://www.google.com/recaptcha/api/siteverify"
}
```

### Recomendación por ambiente

- **Producción**: `captcha_enabled=1`, secret real y límites conservadores.
- **Staging**: puede usarse CAPTCHA deshabilitado para smoke tests, manteniendo rate limit habilitado.
- **Local/dev**: CAPTCHA opcional; si se deshabilita, siguen activos los demás controles.

## Validación manual (checklist)

1. Intentar creación repetida con mismo IP/documento hasta superar límite → debe retornar rate-limit.
2. Habilitar CAPTCHA y enviar token inválido → debe rechazar.
3. Repetir `numero_documento` o `email` ya existente → debe rechazar consistentemente.
4. Crear candidato nuevo → debe crear usuario.
5. Verificar que contraseña `numero_documento` no autentique.
6. Primer login del usuario candidato → debe redirigir a actualización de contraseña.

## Notas de operación

- Si CAPTCHA se deshabilita, no se rompe onboarding: siguen rate-limit y duplicidad.
- El contrato de respuesta de [`create_candidate()`](frappe-bench/apps/hubgh/hubgh/www/candidato.py:18) se mantiene (`{"name", "user"}`).
