-- AXIS Content Automation: initial Supabase/Postgres schema
-- Apply this migration only to a development/staging Supabase project first.

create extension if not exists pgcrypto;

create schema if not exists private;

create table if not exists public.workspaces (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  slug text not null unique,
  logo_url text,
  timezone text not null default 'Asia/Dhaka',
  default_language text not null default 'en',
  default_ai_provider text not null default 'OPENAI',
  status text not null default 'ACTIVE' check (status in ('ACTIVE', 'SUSPENDED', 'ARCHIVED')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.user_profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  full_name text not null default '',
  avatar_url text,
  status text not null default 'ACTIVE' check (status in ('INVITED', 'ACTIVE', 'DISABLED', 'SUSPENDED', 'DELETED')),
  last_login_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.workspace_members (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  user_id uuid not null references public.user_profiles(id) on delete cascade,
  role text not null check (role in ('SUPER_ADMIN', 'WORKSPACE_ADMIN', 'MANAGER', 'TEAM_MEMBER', 'REVIEWER', 'PUBLISHER', 'READ_ONLY')),
  status text not null default 'ACTIVE' check (status in ('INVITED', 'ACTIVE', 'DISABLED', 'SUSPENDED', 'DELETED')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (workspace_id, user_id)
);

create table if not exists public.projects (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  name text not null,
  slug text not null,
  description text,
  website_url text,
  industry text,
  target_audience text,
  brand_voice text,
  prohibited_words text[] not null default '{}',
  preferred_cta text,
  default_writer_id uuid references public.user_profiles(id),
  default_publisher_id uuid references public.user_profiles(id),
  default_channels text[] not null default '{}',
  nuelink_destination_mappings jsonb not null default '{}',
  slack_channel text,
  timezone text not null default 'Asia/Dhaka',
  status text not null default 'ACTIVE' check (status in ('ACTIVE', 'ARCHIVED')),
  created_by uuid not null references public.user_profiles(id),
  updated_by uuid not null references public.user_profiles(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (workspace_id, slug)
);

create table if not exists public.project_members (
  project_id uuid not null references public.projects(id) on delete cascade,
  user_id uuid not null references public.user_profiles(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (project_id, user_id)
);

create table if not exists public.content_items (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  project_id uuid not null references public.projects(id),
  topic text not null check (char_length(topic) between 3 and 300),
  group_or_month text,
  page_type text,
  format_or_intent text,
  funnel_stage text,
  brief_status text not null default 'NOT_STARTED' check (brief_status in ('NOT_STARTED', 'IN_PROGRESS', 'BRIEF_READY', 'CHANGES_REQUESTED', 'COMPLETE')),
  brief_link text,
  brief_text text,
  writer_id uuid references public.user_profiles(id),
  writer_status text not null default 'NOT_ASSIGNED' check (writer_status in ('NOT_ASSIGNED', 'ASSIGNED', 'WRITING', 'READY_FOR_REVIEW', 'COMPLETED', 'BLOCKED')),
  content_status text not null default 'NOT_STARTED' check (content_status in ('NOT_STARTED', 'WRITING', 'EDITING', 'READY', 'PUBLISHED', 'ARCHIVED')),
  publisher_id uuid references public.user_profiles(id),
  planned_publish_date timestamptz,
  actual_publish_date timestamptz,
  progress_percentage integer not null default 0 check (progress_percentage between 0 and 100),
  live_url text,
  automation_status text not null default 'NOT_STARTED' check (automation_status in ('NOT_STARTED', 'QUEUED', 'GENERATING', 'NEEDS_REVIEW', 'CHANGES_REQUESTED', 'APPROVED', 'READY_TO_PUBLISH', 'PUBLISHING', 'PARTIALLY_PUBLISHED', 'PUBLISHED', 'FAILED', 'CANCELED')),
  automation_publisher text,
  priority text not null default 'NORMAL' check (priority in ('LOW', 'NORMAL', 'HIGH', 'URGENT')),
  internal_notes text,
  created_by uuid not null references public.user_profiles(id),
  updated_by uuid not null references public.user_profiles(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  archived_at timestamptz,
  deleted_at timestamptz
);

create table if not exists public.content_versions (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  content_item_id uuid not null references public.content_items(id) on delete cascade,
  version_number integer not null,
  snapshot jsonb not null,
  created_by uuid not null references public.user_profiles(id),
  created_at timestamptz not null default now(),
  unique (content_item_id, version_number)
);

create table if not exists public.social_copies (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  content_item_id uuid not null references public.content_items(id) on delete cascade,
  channel text not null check (channel in ('FACEBOOK_INSTAGRAM', 'LINKEDIN', 'YOUTUBE', 'GBP', 'REDDIT')),
  title text,
  body text,
  first_comment text,
  hashtags jsonb not null default '[]',
  metadata jsonb not null default '{}',
  status text not null default 'DRAFT' check (status in ('DRAFT', 'NEEDS_REVIEW', 'APPROVED', 'CHANGES_REQUESTED')),
  current_version integer not null default 1,
  generated_by_provider text,
  generated_model text,
  generated_at timestamptz,
  created_by uuid not null references public.user_profiles(id),
  updated_by uuid not null references public.user_profiles(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (content_item_id, channel)
);

create table if not exists public.social_copy_versions (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  social_copy_id uuid not null references public.social_copies(id) on delete cascade,
  version_number integer not null,
  title text,
  body text,
  first_comment text,
  hashtags jsonb not null default '[]',
  metadata jsonb not null default '{}',
  created_by uuid not null references public.user_profiles(id),
  created_at timestamptz not null default now(),
  unique (social_copy_id, version_number)
);

create table if not exists public.media_assets (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  project_id uuid not null references public.projects(id),
  storage_path text not null,
  delivery_url text,
  thumbnail_url text,
  original_filename text not null,
  mime_type text not null,
  file_size_bytes bigint not null check (file_size_bytes > 0),
  width integer,
  height integer,
  source text not null default 'UPLOAD' check (source in ('UPLOAD', 'URL', 'GOOGLE_DRIVE', 'LIBRARY')),
  status text not null default 'UPLOADING' check (status in ('UPLOADING', 'PROCESSING', 'READY', 'FAILED', 'DELETED')),
  uploaded_by uuid not null references public.user_profiles(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  deleted_at timestamptz
);

create table if not exists public.content_media (
  content_item_id uuid not null references public.content_items(id) on delete cascade,
  media_asset_id uuid not null references public.media_assets(id) on delete cascade,
  sort_order integer not null default 0,
  created_at timestamptz not null default now(),
  primary key (content_item_id, media_asset_id)
);

create table if not exists public.approvals (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  content_item_id uuid not null references public.content_items(id) on delete cascade,
  reviewer_id uuid not null references public.user_profiles(id),
  decision text not null check (decision in ('SUBMITTED', 'APPROVED', 'CHANGES_REQUESTED', 'REJECTED', 'REOPENED', 'CANCELED')),
  notes text,
  content_version integer,
  copy_version integer,
  previous_status text,
  new_status text,
  created_at timestamptz not null default now()
);

create table if not exists public.publishing_jobs (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  project_id uuid not null references public.projects(id),
  content_item_id uuid not null references public.content_items(id) on delete cascade,
  social_copy_id uuid references public.social_copies(id),
  channel text not null,
  provider text not null,
  status text not null default 'PENDING' check (status in ('PENDING', 'QUEUED', 'PROCESSING', 'SUCCEEDED', 'FAILED', 'RETRY_SCHEDULED', 'CANCELED', 'MANUAL_REQUIRED', 'SKIPPED')),
  idempotency_key text not null unique,
  scheduled_for timestamptz,
  started_at timestamptz,
  completed_at timestamptz,
  external_post_id text,
  external_post_url text,
  retry_count integer not null default 0,
  max_retries integer not null default 3,
  last_error text,
  created_by uuid not null references public.user_profiles(id),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.notifications (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  recipient_id uuid not null references public.user_profiles(id),
  type text not null,
  title text not null,
  body text,
  entity_type text,
  entity_id uuid,
  read_at timestamptz,
  created_at timestamptz not null default now()
);

create table if not exists public.activity_logs (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  actor_id uuid references public.user_profiles(id),
  action text not null,
  entity_type text not null,
  entity_id uuid,
  summary text not null,
  metadata jsonb not null default '{}',
  created_at timestamptz not null default now()
);

create table if not exists public.audit_logs (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid references public.workspaces(id) on delete set null,
  actor_id uuid references public.user_profiles(id),
  action text not null,
  entity_type text not null,
  entity_id uuid,
  previous_value jsonb,
  new_value jsonb,
  ip_address inet,
  user_agent text,
  request_id text,
  created_at timestamptz not null default now()
);

create table if not exists public.error_logs (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid references public.workspaces(id) on delete set null,
  project_id uuid references public.projects(id) on delete set null,
  content_id uuid references public.content_items(id) on delete set null,
  job_id uuid references public.publishing_jobs(id) on delete set null,
  error_type text not null,
  error_code text not null,
  message text not null,
  stack_trace text,
  provider_response jsonb,
  retryable boolean not null default false,
  retry_count integer not null default 0,
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  resolved_at timestamptz,
  resolved_by uuid references public.user_profiles(id)
);

create table if not exists public.job_queue (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  type text not null,
  payload jsonb not null default '{}',
  status text not null default 'QUEUED' check (status in ('QUEUED', 'PROCESSING', 'SUCCEEDED', 'FAILED', 'CANCELED', 'DEAD_LETTER')),
  idempotency_key text unique,
  retry_count integer not null default 0,
  max_retries integer not null default 3,
  scheduled_at timestamptz not null default now(),
  started_at timestamptz,
  completed_at timestamptz,
  error text,
  created_at timestamptz not null default now()
);

create table if not exists public.ai_usage_logs (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid not null references public.workspaces(id) on delete cascade,
  content_item_id uuid references public.content_items(id) on delete set null,
  provider text not null,
  model text,
  prompt_tokens integer,
  completion_tokens integer,
  estimated_cost numeric(12, 6),
  success boolean not null default false,
  created_at timestamptz not null default now()
);

create index if not exists idx_content_workspace_project on public.content_items(workspace_id, project_id);
create index if not exists idx_content_workspace_status on public.content_items(workspace_id, automation_status);
create index if not exists idx_content_writer on public.content_items(workspace_id, writer_id);
create index if not exists idx_content_publisher on public.content_items(workspace_id, publisher_id);
create index if not exists idx_content_planned_date on public.content_items(workspace_id, planned_publish_date);
create index if not exists idx_content_updated on public.content_items(workspace_id, updated_at desc);
create index if not exists idx_activity_workspace_created on public.activity_logs(workspace_id, created_at desc);
create index if not exists idx_errors_workspace_last_seen on public.error_logs(workspace_id, last_seen_at desc);
create index if not exists idx_jobs_workspace_status on public.job_queue(workspace_id, status, scheduled_at);
create index if not exists idx_publishing_content on public.publishing_jobs(workspace_id, content_item_id, channel);

create or replace function private.is_active_workspace_member(target_workspace_id uuid)
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1
    from public.workspace_members wm
    join public.user_profiles up on up.id = wm.user_id
    where wm.workspace_id = target_workspace_id
      and wm.user_id = auth.uid()
      and wm.status = 'ACTIVE'
      and up.status = 'ACTIVE'
  );
$$;

create or replace function private.has_workspace_role(target_workspace_id uuid, allowed_roles text[])
returns boolean
language sql
stable
security definer
set search_path = public
as $$
  select exists (
    select 1 from public.workspace_members
    where workspace_id = target_workspace_id
      and user_id = auth.uid()
      and status = 'ACTIVE'
      and role = any(allowed_roles)
  );
$$;

alter table public.workspaces enable row level security;
alter table public.user_profiles enable row level security;
alter table public.workspace_members enable row level security;
alter table public.projects enable row level security;
alter table public.project_members enable row level security;
alter table public.content_items enable row level security;
alter table public.content_versions enable row level security;
alter table public.social_copies enable row level security;
alter table public.social_copy_versions enable row level security;
alter table public.media_assets enable row level security;
alter table public.content_media enable row level security;
alter table public.approvals enable row level security;
alter table public.publishing_jobs enable row level security;
alter table public.notifications enable row level security;
alter table public.activity_logs enable row level security;
alter table public.audit_logs enable row level security;
alter table public.error_logs enable row level security;
alter table public.job_queue enable row level security;
alter table public.ai_usage_logs enable row level security;

create policy workspace_members_can_read_workspaces on public.workspaces for select using (private.is_active_workspace_member(id));
create policy workspace_admins_can_manage_workspaces on public.workspaces for update using (private.has_workspace_role(id, array['SUPER_ADMIN', 'WORKSPACE_ADMIN']));

create policy users_can_read_own_profile on public.user_profiles for select using (id = auth.uid());
create policy members_can_read_workspace_profiles on public.user_profiles for select using (
  exists (select 1 from public.workspace_members wm where wm.user_id = user_profiles.id and private.is_active_workspace_member(wm.workspace_id))
);

create policy members_can_read_memberships on public.workspace_members for select using (private.is_active_workspace_member(workspace_id));
create policy admins_can_manage_memberships on public.workspace_members for all using (private.has_workspace_role(workspace_id, array['SUPER_ADMIN', 'WORKSPACE_ADMIN']));

create policy members_can_read_projects on public.projects for select using (private.is_active_workspace_member(workspace_id));
create policy managers_can_manage_projects on public.projects for all using (private.has_workspace_role(workspace_id, array['SUPER_ADMIN', 'WORKSPACE_ADMIN', 'MANAGER']));

create policy members_can_read_project_members on public.project_members for select using (
  exists (select 1 from public.projects p where p.id = project_members.project_id and private.is_active_workspace_member(p.workspace_id))
);

create policy members_can_read_content on public.content_items for select using (private.is_active_workspace_member(workspace_id));
create policy editors_can_manage_content on public.content_items for all using (private.has_workspace_role(workspace_id, array['SUPER_ADMIN', 'WORKSPACE_ADMIN', 'MANAGER', 'TEAM_MEMBER', 'REVIEWER', 'PUBLISHER']));

create policy members_can_read_content_versions on public.content_versions for select using (private.is_active_workspace_member(workspace_id));
create policy members_can_read_social_copies on public.social_copies for select using (private.is_active_workspace_member(workspace_id));
create policy editors_can_manage_social_copies on public.social_copies for all using (private.has_workspace_role(workspace_id, array['SUPER_ADMIN', 'WORKSPACE_ADMIN', 'MANAGER', 'TEAM_MEMBER', 'REVIEWER']));
create policy members_can_read_social_copy_versions on public.social_copy_versions for select using (private.is_active_workspace_member(workspace_id));
create policy members_can_read_media on public.media_assets for select using (private.is_active_workspace_member(workspace_id));
create policy editors_can_manage_media on public.media_assets for all using (private.has_workspace_role(workspace_id, array['SUPER_ADMIN', 'WORKSPACE_ADMIN', 'MANAGER', 'TEAM_MEMBER']));
create policy members_can_read_content_media on public.content_media for select using (
  exists (select 1 from public.content_items c where c.id = content_media.content_item_id and private.is_active_workspace_member(c.workspace_id))
);
create policy members_can_read_approvals on public.approvals for select using (private.is_active_workspace_member(workspace_id));
create policy reviewers_can_write_approvals on public.approvals for insert with check (private.has_workspace_role(workspace_id, array['SUPER_ADMIN', 'WORKSPACE_ADMIN', 'MANAGER', 'REVIEWER']));
create policy members_can_read_publishing_jobs on public.publishing_jobs for select using (private.is_active_workspace_member(workspace_id));
create policy publishers_can_manage_publishing_jobs on public.publishing_jobs for all using (private.has_workspace_role(workspace_id, array['SUPER_ADMIN', 'WORKSPACE_ADMIN', 'MANAGER', 'PUBLISHER']));
create policy users_can_read_notifications on public.notifications for select using (recipient_id = auth.uid() and private.is_active_workspace_member(workspace_id));
create policy users_can_update_notifications on public.notifications for update using (recipient_id = auth.uid());
create policy members_can_read_activity on public.activity_logs for select using (private.is_active_workspace_member(workspace_id));
create policy members_can_read_audit on public.audit_logs for select using (private.has_workspace_role(workspace_id, array['SUPER_ADMIN', 'WORKSPACE_ADMIN']));
create policy members_can_read_errors on public.error_logs for select using (workspace_id is null or private.is_active_workspace_member(workspace_id));
create policy operators_can_manage_jobs on public.job_queue for all using (private.has_workspace_role(workspace_id, array['SUPER_ADMIN', 'WORKSPACE_ADMIN', 'MANAGER']));
create policy members_can_read_ai_usage on public.ai_usage_logs for select using (private.is_active_workspace_member(workspace_id));

revoke all on public.audit_logs from authenticated;
grant select on public.audit_logs to authenticated;

comment on table public.audit_logs is 'Append-only security history. Inserts are performed by the backend service role; normal users receive read-only access through RLS.';
comment on table public.publishing_jobs is 'One idempotent job per content/channel/copy version/schedule combination.';
