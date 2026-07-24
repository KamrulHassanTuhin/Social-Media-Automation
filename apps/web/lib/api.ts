import type { AuditRecord, AuditRetentionPolicy, ContentItem, HealthRecord, NotificationEvent, ProviderHealth, PublishingJob, WorkspaceContext, WorkspaceMember, WorkspaceProject } from "./types";
import { createSupabaseBrowserClient } from "./supabase/browser";

type ApiEnvelope<T> = {
  success: boolean;
  data: T;
  error: { code: string; message: string; details?: Record<string, unknown> } | null;
  meta?: Record<string, unknown>;
};

type ApiContent = {
  id: string;
  workspace_id: string;
  project_id: string;
  topic: string;
  brief_status: string;
  automation_status: ContentItem["automationStatus"];
  publisher_id: string | null;
  live_url: string | null;
  has_media: boolean;
  copies: Record<string, string>;
  updated_at: string;
};

type ApiPublishingJob = {
  id: string;
  channel: string;
  status: string;
  external_post_url: string | null;
  last_error: string | null;
  scheduled_for: string | null;
  created_at: string;
};

type ApiProject = { id: string; name: string; slug: string; status: string };
type ApiMember = { user_id: string; full_name: string; role: string; status: string; email?: string | null };
type ApiAudit = { id: string; workspace_id: string; actor_id: string; action: string; entity_type: string; entity_id: string | null; previous_value: Record<string, unknown> | null; new_value: Record<string, unknown> | null; created_at: string };
type ApiNotification = { id: string; workspace_id: string; event_type: string; recipient_id: string | null; status: string; retry_count: number; payload: Record<string, unknown>; provider_message_id: string | null; provider_event_type: string | null; delivered_at: string | null; bounced_at: string | null; unsubscribed_at: string | null; created_at: string; sent_at: string | null; last_error: string | null };

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";
const defaultWorkspaceId = process.env.NEXT_PUBLIC_DEFAULT_WORKSPACE_ID;
const apiRootUrl = apiBaseUrl.replace(/\/api\/v1\/?$/, "");

async function resolveAccessToken(explicitToken?: string): Promise<string | undefined> {
  if (explicitToken) return explicitToken;
  const client = createSupabaseBrowserClient();
  if (!client) return undefined;
  const { data: { session } } = await client.auth.getSession();
  return session?.access_token;
}

function mapApiContent(item: ApiContent): ContentItem {
  return {
    id: item.id,
    workspaceId: item.workspace_id,
    projectId: item.project_id,
    topic: item.topic,
    project: item.project_id,
    group: "Unscheduled",
    funnel: "TOFU",
    briefStatus: item.brief_status,
    writer: "—",
    publisher: item.publisher_id ?? "—",
    plannedDate: "Not planned",
    automationStatus: item.automation_status,
    priority: "NORMAL",
    progress: item.automation_status === "PUBLISHED" ? 100 : item.automation_status === "NOT_STARTED" ? 0 : 50,
    liveUrl: item.live_url ?? undefined,
    channels: Object.keys(item.copies).length,
    media: item.has_media,
    updatedAt: new Date(item.updated_at).toLocaleString(),
    briefText: "Brief loaded from the API.",
    copies: item.copies,
  };
}

async function apiRequest<T>(path: string, init: RequestInit = {}, options: { token?: string } = {}): Promise<T> {
  const token = await resolveAccessToken(options.token);
  const headers = new Headers(init.headers);
  if (!headers.has("Content-Type") && init.body) headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (defaultWorkspaceId && !headers.has("X-Workspace-ID")) headers.set("X-Workspace-ID", defaultWorkspaceId);
  const response = await fetch(`${apiBaseUrl}${path}`, { ...init, headers, cache: "no-store" });
  const payload = await response.json() as ApiEnvelope<T>;
  if (!response.ok || !payload.success) throw new Error(payload.error?.message ?? "API request failed.");
  return payload.data;
}

async function healthRequest<T>(path: string): Promise<T> {
  const response = await fetch(`${apiRootUrl}${path}`, { cache: "no-store" });
  const payload = await response.json() as { data?: T };
  if (!response.ok || payload.data === undefined) throw new Error("Unable to load system health.");
  return payload.data;
}

export async function getProviderHealth(probe = true): Promise<ProviderHealth[]> {
  const records = await healthRequest<Array<{ provider: string; status: string; checked_at: string; probe?: string; response_time_ms?: number | null }>>(`/health/providers?probe=${probe ? "true" : "false"}`);
  return records.map((record) => ({ provider: record.provider, status: record.status, checkedAt: record.checked_at, probe: record.probe, responseTimeMs: record.response_time_ms }));
}

export async function getHealthHistory(limit = 50): Promise<HealthRecord[]> {
  const records = await healthRequest<Array<{ id: string; component: string; status: string; response_time_ms?: number | null; details: Record<string, unknown>; checked_at: string }>>(`/health/history?limit=${limit}`);
  return records.map((record) => ({ id: record.id, component: record.component, status: record.status, responseTimeMs: record.response_time_ms, details: record.details, checkedAt: record.checked_at }));
}

