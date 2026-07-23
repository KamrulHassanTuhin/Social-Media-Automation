-- Encrypted integration credentials and operator-visible integration status.

create table if not exists public.integrations (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  provider text not null,
  status text not null default 'NOT_CONFIGURED' check (status in ('NOT_CONFIGURED', 'CONNECTED', 'DISCONNECTED', 'INVALID_CREDENTIALS', 'DEGRADED', 'ERROR')),
  settings jsonb not null default '{}',
  last_tested_at timestamptz,
  last_successful_use timestamptz,
  last_error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (workspace_id, provider)
);

create table if not exists public.integration_credentials (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  provider text not null,
  ciphertext text not null,
  nonce text not null,
  key_version text not null default 'v1',
  rotated_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  unique (workspace_id, provider)
);

create table if not exists public.system_health_checks (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid references public.workspaces(id) on delete cascade,
  component text not null,
  status text not null,
  response_time_ms integer,
  details jsonb not null default '{}',
  checked_at timestamptz not null default now()
);

create index if not exists idx_integrations_workspace on public.integrations(workspace_id, provider);
create index if not exists idx_health_component on public.system_health_checks(workspace_id, component, checked_at desc);

alter table public.integrations enable row level security;
alter table public.integration_credentials enable row level security;
alter table public.system_health_checks enable row level security;

create policy workspace_members_can_read_integrations
on public.integrations for select
using (private.is_active_workspace_member(workspace_id));

create policy workspace_admins_can_manage_integrations
on public.integrations for all
using (private.has_workspace_role(workspace_id, array['SUPER_ADMIN', 'WORKSPACE_ADMIN']));

create policy workspace_members_can_read_health_checks
on public.system_health_checks for select
using (workspace_id is null or private.is_active_workspace_member(workspace_id));

revoke all on public.integration_credentials from authenticated;
comment on table public.integration_credentials is 'Ciphertext only. Plaintext credentials are never returned to clients or stored in logs.';
