# HubGH Phase 7 — LMS Integration Hardening Runbook

## Goal

Harden LMS integration in HubGH for operational resilience and observability, without changing business logic outside LMS integration and without role normalization/migration.

## Scope implemented

- LMS integration hooks:
  - `hubgh.lms.integration_hooks`
- LMS-dependent operations API:
  - `hubgh.api.ops`
- LMS setup helper:
  - `hubgh.setup_lms_config`
- New hardening/observability helper:
  - `hubgh.lms.hardening`
- Regression tests:
  - `hubgh.tests.test_lms_phase7_hardening`

## Configuration

Phase 7 resolves LMS course and retry settings from:

1. Site config (`site_config.json`) — highest precedence
2. `LMS Settings` single doctype fields (when present)
3. Controlled defaults in code

### Supported keys

- `hubgh_lms_course_name`
  - Default: `calidad-e-inocuidad-alimentaria`
- `hubgh_lms_retry_attempts`
  - Default: `2`
- `hubgh_lms_retry_delay_ms`
  - Default: `150`

## Operational behavior

### 1) Configurable LMS course (no strict hardcode)

- Course resolution now uses centralized resolver (`get_lms_course_name`) with deterministic fallback.

### 2) Controlled retries on critical LMS operations

- Retry wrapper applies bounded retries and delay for critical lookup/write operations, with terminal fallback (no crash).
- Operations fail into controlled states when LMS is unavailable or inconsistent.

### 3) Structured logging

- LMS integration now emits structured JSON logs with:
  - `event`
  - `status` (`success`, `error`, `retry`, `skip`, `fallback`)
  - contextual IDs (`user`, `persona/empleado`, `course`, `pdv`, etc.)
  - error type/message on failures

### 4) Operational metrics

- Lightweight counters are stored in cache by `endpoint:status`.
- Metrics are exposed by health API.

### 5) Explicit degraded contracts (no crash)

- LMS outages/inconsistencies return stable, explicit degraded payloads or empty states.
- Report and enrollment flows avoid unhandled crashes and keep response contract stable.

## Health / diagnostics

### Endpoint

- Whitelisted endpoint: `hubgh.api.ops.get_lms_integration_health`

### Response shape (summary)

- `service`: `hubgh_lms_integration`
- `status`: `ok | degraded`
- `available`: boolean
- `required_doctypes`: list
- `course`: resolved LMS course name
- `retry`: `{ attempts, delay_seconds }`
- `metrics`: `{ "endpoint:status": count, ... }`

## Support playbook

1. Check health endpoint for `status`, `available`, and current course.
2. Inspect retry config (`hubgh_lms_retry_attempts`, `hubgh_lms_retry_delay_ms`) and tune only if required.
3. Review LMS structured logs for `retry/error/skip` patterns.
4. Inspect metrics counters for recurring failures by operation.
5. Confirm required LMS doctypes exist and are queryable.
6. Validate course slug exists in LMS and matches resolved config.

## Manual verification checklist

1. Set `hubgh_lms_course_name` in `site_config.json` and verify reports/enrollment use that course.
2. Simulate LMS doctype unavailability and verify:
   - no crash
   - stable degraded payloads
   - `status=degraded` in health
3. Simulate LMS lookup failures and verify retries are bounded and logged.
4. Call health endpoint and validate counters increment after LMS operations.
5. Run Phase 7 regression tests.

## Tests executed

- `bench --site hubgh.test run-tests --app hubgh --module hubgh.tests.test_lms_phase7_hardening`
  - Result: `Ran 7 tests ... OK`

## Notes

- This phase intentionally does not include role normalization/migration work (reserved for Phase 8).
