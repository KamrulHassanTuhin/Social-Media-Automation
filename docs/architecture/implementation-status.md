# Implementation status

## Completed in the first delivery slice

- Monorepo layout with web and API applications.
- Next.js dashboard with responsive navigation, metrics, content table, filtering, create-content modal, content detail drawer, copy previews, approval action, generation action, retry action, and publish action.
- FastAPI health/readiness endpoints and `/api/v1` response envelope.
- Local content API for list, create, generate, approve, and publish validation.
- Supabase migration with workspace, project, content, copy, media, approval, publishing, notification, activity, audit, error, job, and usage tables.
- Workspace isolation helpers and RLS policies.
- Provider-neutral prompt, output validation, workflow transition, and idempotency services.
- Unit tests for the highest-risk domain rules.
- Bearer-token dependency with a local `demo` identity and Supabase JWT verification boundary.
- Workspace header/context isolation guard returning `403` for unauthorized workspace access.
- Supabase content repository adapter with an environment-controlled local fallback.
- Typed web API client with an opt-in `NEXT_PUBLIC_USE_API` switch.
- Reviewer assignment, required channel constraints, and durable notification outbox migration.
- Supabase browser client boundary, optional session-refresh middleware, and login screen.
- Copy version endpoints and approval history endpoints with request-changes support.
- Supabase-backed workspace membership lookup with fail-fast non-local configuration.
- Session token and default workspace header propagation in the typed API client.
- Authenticated actor IDs used for content mutation audit fields instead of demo identities.
- Retryable idempotent job queue with worker handlers for copy generation and notification delivery.
- Notification outbox with deduplication and local worker delivery.
- Secure local media upload with file-size, MIME, extension, and magic-byte validation.
- Provider-neutral OpenAI, Nuelink, and Slack adapters with local mock implementations.
- Idempotent per-channel publishing jobs and a separate worker entrypoint.
- Supabase RPC claim functions with visibility timeouts for persistent job/outbox workers.
- Private Supabase Storage bucket migration with workspace-scoped RLS and signed URL adapter.
- Queue, storage, and provider health endpoints.
- AES-GCM encrypted credential service and admin-only integration management endpoints.
- Provider probe mode and publishing job listing/retry endpoints.
- Per-channel partial-publish reconciliation that preserves successful channels and retries only failures.
- Future-dated publishing schedules with queue claim-time enforcement.
- Per-workspace provider rate limiter for AI, publishing, and notifications.
- Persisted provider health probe history with `/health/history` (Supabase-backed outside local mode).
- Dashboard scheduling controls wired to the schedule API when API mode is enabled.
- Dashboard API-mode mutations for create, generate, approve, publish, schedule, media upload, and publishing-job retry.
- Content detail publishing-job log with channel-level errors and external post links.
- Workspace project/member context endpoints with Supabase adapters and local demo fixtures.
- React Query provider and cached content/workspace queries for API mode.
- Role-based server-side permission matrix for content actions, integrations, and workspace management.
- Projects and Team management screens with workspace-scoped role/status visibility.
- Admin project creation, member invitation, member role changes, self-role-change protection, and audit-log reads.
- Project edit/archive/restore lifecycle with soft-archive semantics.
- Invitation acceptance endpoint and browser onboarding screen for pending memberships.
- Member soft-deactivation/reactivation, invitation email template preview, and filtered CSV audit export.
- Durable email notification outbox events, provider-neutral email adapter, worker delivery/retry tracking, and Notifications screen.
- Provider message ID persistence, signed email webhooks, delivery/bounce/unsubscribe reconciliation, recipient suppression, and delivery analytics.
- Operations health screen with provider probes, average response-time metrics, and recent health history.
- Workspace-scoped audit retention policy, dry-run-first purge controls, and production deployment runbook.
- Provider health transition alerts through the configured Slack notifier with failure/recovery deduplication.
- One-shot audit retention maintenance command for cron or platform scheduler execution.
- Playwright browser smoke coverage for content creation and approved-content scheduling controls.
- Google Sheets server-side client using runtime-only service-account credentials.
- Scheduled Sheet automation worker with dry-run validation, Nuelink handoff, channel-level duplicate protection, retry limits, and append-only Automation Log writes.
- Sheet automation tests covering missing links, dry-run, duplicate channel success, and partial provider failure.

## Deliberate local-only boundaries

- UI data is demo data unless `NEXT_PUBLIC_USE_API=true`; Supabase Auth is opt-in until project credentials exist.
- API content storage is in-memory for local smoke tests.
- AI, Nuelink, and Slack are mock adapters.
- Production email delivery is available through the configured HTTP adapter; real provider credentials and webhook secrets remain deployment-owned.
- Local mode uses in-memory queue and local files; non-local mode uses `job_queue`, `notification_outbox`, and the private `axis-media` Supabase Storage bucket.
- Provider credential responses are always masked; plaintext is never returned by integration APIs.

## Deployment-owned prerequisites

1. Configure production credentials, migrations, hosting, and scheduler-owned maintenance outside the repository.
2. Share the workbook with the Google service-account email and add `GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON` to the Modal `nova-runtime` secret.
3. Keep `SHEET_AUTOMATION_DRY_RUN=true` until Nuelink credentials and an approved test destination are verified.
