-- Workspace-scoped audit retention policy. Purges are performed by the backend service role.

create table if not exists public.audit_retention_policies (
  workspace_id uuid primary key references public.workspaces(id) on delete cascade,
  retention_days integer not null default 365 check (retention_days between 30 and 3650),
  updated_by uuid references public.user_profiles(id),
  updated_at timestamptz not null default now()
);

alter table public.audit_retention_policies enable row level security;

create policy admins_can_read_audit_retention
  on public.audit_retention_policies for select
  using (private.has_workspace_role(workspace_id, array['SUPER_ADMIN', 'WORKSPACE_ADMIN']));

revoke all on public.audit_retention_policies from authenticated;
grant select on public.audit_retention_policies to authenticated;

create index if not exists idx_audit_logs_workspace_created
  on public.audit_logs(workspace_id, created_at desc);

comment on table public.audit_retention_policies is 'Workspace retention policy for append-only audit history; deletion is backend-admin controlled.';
