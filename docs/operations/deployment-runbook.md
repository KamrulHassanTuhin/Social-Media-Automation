# Nova Studio production deployment runbook

## 1. Required infrastructure

- Supabase project with migrations `001` through `006` applied in order.
- Private `axis-media` storage bucket created by migration `003`.
- API service running behind HTTPS with a stable worker process.
- Web app deployed with the API base URL and Supabase browser values.
- Email provider webhook configured to `POST /api/v1/notifications/webhook/email`.
- Generic container templates are available in `apps/api/Dockerfile`, `apps/web/Dockerfile`, and `docker-compose.production.yml`.

## 2. Required secrets and configuration

API secrets must be stored in the platform secret manager, never committed to `.env` files:

- `APP_ENV=production`
- `APP_SECRET`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_JWT_SECRET`
- `ENCRYPTION_KEY`
- `OPENAI_API_KEY`, `NUELINK_API_KEY`, `SLACK_WEBHOOK_URL`
- `EMAIL_API_KEY`, `EMAIL_FROM`, `EMAIL_WEBHOOK_SECRET`
- `ALLOWED_ORIGINS` containing only the deployed web origin

Set `AUDIT_RETENTION_DAYS` to the organization default. Workspace admins can override it from the Team/Projects management screen within the 30–3650 day guardrail.

## 3. Release sequence

1. Apply database migrations in a transaction-aware migration job.
2. Deploy the API and worker from the same commit.
3. Deploy the web app with `NEXT_PUBLIC_USE_API=true` and the production API URL.
4. Run `GET /health`, `GET /health/providers?probe=true`, `GET /health/queue`, and `GET /health/storage`.
5. Open `/operations` and confirm provider probes and response-time history are recorded.
6. Create a test content item, generate copy, approve it, and verify the publishing job log.
7. Send a test invitation and verify the email webhook updates delivery state.

For scheduled audit maintenance, run `python maintenance.py --apply` from `apps/api` using the platform scheduler. Run it first without `--apply` to preview eligible records.

For a container-based release, copy `apps/api/.env.example` to `apps/api/.env`, provide the web `NEXT_PUBLIC_*` build arguments through the compose environment, then run `docker compose -f docker-compose.production.yml up -d --build`.

## 4. Rollback and incident handling

- Roll back the web and API image to the previous known-good commit if health checks or smoke tests fail.
- Do not roll back database migrations that contain data or policy changes; ship a forward-fix migration.
- Pause publishing workers before replaying a suspected duplicate-provider incident.
- Use notification outbox retry only after checking provider status and recipient suppression.
- Export the audit log before any destructive maintenance operation.
- Audit retention purge is admin-only, starts with a dry run, and is irreversible after confirmation.

## 5. Operational checks

- Review `/operations` response-time history daily during rollout.
- Review failed publishing jobs and notification outbox failures.
- Confirm webhook signatures are rejected when `EMAIL_WEBHOOK_SECRET` is missing or incorrect outside local mode.
- Verify Supabase RLS policies after every schema change.
- Keep provider payloads and logs free of API keys, access tokens, and unnecessary personal data.
