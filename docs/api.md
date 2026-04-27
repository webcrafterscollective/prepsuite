# API Baseline

All public endpoints are versioned under `/api/v1`.

## System Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/health` | Liveness check for the API process. |
| `GET` | `/api/v1/ready` | Readiness check for PostgreSQL and Redis dependencies. |
| `GET` | `/api/v1/openapi.json` | OpenAPI schema. |

## Tenancy Endpoints

Platform bootstrap endpoints remain available for local bootstrapping until the platform-admin hardening phase wires them to PrepAccess platform permissions.

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/platform/tenants` | Create a tenant institution with default settings and branding. |
| `GET` | `/api/v1/platform/tenants/{tenant_id}` | Fetch a tenant by ID. |
| `POST` | `/api/v1/platform/tenants/{tenant_id}/domains` | Add a tenant domain. |
| `GET` | `/api/v1/platform/app-catalog` | List app catalog entries. |
| `POST` | `/api/v1/platform/app-catalog` | Upsert one app catalog entry. |
| `POST` | `/api/v1/platform/app-catalog/seed` | Seed the default PrepSuite app catalog. |
| `PUT` | `/api/v1/platform/tenants/{tenant_id}/apps/{app_code}` | Update app enablement and subscription state. |
| `POST` | `/api/v1/platform/tenants/{tenant_id}/users` | Link an existing PrepAccess user UUID to a tenant. |
| `GET` | `/api/v1/tenant/current` | Resolve the current tenant context. |
| `GET` | `/api/v1/tenant/apps` | List apps visible to the current tenant. |
| `GET` | `/api/v1/tenant/settings` | Fetch current tenant settings. |
| `PATCH` | `/api/v1/tenant/settings` | Update current tenant settings. |
| `GET` | `/api/v1/tenant/branding` | Fetch current tenant branding. |
| `PATCH` | `/api/v1/tenant/branding` | Update current tenant branding. |

Tenant resolution supports `X-Tenant-ID`, `X-Tenant-Slug`, `X-Tenant-Domain`, host/domain, subdomain, `X-User-ID`, and authenticated JWT claims.

## PrepAccess Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/access/register-institution-admin` | Register the primary institution admin for an existing tenant. |
| `POST` | `/api/v1/access/login` | Authenticate with email/password and issue access/refresh tokens. |
| `POST` | `/api/v1/access/refresh` | Rotate a refresh token and issue a new token pair. |
| `POST` | `/api/v1/access/logout` | Revoke the current refresh token or all sessions. |
| `POST` | `/api/v1/access/password-reset/request` | Create a password reset token. Local/test responses expose the token until notification delivery exists. |
| `POST` | `/api/v1/access/password-reset/confirm` | Reset password and revoke active refresh tokens. |
| `POST` | `/api/v1/access/invitations` | Invite a tenant user. Requires `prepaccess.user.invite`. |
| `POST` | `/api/v1/access/invitations/accept` | Accept an invitation and create the invited user. |
| `POST` | `/api/v1/access/roles` | Create a custom tenant role. Requires `prepaccess.role.manage`. |
| `POST` | `/api/v1/access/users/{user_id}/roles` | Assign a role to a user. Requires `prepaccess.role.manage`. |
| `DELETE` | `/api/v1/access/users/{user_id}/roles/{role_id}` | Remove a user role. Requires `prepaccess.role.manage`. |
| `GET` | `/api/v1/access/permission-matrix` | List permissions and tenant roles. Requires `prepaccess.permission.read`. |
| `GET` | `/api/v1/access/me` | Return the authenticated user. |
| `GET` | `/api/v1/access/me/permissions` | Return the authenticated user's effective permission codes. |

Authenticated endpoints use `Authorization: Bearer <access_token>`. Access tokens are RS256 JWTs with `sub`, optional `tid`, `user_type`, `typ=access`, issuer, audience, expiry, and `jti`.

