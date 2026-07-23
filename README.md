# AXIS Internal Social Content Automation

Internal content operations SaaS for AXIS Consulting. The application is designed around the master specification in `axis_internal_social_content_automation_saas_master_spec.txt`.

## Current slice

The repository currently contains:

- `apps/web`: Next.js dashboard prototype with interactive content workflow screens.
- `apps/api`: FastAPI service skeleton with health endpoints and API conventions.
- `infrastructure/migrations`: Supabase/Postgres schema with workspace isolation, audit-ready records, indexes, and RLS policies.

The web app runs with local demo data until Supabase and provider credentials are configured. Set `NEXT_PUBLIC_USE_API=true` to use the typed list/create/generate/approve/publish/schedule client, workspace project/member context, React Query cache, media upload, and publishing-job retry flows. AI, Nuelink, and Slack calls are intentionally represented as adapter boundaries; no secret is exposed in the browser.

## Run the web app

```powershell
corepack enable
pnpm install --ignore-scripts
pnpm dev
```

Open `http://localhost:3000`.

## Environment

Copy `apps/web/.env.example` to `apps/web/.env.local` and add the Supabase values when the backend is connected. Set `NEXT_PUBLIC_DEFAULT_WORKSPACE_ID` and `NEXT_PUBLIC_DEFAULT_PROJECT_ID` to real IDs for API-mode content creation and media uploads. Never commit real credentials.

For the API, copy `apps/api/.env.example` to `apps/api/.env`. In local mode, requests without a token use the demo identity; use `Authorization: Bearer demo` to exercise the same authentication path. In staging/production, `SUPABASE_JWT_SECRET` is required and the service role key remains backend-only.

## API service

```powershell
cd apps/api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

The API exposes `GET /health`, `GET /health/providers`, `GET /health/history`, and the versioned base at `/api/v1`.

For the current local slice, the API also exposes demo content endpoints under `/api/v1/content`. They use an in-memory repository and a mock provider adapter so the workflow can be exercised without production credentials. Set `NEXT_PUBLIC_USE_API=true` to opt the dashboard into the typed API client. They must be replaced with Supabase-backed repositories before staging.

Media uploads are available at `POST /api/v1/media/upload`. Local mode writes only under `var/media/`; non-local mode uses the private `axis-media` Supabase Storage bucket and signed URLs. Both paths validate type, size, extension-safe names, and file signatures.

The content detail drawer exposes image upload in API mode. It also loads publishing jobs from `/api/v1/publishing-jobs/content/{content_id}`, shows channel-level errors, and retries failed jobs through `/api/v1/publishing-jobs/{job_id}/retry`. Workspace project and member selectors are loaded from `/api/v1/workspace/projects` and `/api/v1/workspace/members`. The workspace context endpoint `/api/v1/workspace/context` returns the effective role and permissions for the current session.

Projects and Team screens are available at `/projects` and `/team`. Admins can create, edit, archive/restore projects, invite members, preview the invitation email, change member roles, and deactivate/reactivate members; each write is recorded in `/api/v1/workspace/audit-log`. Audit records can be filtered and exported through `/api/v1/workspace/audit-log.csv`. Supabase Auth invitation links can finish at `/invite/accept?workspace_id=...`, which activates the pending workspace membership. The Operations screen at `/operations` shows provider probes, response-time metrics, queue/storage mode, and recent health history from `/health/providers` and `/health/history`. Content generation, approval, publishing, scheduling, integration management, and workspace management are protected server-side by role permissions; frontend visibility is not treated as an authorization boundary.

Invitation emails are written to the durable notification outbox and queued as `SEND_NOTIFICATION` jobs. Local mode uses a mock email adapter; production mode uses the configured email HTTP provider (`EMAIL_API_KEY`, `EMAIL_BASE_URL`, and `EMAIL_FROM`). Delivery status, retry controls, provider webhook reconciliation, bounce/unsubscribe suppression, and aggregate delivery analytics are available at `/notifications`, `/api/v1/notifications/outbox`, and `/api/v1/notifications/analytics`. Configure `EMAIL_WEBHOOK_SECRET` and point the provider webhook to `POST /api/v1/notifications/webhook/email`.

Apply `infrastructure/migrations/003_operations_storage.sql` after the previous migrations to enable persistent queue claims, notification claims, and the private `axis-media` bucket. Health endpoints include `/health/providers`, `/health/history`, `/health/queue`, and `/health/storage`.

Apply `infrastructure/migrations/004_integrations_credentials.sql` for encrypted integration credentials. Set a strong `ENCRYPTION_KEY` outside local mode. Integration management is available under `/api/v1/integrations`; secrets are accepted only on connect and are never returned.

Apply `infrastructure/migrations/005_notification_delivery.sql` after migration 004 to persist provider message IDs, delivery events, bounce/unsubscribe suppression, and notification delivery state.

Apply `infrastructure/migrations/006_audit_retention.sql` after migration 005 to configure workspace-scoped audit retention. The Team/Projects management screen provides an admin-only retention policy editor and dry-run-first purge control. See [the production deployment runbook](docs/operations/deployment-runbook.md) before deploying outside local mode.

Use `/health/providers?probe=true` for provider probes. Publishing jobs can be inspected at `/api/v1/publishing-jobs/content/{content_id}` and failed channel jobs can be retried with `/api/v1/publishing-jobs/{job_id}/retry`.

Future-dated publishing uses `POST /api/v1/content/{content_id}/schedule` with a timezone-aware `scheduled_for` value. The worker will not claim the channel job before that timestamp.

When `NEXT_PUBLIC_USE_API=true`, the content detail drawer exposes the same scheduling flow and sends the browser session token plus workspace context to the API.

## Browser smoke tests

Install the Playwright browser once, then run the dashboard smoke suite:

```powershell
pnpm --filter @axis/web exec playwright install chromium
pnpm --filter @axis/web e2e
```

## Database

Apply `infrastructure/migrations/001_initial_schema.sql` to a Supabase project. It creates the core multi-tenant tables and RLS policies. Provider credentials are deliberately not included in the seed data.

## Planned delivery order

1. Foundation and schema
2. Auth, workspaces, roles, and project access
3. Content CRUD and server-side table operations
4. AI generation and copy versioning
5. Review and approval
6. Media and publishing jobs
7. Notifications, logs, integrations, and operations

## Product additions I recommend

- Treat a `workspace_members` record as the canonical user/workspace relationship; do not rely only on a profile role.
- Add an explicit `reviewer_id` and `required_channels` to content items before production rollout.
- Store provider payloads in a redacted form so retry/debugging does not leak credentials or sensitive content.
- Add an outbox/event table before Slack and email notifications are enabled, so notifications are retryable and idempotent.
- Keep manual YouTube/Reddit tasks separate from the content status so one channel cannot hide a partial publish outcome.
- Verify provider webhook signatures in every non-local environment and suppress bounced/unsubscribed recipients before retrying email.
