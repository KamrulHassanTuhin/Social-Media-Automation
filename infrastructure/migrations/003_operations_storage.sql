-- Persistent worker claims, notification claims, and private media storage.

alter table public.job_queue
  add column if not exists claimed_by text,
  add column if not exists claimed_at timestamptz,
  add column if not exists visibility_timeout_at timestamptz;

alter table public.notification_outbox
  add column if not exists claimed_by text,
  add column if not exists claimed_at timestamptz,
  add column if not exists visibility_timeout_at timestamptz;

create index if not exists idx_job_queue_claimable
  on public.job_queue(status, scheduled_at, visibility_timeout_at);

create or replace function public.claim_next_job(worker_id text, visibility_seconds integer default 300)
returns public.job_queue
language plpgsql
security definer
set search_path = public
as $$
declare claimed public.job_queue;
begin
  with candidate as (
    select id
    from public.job_queue
    where (status in ('QUEUED', 'RETRY_SCHEDULED') and scheduled_at <= now())
       or (status = 'PROCESSING' and visibility_timeout_at < now())
    order by scheduled_at asc
    for update skip locked
    limit 1
  )
  update public.job_queue q
  set status = 'PROCESSING',
      claimed_by = worker_id,
      claimed_at = now(),
      visibility_timeout_at = now() + make_interval(secs => visibility_seconds),
      started_at = coalesce(started_at, now())
  from candidate
  where q.id = candidate.id
  returning q.* into claimed;
  return claimed;
end;
$$;

create or replace function public.complete_job(job_id uuid)
returns void
language sql
security definer
set search_path = public
as $$
  update public.job_queue
  set status = 'SUCCEEDED', completed_at = now(), visibility_timeout_at = null
  where id = job_id;
$$;

create or replace function public.claim_next_notification(worker_id text, visibility_seconds integer default 300)
returns public.notification_outbox
language plpgsql
security definer
set search_path = public
as $$
declare claimed public.notification_outbox;
begin
  with candidate as (
    select id
    from public.notification_outbox
    where status = 'PENDING'
       or (status = 'PROCESSING' and visibility_timeout_at < now())
    order by scheduled_at asc
    for update skip locked
    limit 1
  )
  update public.notification_outbox n
  set status = 'PROCESSING',
      claimed_by = worker_id,
      claimed_at = now(),
      visibility_timeout_at = now() + make_interval(secs => visibility_seconds)
  from candidate
  where n.id = candidate.id
  returning n.* into claimed;
  return claimed;
end;
$$;

insert into storage.buckets (id, name, public)
values ('axis-media', 'axis-media', false)
on conflict (id) do nothing;

create policy axis_media_read_for_workspace_members
on storage.objects for select to authenticated
using (
  bucket_id = 'axis-media'
  and private.is_active_workspace_member((storage.foldername(name))[2]::uuid)
);

create policy axis_media_insert_for_workspace_members
on storage.objects for insert to authenticated
with check (
  bucket_id = 'axis-media'
  and private.is_active_workspace_member((storage.foldername(name))[2]::uuid)
);

create policy axis_media_delete_for_workspace_admins
on storage.objects for delete to authenticated
using (
  bucket_id = 'axis-media'
  and private.has_workspace_role((storage.foldername(name))[2]::uuid, array['SUPER_ADMIN', 'WORKSPACE_ADMIN'])
);