export async function listContent(options: { search?: string; token?: string } = {}): Promise<ContentItem[]> {
  const url = new URL(`${apiBaseUrl}/content`);
  if (options.search) url.searchParams.set("search", options.search);
  const token = await resolveAccessToken(options.token);
  const headers = new Headers();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (defaultWorkspaceId) headers.set("X-Workspace-ID", defaultWorkspaceId);
  const response = await fetch(url, {
    headers,
    cache: "no-store",
  });
  const payload = await response.json() as ApiEnvelope<ApiContent[]>;
  if (!response.ok || !payload.success) throw new Error(payload.error?.message ?? "Unable to load content.");
  return payload.data.map(mapApiContent);
}

export async function scheduleContent(contentId: string, scheduledFor: string, options: { token?: string } = {}): Promise<void> {
  await apiRequest(`/content/${contentId}/schedule`, {
    method: "POST",
    body: JSON.stringify({ scheduled_for: scheduledFor }),
  }, options);
}

export async function createContent(topic: string, projectId: string, briefStatus = "NOT_STARTED", options: { token?: string } = {}): Promise<ContentItem> {
  const item = await apiRequest<ApiContent>("/content", { method: "POST", body: JSON.stringify({ topic, project_id: projectId, brief_status: briefStatus }) }, options);
  return mapApiContent(item);
}

export async function generateContent(contentId: string, options: { token?: string } = {}): Promise<void> {
  await apiRequest(`/content/${contentId}/generate`, { method: "POST", body: JSON.stringify({}) }, options);
}

export async function approveContent(contentId: string, options: { token?: string } = {}): Promise<void> {
  await apiRequest(`/content/${contentId}/approve`, { method: "POST" }, options);
}

export async function publishContent(contentId: string, options: { token?: string } = {}): Promise<void> {
  await apiRequest(`/content/${contentId}/publish`, { method: "POST" }, options);
}

export async function listPublishingJobs(contentId: string, options: { token?: string } = {}): Promise<PublishingJob[]> {
  const jobs = await apiRequest<ApiPublishingJob[]>(`/publishing-jobs/content/${contentId}`, {}, options);
  return jobs.map((job) => ({ id: job.id, channel: job.channel, status: job.status, externalPostUrl: job.external_post_url, lastError: job.last_error, scheduledFor: job.scheduled_for, createdAt: job.created_at }));
}

export async function retryPublishingJob(jobId: string, options: { token?: string } = {}): Promise<void> {
  await apiRequest(`/publishing-jobs/${jobId}/retry`, { method: "POST" }, options);
}

export async function uploadMedia(file: File, projectId: string, contentId: string, options: { token?: string } = {}): Promise<void> {
  const token = await resolveAccessToken(options.token);
  const headers = new Headers();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (defaultWorkspaceId) headers.set("X-Workspace-ID", defaultWorkspaceId);
  const body = new FormData();
  body.append("file", file);
  body.append("project_id", projectId);
  body.append("content_id", contentId);
  const response = await fetch(`${apiBaseUrl}/media/upload`, { method: "POST", headers, body });
  const payload = await response.json() as ApiEnvelope<unknown>;
  if (!response.ok || !payload.success) throw new Error(payload.error?.message ?? "Unable to upload media.");
}

export async function listProjects(options: { token?: string; includeArchived?: boolean } = {}): Promise<WorkspaceProject[]> {
  const path = options.includeArchived ? "/workspace/projects?include_archived=true" : "/workspace/projects";
  return apiRequest<ApiProject[]>(path, {}, options);
}

export async function listMembers(options: { token?: string } = {}): Promise<WorkspaceMember[]> {
  const members = await apiRequest<ApiMember[]>("/workspace/members", {}, options);
  return members.map((member) => ({ userId: member.user_id, fullName: member.full_name, role: member.role, status: member.status, email: member.email ?? null }));
}

export async function getWorkspaceContext(options: { token?: string } = {}): Promise<WorkspaceContext> {
  const context = await apiRequest<{ workspace_id: string; workspace_name: string; user_id: string; email: string | null; roles: string[]; permissions: string[] }>("/workspace/context", {}, options);
  return { workspaceId: context.workspace_id, workspaceName: context.workspace_name, userId: context.user_id, email: context.email, roles: context.roles, permissions: context.permissions };
}

export async function createProject(name: string, slug?: string): Promise<WorkspaceProject> {
  return apiRequest<WorkspaceProject>("/workspace/projects", { method: "POST", body: JSON.stringify({ name, slug }) });
}

export async function inviteMember(email: string, role: string): Promise<WorkspaceMember> {
  const member = await apiRequest<{ user_id: string; full_name: string; role: string; status: string; email: string }>("/workspace/members/invite", { method: "POST", body: JSON.stringify({ email, role }) });
  return { userId: member.user_id, fullName: member.full_name, role: member.role, status: member.status, email: member.email };
}

