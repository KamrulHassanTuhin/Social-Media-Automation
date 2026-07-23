"use client";

import { ArrowLeft, Bell, CheckCircle2, Clock3, Loader2, RotateCcw, XCircle } from "lucide-react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getNotificationAnalytics, listNotificationOutbox, retryNotification } from "../lib/api";
import type { NotificationEvent } from "../lib/types";

const demoEvents: NotificationEvent[] = [
  { id: "notification_demo_1", workspaceId: "ws_demo", eventType: "EMAIL", recipientId: "user_demo", status: "SENT", retryCount: 0, payload: { subject: "Copy is ready for review", template: "copy_ready" }, createdAt: new Date().toISOString(), sentAt: new Date().toISOString(), deliveredAt: new Date().toISOString(), lastError: null },
  { id: "notification_demo_2", workspaceId: "ws_demo", eventType: "EMAIL", recipientId: "user_writer", status: "FAILED", retryCount: 2, payload: { subject: "Workspace invitation", template: "workspace_invitation" }, createdAt: new Date().toISOString(), sentAt: null, lastError: "Email provider is not configured." },
];

function statusIcon(status: string) {
  if (status === "SENT") return <CheckCircle2 size={16} />;
  if (status === "FAILED" || status === "BOUNCED") return <XCircle size={16} />;
  if (status === "PROCESSING") return <Loader2 size={16} className="spin" />;
  return <Clock3 size={16} />;
}

export function NotificationsScreen() {
  const useApi = process.env.NEXT_PUBLIC_USE_API === "true";
  const queryClient = useQueryClient();
  const query = useQuery<NotificationEvent[]>({ queryKey: ["notification-outbox"], queryFn: listNotificationOutbox, enabled: useApi });
  const analyticsQuery = useQuery<Record<string, number>>({ queryKey: ["notification-analytics"], queryFn: getNotificationAnalytics, enabled: useApi });
  const events = useApi ? (query.data ?? []) : demoEvents;
  const analytics = useApi ? (analyticsQuery.data ?? {}) : { SENT: 1, BOUNCED: 0, FAILED: 1, UNSUBSCRIBED: 0 };
  const retry = async (event: NotificationEvent) => { if (!useApi) return; await retryNotification(event.id); await queryClient.invalidateQueries({ queryKey: ["notification-outbox"] }); };

  return <main className="management-shell"><header className="management-header"><div><Link className="back-link" href="/"><ArrowLeft size={15} /> Dashboard</Link><span className="eyebrow">AXIS OS / Operations</span><h1>Notifications</h1><p>Track durable notification delivery, retries, and provider errors.</p></div><span className="permission-pill allowed"><Bell size={14} /> Outbox tracking</span></header><section className="management-card"><div className="management-card-header"><div><span className="card-kicker"><Bell size={14} /> Delivery analytics</span><h2>Provider delivery health</h2></div><span className="api-source-pill">{useApi ? (query.isLoading || analyticsQuery.isLoading ? "Loading API" : "API connected") : "Demo data"}</span></div><div className="metrics-grid"><div className="metric-card"><span>Sent</span><strong>{analytics.SENT ?? 0}</strong></div><div className="metric-card"><span>Bounced</span><strong>{analytics.BOUNCED ?? 0}</strong></div><div className="metric-card"><span>Unsubscribed</span><strong>{analytics.UNSUBSCRIBED ?? 0}</strong></div><div className="metric-card"><span>Failed</span><strong>{analytics.FAILED ?? 0}</strong></div></div></section><section className="management-card"><div className="management-card-header"><div><span className="card-kicker"><Bell size={14} /> Delivery outbox</span><h2>{events.length} notification events</h2></div></div><div className="management-table">{events.map((event) => <div className="notification-row" key={event.id}><div className={`notification-icon ${event.status.toLowerCase()}`}>{statusIcon(event.status)}</div><div><strong>{String(event.payload.subject ?? event.eventType)}</strong><span>{event.eventType} · {event.recipientId ?? "workspace recipient"}</span>{event.providerEventType && <small>Provider event: {event.providerEventType}</small>}{event.lastError && <small>{event.lastError}</small>}</div><span className={`notification-status ${event.status.toLowerCase()}`}>{event.status}</span>{event.status === "FAILED" && useApi && <button className="secondary-button" onClick={() => retry(event)}><RotateCcw size={14} /> Retry</button>}</div>)}{events.length === 0 && <div className="management-empty">No notification events are available.</div>}</div></section></main>;
}
