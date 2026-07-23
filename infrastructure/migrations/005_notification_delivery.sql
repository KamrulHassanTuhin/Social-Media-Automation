-- Notification delivery lifecycle, provider webhooks, and suppression safety.

alter table public.notification_outbox
  add column if not exists provider_message_id text,
  add column if not exists delivered_at timestamptz,
  add column if not exists bounced_at timestamptz,
  add column if not exists unsubscribed_at timestamptz,
  add column if not exists provider_event_type text,
  add column if not exists provider_event_payload jsonb not null default '{}';

alter table public.notification_outbox drop constraint if exists notification_outbox_status_check;
alter table public.notification_outbox add constraint notification_outbox_status_check
  check (status in ('PENDING', 'PROCESSING', 'SENT', 'FAILED', 'CANCELED', 'BOUNCED', 'UNSUBSCRIBED'));

create unique index if not exists idx_notification_provider_message
  on public.notification_outbox(provider_message_id)
  where provider_message_id is not null;

create table if not exists public.notification_suppressions (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  recipient text not null,
  reason text not null check (reason in ('BOUNCE', 'UNSUBSCRIBE', 'COMPLAINT')),
  source_event_id text,
  created_at timestamptz not null default now(),
  unique (workspace_id, recipient)
);

alter table public.notification_suppressions enable row level security;

create policy admins_can_read_notification_suppressions
  on public.notification_suppressions for select
  using (private.has_workspace_role(workspace_id, array['SUPER_ADMIN', 'WORKSPACE_ADMIN', 'MANAGER']));

create table if not exists public.notification_delivery_events (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid references public.workspaces(id) on delete cascade,
  notification_id uuid references public.notification_outbox(id) on delete set null,
  provider text not null,
  event_type text not null,
  provider_message_id text,
  payload jsonb not null default '{}',
  created_at timestamptz not null default now()
);

alter table public.notification_delivery_events enable row level security;

create policy admins_can_read_notification_delivery_events
  on public.notification_delivery_events for select
  using (workspace_id is null or private.has_workspace_role(workspace_id, array['SUPER_ADMIN', 'WORKSPACE_ADMIN', 'MANAGER']));