export async function updateMemberRole(userId: string, role: string): Promise<WorkspaceMember> {
  const member = await apiRequest<{ user_id: string; full_name: string; role: string; status: string; email: string | null }>(`/workspace/members/${userId}/role`, { method: "PATCH", body: JSON.stringify({ role }) });
  return { userId: member.user_id, fullName: member.full_name, role: member.role, status: member.status, email: member.email };
}

export async function listAuditLog(options: { action?: string } = {}): Promise<AuditRecord[]> {
  const path = options.action ? `/workspace/audit-log?action=${encodeURIComponent(options.action)}` : "/workspace/audit-log";
  const records = await apiRequest<ApiAudit[]>(path);
  return records.map((record) => ({ id: record.id, workspaceId: record.workspace_id, actorId: record.actor_id, action: record.action, entityType: record.entity_type, entityId: record.entity_id, previousValue: record.previous_value, newValue: record.new_value, createdAt: record.created_at }));
}

export async function updateProject(projectId: string, payload: { name: string; slug: string; status: "ACTIVE" | "ARCHIVED" }): Promise<WorkspaceProject> {
  return apiRequest<WorkspaceProject>(`/workspace/projects/${projectId}`, { method: "PATCH", body: JSON.stringify(payload) });
}

export async function acceptInvitation(workspaceId: string): Promise<void> {
  await apiRequest("/workspace/invitations/accept", { method: "POST", headers: { "X-Workspace-ID": workspaceId } });
}

export async function updateMemberStatus(userId: string, status: "ACTIVE" | "DISABLED"): Promise<WorkspaceMember> {
  const member = await apiRequest<{ user_id: string; full_name: string; role: string; status: string; email: string | null }>(`/workspace/members/${userId}/status`, { method: "PATCH", body: JSON.stringify({ status }) });
  return { userId: member.user_id, fullName: member.full_name, role: member.role, status: member.status, email: member.email };
}

export async function previewInvitationEmail(email: string): Promise<{ subject: string; preview: string; bodyText: string }> {
  const data = await apiRequest<{ subject: string; preview: string; body_text: string }>("/workspace/invitations/preview", { method: "POST", body: JSON.stringify({ email }) });
  return { subject: data.subject, preview: data.preview, bodyText: data.body_text };
}

export async function exportAuditLog(action?: string): Promise<Blob> {
  const token = await resolveAccessToken();
  const headers = new Headers();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (defaultWorkspaceId) headers.set("X-Workspace-ID", defaultWorkspaceId);
  const path = action ? `/workspace/audit-log.csv?action=${encodeURIComponent(action)}` : "/workspace/audit-log.csv";
  const response = await fetch(`${apiBaseUrl}${path}`, { headers, cache: "no-store" });
  if (!response.ok) throw new Error("Unable to export audit log.");
  return response.blob();
}

export async function getAuditRetention(): Promise<AuditRetentionPolicy> {
  const data = await apiRequest<{ retention_days: number; cutoff_at: string }>("/workspace/audit-retention");
  return { retentionDays: data.retention_days, cutoffAt: data.cutoff_at };
}

export async function updateAuditRetention(retentionDays: number): Promise<AuditRetentionPolicy> {
  const data = await apiRequest<{ retention_days: number; cutoff_at: string }>("/workspace/audit-retention", { method: "PATCH", body: JSON.stringify({ retention_days: retentionDays }) });
  return { retentionDays: data.retention_days, cutoffAt: data.cutoff_at };
}

export async function purgeAuditLog(confirm = false): Promise<{ eligibleCount: number; deletedCount: number; retentionDays: number; cutoffAt: string; dryRun: boolean }> {
  const data = await apiRequest<{ eligible_count: number; deleted_count: number; retention_days: number; cutoff_at: string; dry_run: boolean }>("/workspace/audit-log/retention/purge", { method: "POST", body: JSON.stringify({ confirm }) });
  return { eligibleCount: data.eligible_count, deletedCount: data.deleted_count, retentionDays: data.retention_days, cutoffAt: data.cutoff_at, dryRun: data.dry_run };
}

export async function listNotificationOutbox(): Promise<NotificationEvent[]> {
  const events = await apiRequest<ApiNotification[]>("/notifications/outbox");
  return events.map((event) => ({ id: event.id, workspaceId: event.workspace_id, eventType: event.event_type, recipientId: event.recipient_id, status: event.status, retryCount: event.retry_count, payload: event.payload, providerMessageId: event.provider_message_id, providerEventType: event.provider_event_type, deliveredAt: event.delivered_at, bouncedAt: event.bounced_at, unsubscribedAt: event.unsubscribed_at, createdAt: event.created_at, sentAt: event.sent_at, lastError: event.last_error }));
}

export async function retryNotification(eventId: string): Promise<void> {
  await apiRequest(`/notifications/outbox/${eventId}/retry`, { method: "POST" });
}

export async function getNotificationAnalytics(): Promise<Record<string, number>> {
  return apiRequest<Record<string, number>>("/notifications/analytics");
}
