# Phase 4: PrepSettings

## Goal

Add tenant-level configuration for institution operations: general settings, branding, app toggles, academic years, grading rules, attendance rules, integration placeholders, and per-app settings. PrepSettings is protected by RBAC and emits audit-friendly events for every write.

## Data Model

PrepSettings reuses Phase 2 tables where they are already authoritative:

| Table | Purpose |
| --- | --- |
| `tenant_settings` | Timezone, locale, general settings, and notification preferences. |
| `tenant_branding` | Logo, color, and branding JSON settings. |
| `tenant_apps` | App subscription and tenant enablement state. |
| `app_catalog` | Global app metadata. |

Phase 4 adds:

| Table | Purpose | Key Relationships |
| --- | --- | --- |
| `tenant_academic_years` | Academic year calendar with exclusive current flag managed in service logic. | `tenant_id -> tenants.id`. |
| `tenant_grading_rules` | Default grading scale, pass percentage, and rounding settings. | `tenant_id -> tenants.id`. |
| `tenant_attendance_rules` | Attendance thresholds and policy JSON. | `tenant_id -> tenants.id`. |
| `tenant_integrations` | Provider/integration placeholders with config and secret reference. | `tenant_id -> tenants.id`. |
| `tenant_app_settings` | Tenant-admin app toggle metadata and app-specific settings. | `tenant_id -> tenants.id`, `app_code -> app_catalog.code`. |

All new tenant-owned tables have `tenant_id`, timestamps, and PostgreSQL RLS.

## Classes and Methods

- `PrepSettingsService.get_general_settings` and `update_general_settings`: read/update tenant settings.
- `PrepSettingsService.get_branding` and `update_branding`: read/update branding.
- `PrepSettingsService.list_app_settings`: combines `app_catalog`, `tenant_apps`, and `tenant_app_settings`.
- `PrepSettingsService.toggle_app`: enforces subscription state, locked app rules, and tenant toggle metadata.
- `PrepSettingsService.create_academic_year` and `update_academic_year`: create/update academic years and keep only one current year.
- `PrepSettingsService.get_grading_rule` and `update_grading_rule`: create-on-read default grading rule and update it.
- `PrepSettingsService.get_attendance_rule` and `update_attendance_rule`: create-on-read default attendance rule and update it.
- `event_dispatcher.publish(DomainEvent(...))`: emits audit-friendly settings events.

Routers remain thin. Repositories keep SQLAlchemy queries only. Service methods own subscription validation, RLS context continuity, transaction boundaries, and audit event payloads.

## API Endpoints

- `GET /api/v1/settings/general`
- `PATCH /api/v1/settings/general`
- `GET /api/v1/settings/branding`
- `PATCH /api/v1/settings/branding`
- `GET /api/v1/settings/apps`
- `PATCH /api/v1/settings/apps/{app_code}/toggle`
- `GET /api/v1/settings/academic-years`
- `POST /api/v1/settings/academic-years`
- `PATCH /api/v1/settings/academic-years/{academic_year_id}`
- `GET /api/v1/settings/grading-rules`
- `PATCH /api/v1/settings/grading-rules`
- `GET /api/v1/settings/attendance-rules`
- `PATCH /api/v1/settings/attendance-rules`

Every endpoint requires `prepsettings.settings.manage`.

## App Toggle Rules

Tenant admins can toggle only apps with an existing `tenant_apps` subscription row. Enabling requires:

- `tenant_apps.status != locked`
- `tenant_apps.subscription_status in {active, trial}`
- `tenant_apps.ends_at` is null or in the future
- `app_catalog.is_active = true`

Enabling an active subscription sets status to `enabled`. Enabling a trial subscription sets status to `trial`. Disabling sets status to `disabled` and preserves subscription metadata for platform billing/admin flows.

Platform subscription-state updates continue through the platform tenant-app endpoint until platform-admin hardening lands.

## Audit Events

PrepSettings emits in-process domain events:

- `prepsettings.general.updated`
- `prepsettings.branding.updated`
- `prepsettings.app_toggled`
- `prepsettings.academic_year.created`
- `prepsettings.academic_year.updated`
- `prepsettings.grading_rules.updated`
- `prepsettings.attendance_rules.updated`

Payloads include actor user ID, entity type, entity ID, old value, and new value. Phase 23 will move this to transactional outbox processing.

## Tests

Phase 4 tests cover:

- Settings, branding, grading, and attendance updates.
- Audit events for settings writes.
- Subscription-aware app toggles.
- Locked app enforcement.
- Academic-year current flag exclusivity.
- Permission denial for users without settings permissions.

Run:

```bash
make check
```

## Local Review

```bash
uv sync --all-groups
uv run alembic upgrade head
make check
docker compose up --build
curl http://localhost:8000/api/v1/health
curl http://localhost:8000/api/v1/ready
curl http://localhost:8000/docs
```