## PrepSettings Endpoints

All PrepSettings endpoints require `prepsettings.settings.manage`.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/settings/general` | Fetch general tenant settings and notification preferences. |
| `PATCH` | `/api/v1/settings/general` | Update general tenant settings. |
| `GET` | `/api/v1/settings/branding` | Fetch tenant branding settings. |
| `PATCH` | `/api/v1/settings/branding` | Update tenant branding settings. |
| `GET` | `/api/v1/settings/apps` | List app catalog entries with tenant subscription/toggle state. |
| `PATCH` | `/api/v1/settings/apps/{app_code}/toggle` | Enable or disable a subscribed tenant app. |
| `GET` | `/api/v1/settings/academic-years` | List tenant academic years. |
| `POST` | `/api/v1/settings/academic-years` | Create an academic year. |
| `PATCH` | `/api/v1/settings/academic-years/{academic_year_id}` | Update an academic year. |
| `GET` | `/api/v1/settings/grading-rules` | Fetch the default grading rule. |
| `PATCH` | `/api/v1/settings/grading-rules` | Update the default grading rule. |
| `GET` | `/api/v1/settings/attendance-rules` | Fetch the default attendance rule. |
| `PATCH` | `/api/v1/settings/attendance-rules` | Update the default attendance rule. |

Tenant app toggles require an existing `tenant_apps` subscription row. Locked apps cannot be toggled by tenant admins. Enabling is allowed only for active or trial subscriptions that have not expired.

## PrepStudents Endpoints

All PrepStudents endpoints require the `prepstudents` tenant app to be enabled. Student read endpoints require `prepstudents.student.read`, create requires `prepstudents.student.create`, import requires `prepstudents.student.import`, student mutations require `prepstudents.student.update` or `prepstudents.student.delete`, and batch workflows require `prepstudents.batch.manage`.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/students` | Cursor-paginated student list with `status`, `search`, `batch_id`, and `sort` filters. |
| `POST` | `/api/v1/students` | Create a student with tenant-unique `admission_no`. |
| `GET` | `/api/v1/students/{student_id}` | Fetch one active, non-deleted student. |
| `PATCH` | `/api/v1/students/{student_id}` | Update student identity, contact, demographics, or status. |
| `DELETE` | `/api/v1/students/{student_id}` | Soft delete a student. |
| `POST` | `/api/v1/students/bulk-import` | Import up to 500 students and return per-row duplicate errors. |
| `GET` | `/api/v1/students/{student_id}/timeline` | Return a student activity timeline from status, batch, enrollment, and note records. |
| `GET` | `/api/v1/students/{student_id}/profile` | Return the student profile aggregate. |
| `POST` | `/api/v1/students/{student_id}/guardians` | Add a guardian and student-guardian link. |
| `POST` | `/api/v1/students/{student_id}/notes` | Add an internal/teacher/guardian-visible note. |
| `POST` | `/api/v1/students/{student_id}/documents` | Add document metadata for externally stored files. |
| `POST` | `/api/v1/students/{student_id}/enrollments` | Enroll a student into a course UUID, optionally linked to a batch. |
| `GET` | `/api/v1/batches` | List batches with optional `status` and `search`. |
| `POST` | `/api/v1/batches` | Create a batch with optional capacity and course UUID. |
| `GET` | `/api/v1/batches/{batch_id}` | Fetch one batch. |
| `PATCH` | `/api/v1/batches/{batch_id}` | Update a batch while preserving capacity constraints. |
| `POST` | `/api/v1/batches/{batch_id}/students` | Add or reactivate a student membership, enforcing capacity. |
| `DELETE` | `/api/v1/batches/{batch_id}/students/{student_id}` | Mark an active batch membership as removed. |

## Error Shape

```json
{
  "error": {
    "code": "string",
    "message": "string",
    "details": {},
    "request_id": "string"
  }
}
```

Every response includes or propagates the `X-Request-ID` header.
