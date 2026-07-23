-- Workflow safety additions identified during the first implementation slice.

alter table public.content_items
  add column if not exists reviewer_id uuid references public.user_profiles(id),
  add column if not exists required_channels text[] not null default '{}';

create index if not exists idx_content_reviewer on public.content_items(workspace_id, reviewer_id);

create table if not exists public.notification_outbox (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  event_type text not null,
  recipient_id uuid references public.user_profiles(id),
  payload jsonb not null default '{}',
  idempotency_key text not null unique,
  status text not null default 'PENDING' check (status in ('PENDING', 'PROCESSING', 'SENT', 'FAILED', 'CANCELED')),
  retry_count integer not null default 0,
  max_retries integer not null default 3,
  last_error text,
  scheduled_at timestamptz not null default now(),
  sent_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_notification_outbox_queue
  on public.notification_outbox(status, scheduled_at);

alter table public.notification_outbox enable row level security;

create policy admins_can_read_notification_outbox
  on public.notification_outbox for select
  using (private.has_workspace_role(workspace_id, array['SUPER_ADMIN', 'WORKSPACE_ADMIN', 'MANAGER']));

comment on column public.content_items.reviewer_id is 'Explicit reviewer assignment; avoids treating every manager as the implicit reviewer.';
comment on column public.content_items.required_channels is 'Channels that must pass copy/media/integration validation before publishing.';
comment on table public.notification_outbox is 'Durable notification events; workers should claim by idempotency_key and retry safely.';
