export type AutomationStatus =
  | "NOT_STARTED"
  | "QUEUED"
  | "GENERATING"
  | "NEEDS_REVIEW"
  | "CHANGES_REQUESTED"
  | "APPROVED"
  | "READY_TO_PUBLISH"
  | "PUBLISHING"
  | "PARTIALLY_PUBLISHED"
  | "PUBLISHED"
  | "FAILED"
  | "CANCELED";

export type Priority = "LOW" | "NORMAL" | "HIGH" | "URGENT";

export type ContentItem = {
  id: string;
  workspaceId?: string;
  projectId?: string;
  topic: string;
  project: string;
  group: string;
  funnel: string;
  briefStatus: string;
  writer: string;
  publisher: string;
  plannedDate: string;
  automationStatus: AutomationStatus;
  priority: Priority;
  progress: number;
  liveUrl?: string;
  channels: number;
  media: boolean;
  updatedAt: string;
  briefText: string;
  copies: Record<string, string>;
};

export type PublishingJob = {
  id: string;
  channel: string;
  status: string;
  externalPostUrl?: string | null;
  lastError?: string | null;
  scheduledFor?: string | null;
  createdAt: string;
};

export type WorkspaceProject = {
  id: string;
  name: string;
  slug: string;
  status: string;
};

export type WorkspaceMember = {
  userId: string;
  fullName: string;
  role: string;
  status: string;
  email?: string | null;
};

export type WorkspaceContext = {
  workspaceId: string;
  userId: string;
  email?: string | null;
  roles: string[];
  permissions: string[];
};

export type AuditRecord = {
  id: string;
  workspaceId: string;
  actorId: string;
  action: string;
  entityType: string;
  entityId?: string | null;
  previousValue?: Record<string, unknown> | null;
  newValue?: Record<string, unknown> | null;
  createdAt: string;
};

export type AuditRetentionPolicy = {
  retentionDays: number;
  cutoffAt: string;
};

export type NotificationEvent = {
  id: string;
  workspaceId: string;
  eventType: string;
  recipientId?: string | null;
  status: string;
  retryCount: number;
  payload: Record<string, unknown>;
  providerMessageId?: string | null;
  providerEventType?: string | null;
  deliveredAt?: string | null;
  bouncedAt?: string | null;
  unsubscribedAt?: string | null;
  createdAt: string;
  sentAt?: string | null;
  lastError?: string | null;
};

export type ProviderHealth = {
  provider: string;
  status: string;
  checkedAt: string;
  probe?: string;
  responseTimeMs?: number | null;
};

export type HealthRecord = {
  id: string;
  component: string;
  status: string;
  responseTimeMs?: number | null;
  details: Record<string, unknown>;
  checkedAt: string;
};
