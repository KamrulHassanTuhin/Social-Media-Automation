"use client";

import { Activity, ArrowLeft, CheckCircle2, Database, Gauge, Link2, Mail, RefreshCw, Sparkles, XCircle } from "lucide-react";
import Link from "next/link";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getHealthHistory, getProviderHealth } from "../lib/api";
import type { HealthRecord, ProviderHealth } from "../lib/types";

const demoProviders: ProviderHealth[] = [
  { provider: "supabase", status: "MOCK", probe: "PASS", responseTimeMs: 3, checkedAt: new Date().toISOString() },
  { provider: "openai", status: "MOCK", probe: "PASS", responseTimeMs: 4, checkedAt: new Date().toISOString() },
  { provider: "nuelink", status: "MOCK", probe: "PASS", responseTimeMs: 4, checkedAt: new Date().toISOString() },
  { provider: "slack", status: "MOCK", probe: "PASS", responseTimeMs: 2, checkedAt: new Date().toISOString() },
  { provider: "email", status: "MOCK", probe: "PASS", responseTimeMs: 2, checkedAt: new Date().toISOString() },
];

const demoHistory: HealthRecord[] = demoProviders.map((provider, index) => ({ id: `health_demo_${index}`, component: provider.provider, status: "PASS", responseTimeMs: provider.responseTimeMs, details: { status: provider.status }, checkedAt: provider.checkedAt }));

function providerIcon(provider: string) {
  if (provider === "openai") return <Sparkles size={16} />;
  if (provider === "nuelink") return <Link2 size={16} />;
  if (provider === "slack") return <Activity size={16} />;
  if (provider === "email") return <Mail size={16} />;
  return <Database size={16} />;
}

export function OperationsScreen() {
  const useApi = process.env.NEXT_PUBLIC_USE_API === "true";
  const queryClient = useQueryClient();
  const providersQuery = useQuery<ProviderHealth[]>({ queryKey: ["provider-health"], queryFn: () => getProviderHealth(true), enabled: useApi });
  const historyQuery = useQuery<HealthRecord[]>({ queryKey: ["health-history"], queryFn: () => getHealthHistory(50), enabled: useApi && providersQuery.isSuccess });
  const providers = useApi ? (providersQuery.data ?? []) : demoProviders;
  const history = useApi ? (historyQuery.data ?? []) : demoHistory;
  const passCount = providers.filter((provider) => provider.probe === "PASS").length;
  const responseTimes = providers.map((provider) => provider.responseTimeMs).filter((value): value is number => typeof value === "number");
  const averageResponse = responseTimes.length ? Math.round(responseTimes.reduce((total, value) => total + value, 0) / responseTimes.length) : 0;
  const refresh = async () => { await queryClient.invalidateQueries({ queryKey: ["provider-health"] }); await queryClient.invalidateQueries({ queryKey: ["health-history"] }); };

  return <main className="management-shell"><header className="management-header"><div><Link className="back-link" href="/"><ArrowLeft size={15} /> Dashboard</Link><span className="eyebrow">Nova Studio / Operations</span><h1>System health</h1><p>Probe provider connections, response time, and recent operational history.</p></div><button className="secondary-button" onClick={refresh}><RefreshCw size={14} /> Run health checks</button></header><section className="metrics-grid operations-metrics"><div className="metric-card"><div className="metric-icon green"><CheckCircle2 size={18} /></div><div className="metric-copy"><span>Passing providers</span><strong>{passCount}/{providers.length}</strong><small>latest probe result</small></div></div><div className="metric-card"><div className="metric-icon blue"><Gauge size={18} /></div><div className="metric-copy"><span>Average response</span><strong>{averageResponse}ms</strong><small>across configured checks</small></div></div><div className="metric-card"><div className="metric-icon purple"><Activity size={18} /></div><div className="metric-copy"><span>Recorded checks</span><strong>{history.length}</strong><small>{useApi ? "persisted health history" : "local demo history"}</small></div></div><div className="metric-card"><div className="metric-icon amber"><Database size={18} /></div><div className="metric-copy"><span>Storage mode</span><strong>{useApi ? "Remote" : "Local"}</strong><small>queue and media boundary</small></div></div></section><section className="management-card"><div className="management-card-header"><div><span className="card-kicker"><Activity size={14} /> Provider probes</span><h2>Connection status and latency</h2></div><span className="api-source-pill">{useApi ? (providersQuery.isLoading ? "Checking API" : "API connected") : "Demo data"}</span></div><div className="management-table">{providers.map((provider) => <div className="health-management-row" key={provider.provider}><div className="health-provider-icon">{providerIcon(provider.provider)}</div><div><strong>{provider.provider}</strong><span>{provider.status} · checked {new Date(provider.checkedAt).toLocaleTimeString()}</span></div><span className={`connection-status ${provider.probe === "PASS" ? "" : "warn"}`}><i />{provider.probe ?? "NOT RUN"}</span><b>{provider.responseTimeMs == null ? "—" : `${provider.responseTimeMs}ms`}</b></div>)}{providers.length === 0 && <div className="management-empty">No provider health data is available.</div>}</div></section><section className="management-card health-history-card"><div className="management-card-header"><div><span className="card-kicker"><Gauge size={14} /> Health history</span><h2>Recent checks</h2></div><span className="management-status">Last {history.length} records</span></div><div className="management-table">{history.slice(0, 20).map((record) => <div className="health-history-row" key={record.id}><div className={`health-history-icon ${record.status === "PASS" ? "pass" : "fail"}`}>{record.status === "PASS" ? <CheckCircle2 size={14} /> : <XCircle size={14} />}</div><strong>{record.component}</strong><span>{record.status}</span><b>{record.responseTimeMs == null ? "—" : `${record.responseTimeMs}ms`}</b><small>{new Date(record.checkedAt).toLocaleString()}</small></div>)}{history.length === 0 && <div className="management-empty">Run a health check to start recording operational history.</div>}</div></section></main>;
}
