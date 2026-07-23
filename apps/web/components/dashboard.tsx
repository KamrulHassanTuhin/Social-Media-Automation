"use client";

import {
  Activity,
  AlertTriangle,
  ArrowUpRight,
  Bell,
  Check,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  Clock3,
  Command,
  FileText,
  Filter,
  FolderKanban,
  Gauge,
  Globe2,
  Inbox,
  LayoutDashboard,
  Link2,
  ListFilter,
  Loader2,
  Menu,
  MoreHorizontal,
  Plus,
  Search,
  Settings2,
  ShieldCheck,
  Sparkles,
  Users,
  X,
} from "lucide-react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { approveContent, createContent, generateContent, listContent, listMembers, listProjects, listPublishingJobs, publishContent, retryPublishingJob, scheduleContent, uploadMedia } from "../lib/api";
import { activity, demoItems } from "../lib/demo-data";
import type { AutomationStatus, ContentItem, Priority, PublishingJob, WorkspaceMember, WorkspaceProject } from "../lib/types";

const statusLabels: Record<AutomationStatus, string> = {
  NOT_STARTED: "Not started",
  QUEUED: "Queued",
  GENERATING: "Generating",
  NEEDS_REVIEW: "Needs review",
  CHANGES_REQUESTED: "Changes requested",
  APPROVED: "Approved",
  READY_TO_PUBLISH: "Ready to publish",
  PUBLISHING: "Publishing",
  PARTIALLY_PUBLISHED: "Partially published",
  PUBLISHED: "Published",
  FAILED: "Failed",
  CANCELED: "Canceled",
};

const navItems = [
  { label: "Dashboard", icon: LayoutDashboard, active: true },
  { label: "Content", icon: FileText, count: "24" },
  { label: "Approvals", icon: ShieldCheck, count: "6" },
  { label: "Publishing", icon: Globe2, count: "3" },
  { label: "Media library", icon: FolderKanban },
];

const secondaryNav = [
  { label: "Activity", icon: Activity },
  { label: "Errors", icon: AlertTriangle, count: "2", danger: true },
  { label: "Operations", icon: Gauge },
  { label: "Projects", icon: Command },
  { label: "Team", icon: Users },
];

const statusTone = (status: AutomationStatus) => {
  if (status === "APPROVED" || status === "PUBLISHED" || status === "READY_TO_PUBLISH") return "success";
  if (status === "FAILED" || status === "CHANGES_REQUESTED") return "danger";
  if (status === "NEEDS_REVIEW" || status === "GENERATING" || status === "PUBLISHING") return "warning";
  return "neutral";
};

const priorityTone = (priority: Priority) => {
  if (priority === "URGENT") return "urgent";
  if (priority === "HIGH") return "high";
  return "normal";
};

function StatusBadge({ status }: { status: AutomationStatus }) {
  return <span className={`status-badge ${statusTone(status)}`}><span className="status-dot" />{statusLabels[status]}</span>;
}

function Progress({ value }: { value: number }) {
  return <div className="progress-wrap"><div className="progress-track"><div className="progress-bar" style={{ width: `${value}%` }} /></div><span>{value}%</span></div>;
}

export function Dashboard() {
  const [items, setItems] = useState<ContentItem[]>(demoItems);
  const [query, setQuery] = useState("");
  const [project, setProject] = useState("All projects");
  const [status, setStatus] = useState("All statuses");
  const [selected, setSelected] = useState<ContentItem | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [showFilters, setShowFilters] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [mobileNav, setMobileNav] = useState(false);
  const useApi = process.env.NEXT_PUBLIC_USE_API === "true";
  const defaultProjectId = process.env.NEXT_PUBLIC_DEFAULT_PROJECT_ID;
  const defaultWorkspaceId = process.env.NEXT_PUBLIC_DEFAULT_WORKSPACE_ID;
  const queryClient = useQueryClient();
  const contentQuery = useQuery({ queryKey: ["content", defaultWorkspaceId, query], queryFn: () => listContent({ search: query.length >= 2 ? query : undefined }), enabled: useApi });
  const projectsQuery = useQuery<WorkspaceProject[]>({ queryKey: ["workspace-projects", defaultWorkspaceId], queryFn: () => listProjects(), enabled: useApi });
  const membersQuery = useQuery<WorkspaceMember[]>({ queryKey: ["workspace-members", defaultWorkspaceId], queryFn: () => listMembers(), enabled: useApi });
  const [projects, setProjects] = useState<WorkspaceProject[]>([]);
  const [members, setMembers] = useState<WorkspaceMember[]>([]);

  useEffect(() => {
    if (contentQuery.data) setItems(contentQuery.data);
    if (contentQuery.error) setToast("API unavailable; showing local demo data");
  }, [contentQuery.data, contentQuery.error]);

  useEffect(() => { if (projectsQuery.data) setProjects(projectsQuery.data); }, [projectsQuery.data]);
  useEffect(() => { if (membersQuery.data) setMembers(membersQuery.data); }, [membersQuery.data]);

  const filteredItems = useMemo(() => items.filter((item) => {
    const matchesQuery = !query || `${item.topic} ${item.project} ${item.writer}`.toLowerCase().includes(query.toLowerCase());
    const matchesProject = project === "All projects" || item.project === project;
    const matchesStatus = status === "All statuses" || statusLabels[item.automationStatus] === status;
    return matchesQuery && matchesProject && matchesStatus;
  }), [items, project, query, status]);

  const flash = (message: string) => {
    setToast(message);
    window.setTimeout(() => setToast(null), 2800);
  };

  const updateItem = (id: string, patch: Partial<ContentItem>, message: string) => {
    setItems((current) => current.map((item) => item.id === id ? { ...item, ...patch, updatedAt: "Just now" } : item));
    if (selected?.id === id) setSelected((current) => current ? { ...current, ...patch, updatedAt: "Just now" } : current);
    flash(message);
  };

  const syncContentCache = async () => {
    const refreshed = await queryClient.fetchQuery({ queryKey: ["content", defaultWorkspaceId, query], queryFn: () => listContent({ search: query.length >= 2 ? query : undefined }) });
    setItems(refreshed);
    return refreshed;
  };

  const generateCopy = async (item: ContentItem) => {
    if (useApi) {
      updateItem(item.id, { automationStatus: "QUEUED" }, "Generation job queued");
      try {
        await generateContent(item.id);
        const refreshed = await syncContentCache();
        setSelected((current) => current?.id === item.id ? refreshed.find((next) => next.id === item.id) ?? current : current);
      } catch (error) {
        flash(error instanceof Error ? error.message : "Unable to generate copy");
      }
      return;
    }
    updateItem(item.id, { automationStatus: "GENERATING" }, "Generation job queued");
    window.setTimeout(() => updateItem(item.id, { automationStatus: "NEEDS_REVIEW", channels: 5 }, "Social copies are ready for review"), 900);
  };

  const scheduleItem = async (item: ContentItem, scheduledFor: string) => {
    if (useApi) {
      try {
        await scheduleContent(item.id, new Date(scheduledFor).toISOString());
      } catch {
        flash("Unable to schedule content");
        return;
      }
    }
    updateItem(item.id, { automationStatus: "READY_TO_PUBLISH", plannedDate: new Date(scheduledFor).toLocaleString() }, "Content scheduled for publishing");
  };

  const approveItem = async (item: ContentItem) => {
    if (useApi) {
      try { await approveContent(item.id); const refreshed = await syncContentCache(); setSelected(refreshed.find((next) => next.id === item.id) ?? item); flash("Content approved"); } catch (error) { flash(error instanceof Error ? error.message : "Unable to approve content"); }
      return;
    }
    updateItem(item.id, { automationStatus: "APPROVED" }, "Content approved");
  };

  const publishItem = async (item: ContentItem) => {
    if (useApi) {
      try { await publishContent(item.id); const refreshed = await syncContentCache(); setSelected(refreshed.find((next) => next.id === item.id) ?? item); flash("Publishing jobs queued"); } catch (error) { flash(error instanceof Error ? error.message : "Unable to publish content"); }
      return;
    }
    updateItem(item.id, { automationStatus: "PUBLISHING" }, "Publishing jobs queued");
  };

  const retryItem = async (item: ContentItem) => {
    if (useApi) {
      try {
        const jobs = await listPublishingJobs(item.id);
        const failed = jobs.filter((job) => job.status === "FAILED");
        await Promise.all(failed.map((job) => retryPublishingJob(job.id)));
        updateItem(item.id, { automationStatus: failed.length ? "QUEUED" : item.automationStatus }, failed.length ? "Failed jobs queued for retry" : "No failed publishing jobs found");
      } catch (error) { flash(error instanceof Error ? error.message : "Unable to retry publishing jobs"); }
      return;
    }
    updateItem(item.id, { automationStatus: "QUEUED" }, "Failed job queued for retry");
  };

  const attachMedia = async (item: ContentItem, file: File) => {
    if (!useApi) { updateItem(item.id, { media: true }, "Media attached in demo mode"); return; }
    try {
      await uploadMedia(file, item.projectId ?? defaultProjectId ?? item.project, item.id);
      updateItem(item.id, { media: true }, "Media uploaded");
    } catch (error) { flash(error instanceof Error ? error.message : "Unable to upload media"); }
  };

  const createItem = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const topic = String(form.get("topic") || "New content topic");
    const projectName = String(form.get("project") || "AXIS Consulting");
    const selectedProject = projects.find((candidate) => candidate.name === projectName);
    if (useApi) {
      try {
        const item = await createContent(topic, selectedProject?.id ?? defaultProjectId ?? projectName);
        setItems((current) => [item, ...current]);
        setShowCreate(false);
        setSelected(item);
        flash("Content item created");
      } catch (error) { flash(error instanceof Error ? error.message : "Unable to create content"); }
      return;
    }
    const item: ContentItem = {
      id: `cnt_${Date.now()}`,
      topic,
      project: projectName,
      group: "August 2026",
      funnel: "TOFU",
      briefStatus: "NOT_STARTED",
      writer: "Unassigned",
      publisher: "Unassigned",
      plannedDate: "Aug 18, 2026",
      automationStatus: "NOT_STARTED",
      priority: "NORMAL",
      progress: 0,
      channels: 0,
      media: false,
      updatedAt: "Just now",
      briefText: "Add a working brief to unlock AI copy generation.",
      copies: {},
    };
    setItems((current) => [item, ...current]);
    setShowCreate(false);
    setSelected(item);
    flash("Content item created");
  };

  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobileNav ? "sidebar-open" : ""}`}>
        <div className="brand-lockup"><div className="brand-mark">A</div><div><div className="brand-name">AXIS <span>OS</span></div><div className="brand-subtitle">Content operations</div></div><button className="mobile-close" onClick={() => setMobileNav(false)}><X size={18} /></button></div>
        <div className="workspace-switcher"><div className="workspace-avatar">AC</div><div className="workspace-copy"><strong>AXIS Consulting</strong><span>{useApi ? `${members.filter((member) => member.status === "ACTIVE").length} active members` : "Internal workspace"}</span></div><ChevronDown size={15} className="muted-icon" /></div>
        <nav className="nav-group" aria-label="Primary navigation">
          <div className="nav-label">Workspace</div>
          {navItems.map(({ label, icon: Icon, active, count }) => <button key={label} className={`nav-item ${active ? "active" : ""}`} onClick={() => flash(`${label} view is coming next`)}><Icon size={17} /><span>{label}</span>{count && <span className="nav-count">{count}</span>}</button>)}
          <div className="nav-label nav-label-spaced">Manage</div>
          {secondaryNav.map(({ label, icon: Icon, count, danger }) => <button key={label} className="nav-item" onClick={() => { if (label === "Projects" || label === "Team" || label === "Operations") { window.location.href = label === "Projects" ? "/projects" : label === "Team" ? "/team" : "/operations"; } else { flash(`${label} view is coming next`); } }}><Icon size={17} /><span>{label}</span>{count && <span className={`nav-count ${danger ? "danger-count" : ""}`}>{count}</span>}</button>)}
        </nav>
        <div className="sidebar-bottom"><div className="health-card"><div className="health-icon"><Gauge size={17} /></div><div><strong>System health</strong><span><i className="health-dot" /> All systems operational</span></div><ChevronRight size={16} /></div><button className="nav-item" onClick={() => flash("Settings view is coming next")}><Settings2 size={17} /><span>Settings</span></button><div className="profile"><div className="profile-avatar">NR</div><div className="profile-copy"><strong>Nadia Rahman</strong><span>Workspace admin</span></div><MoreHorizontal size={17} className="muted-icon" /></div></div>
      </aside>

      <main className="main-content">
        <header className="topbar"><button className="mobile-menu" onClick={() => setMobileNav(true)}><Menu size={20} /></button><div className="breadcrumb"><span>Workspace</span><ChevronRight size={14} /><strong>Dashboard</strong></div><div className="topbar-actions"><button className="icon-button search-shortcut" onClick={() => document.getElementById("global-search")?.focus()}><Search size={17} /><span>Search</span><kbd>⌘ K</kbd></button><button className="icon-button" aria-label="Help" onClick={() => flash("Help center will be connected here")}><CircleHelp size={18} /></button><button className="icon-button notification-button" aria-label="Notifications" onClick={() => flash("You have 6 pending notifications")}><Bell size={18} /><i /></button><div className="top-avatar">NR</div></div></header>

        <div className="page-body">
          <div className="page-heading"><div><div className="eyebrow">Thursday, July 23, 2026 <span className="eyebrow-dot" /> Asia/Dhaka</div><h1>Good morning, Nadia <span className="wave">✦</span></h1><p>Here is what is moving across your content operation today.</p></div><button className="primary-button" onClick={() => setShowCreate(true)}><Plus size={17} /> New content</button></div>

          <section className="metrics-grid" aria-label="Content summary">
            <MetricCard label="Total content" value="248" delta="12.4%" detail="vs. last month" icon={FileText} tone="blue" />
            <MetricCard label="Needs review" value="06" delta="4 waiting" detail="across 3 projects" icon={ShieldCheck} tone="amber" />
            <MetricCard label="Ready to publish" value="11" delta="3 today" detail="next 7 days" icon={Globe2} tone="purple" />
            <MetricCard label="Failed jobs" value="02" delta="Needs attention" detail="last 24 hours" icon={AlertTriangle} tone="red" alert />
          </section>

          <section className="insight-grid"><div className="insight-card primary-insight"><div className="insight-header"><div><span className="card-kicker"><Sparkles size={14} /> This week</span><h2>Keep the workflow moving</h2></div><button className="quiet-button" onClick={() => flash("Weekly report export queued")}>View report <ArrowUpRight size={15} /></button></div><div className="insight-content"><div><strong>74%</strong><span>of scheduled content is on track</span></div><div className="mini-bars"><span style={{ height: "42%" }} /><span style={{ height: "55%" }} /><span style={{ height: "49%" }} /><span style={{ height: "74%" }} /><span style={{ height: "64%" }} /><span style={{ height: "88%" }} /><span style={{ height: "76%" }} /></div></div><div className="insight-footer"><span><i className="legend-dot blue-dot" /> Published <b>32</b></span><span><i className="legend-dot purple-dot" /> In review <b>06</b></span><span><i className="legend-dot gray-dot" /> In progress <b>18</b></span></div></div><div className="insight-card approval-card"><div className="insight-header"><div><span className="card-kicker"><Clock3 size={14} /> Attention needed</span><h2>Approval queue</h2></div><button className="link-button" onClick={() => setStatus("Needs review")}>View all <ChevronRight size={15} /></button></div><div className="approval-list"><ApprovalRow title="Search intent content engine" project="AXIS Consulting" who="NR" color="orange" onClick={() => setSelected(items[0])} /><ApprovalRow title="Content refresh playbook" project="Growth Lab" who="FC" color="green" onClick={() => setSelected(items[3])} /><ApprovalRow title="Publishing without approval" project="AXIS Consulting" who="MP" color="purple" onClick={() => setSelected(items[2])} /></div></div></section>

          <section className="content-section"><div className="section-heading"><div><div className="section-title-row"><h2>Content overview</h2><span className="count-pill">{filteredItems.length} items</span>{useApi && <span className="api-source-pill">{contentQuery.isLoading ? "Loading API" : "API connected"}</span>}</div><p>Track planning, copy review, and publishing from one source of truth.</p></div><button className="secondary-button" onClick={() => flash("Export job queued")}>Export <ArrowUpRight size={15} /></button></div><div className="table-toolbar"><div className="search-input"><Search size={17} /><input id="global-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search topics, projects, people..." /><kbd>⌘ K</kbd></div><div className="toolbar-actions"><select value={project} onChange={(event) => setProject(event.target.value)} aria-label="Filter by project"><option>All projects</option>{(projects.length ? projects : [{ id: "project_demo", name: "AXIS Consulting" }, { id: "project_growth", name: "Growth Lab" }]).map((option) => <option key={option.id}>{option.name}</option>)}</select><select value={status} onChange={(event) => setStatus(event.target.value)} aria-label="Filter by status"><option>All statuses</option>{Object.values(statusLabels).map((label) => <option key={label}>{label}</option>)}</select><button className={`filter-button ${showFilters ? "selected" : ""}`} onClick={() => setShowFilters((value) => !value)}><ListFilter size={16} /> Filters <span>3</span></button></div></div>{showFilters && <div className="filter-strip"><span><Filter size={14} /> Active filters</span><button onClick={() => { setProject("All projects"); setStatus("All statuses"); }} className="clear-filter">Clear all</button><button onClick={() => setStatus("Needs review")} className="filter-chip">Needs review <X size={13} /></button><button onClick={() => setProject("AXIS Consulting")} className="filter-chip">AXIS Consulting <X size={13} /></button><button onClick={() => flash("More filters are ready for the API connection")} className="filter-chip muted-chip">+ Add filter</button></div>}<div className="table-card"><div className="table-scroll"><table><thead><tr><th className="check-cell"><input type="checkbox" aria-label="Select all content" /></th><th>Content topic</th><th>Project</th><th>Owner</th><th>Planned date</th><th>Progress</th><th>Status</th><th>Priority</th><th className="action-cell" /></tr></thead><tbody>{filteredItems.map((item) => <tr key={item.id} onClick={() => setSelected(item)}><td className="check-cell" onClick={(event) => event.stopPropagation()}><input type="checkbox" aria-label={`Select ${item.topic}`} /></td><td><div className="topic-cell"><div className={`topic-icon ${item.automationStatus === "FAILED" ? "failed-icon" : ""}`}>{item.automationStatus === "FAILED" ? <AlertTriangle size={15} /> : <FileText size={15} />}</div><div><strong>{item.topic}</strong><span>{item.group} <i /> {item.funnel}</span></div></div></td><td><div className="project-cell"><span className={`project-dot ${item.project === "Growth Lab" ? "teal" : "orange"}`} />{item.project}</div></td><td><div className="owner-cell"><span className="mini-avatar">{item.writer === "—" ? "—" : item.writer.split(" ").map((part) => part[0]).join("")}</span>{item.writer === "—" ? <span className="muted-text">Unassigned</span> : item.writer}</div></td><td><span className="date-cell">{item.plannedDate}</span></td><td><Progress value={item.progress} /></td><td><StatusBadge status={item.automationStatus} /></td><td><span className={`priority ${priorityTone(item.priority)}`}><i />{item.priority.charAt(0) + item.priority.slice(1).toLowerCase()}</span></td><td className="action-cell"><button className="row-action" onClick={(event) => { event.stopPropagation(); setSelected(item); }} aria-label={`Open ${item.topic}`}><MoreHorizontal size={17} /></button></td></tr>)}</tbody></table>{filteredItems.length === 0 && <div className="empty-state"><Search size={22} /><strong>No content found</strong><span>Try changing your search or filters.</span></div>}</div><div className="table-footer"><span>Showing <strong>{filteredItems.length}</strong> of <strong>{items.length}</strong> content items</span><div className="pagination"><button disabled><ChevronRight size={15} className="rotate" /></button><button className="current-page">1</button><button>2</button><button>3</button><button><ChevronRight size={15} /></button></div></div></div></section>

          <section className="bottom-grid"><div className="activity-card"><div className="section-heading compact"><div><h2>Recent activity</h2><p>Latest changes across your workspace.</p></div><button className="link-button" onClick={() => flash("Activity log view is coming next")}>View activity <ChevronRight size={15} /></button></div><div className="activity-list">{activity.map((entry) => <div className="activity-row" key={`${entry.name}-${entry.time}`}><div className={`activity-avatar ${entry.tone}`}>{entry.name === "System" ? <Activity size={15} /> : entry.name.split(" ").map((part) => part[0]).join("")}</div><div className="activity-copy"><span><strong>{entry.name}</strong> {entry.action}</span><b>{entry.target}</b><small>{entry.time}</small></div></div>)}</div></div><div className="health-panel"><div className="section-heading compact"><div><h2>Integration health</h2><p>Provider connections and queue status.</p></div><button className="icon-button small" onClick={() => flash("Health checks refreshed")}><Activity size={16} /></button></div><HealthRow name="Supabase" detail="Database & auth" status="Connected" icon="database" /><HealthRow name="OpenAI" detail="AI generation" status="Connected" icon="sparkles" /><HealthRow name="Nuelink" detail="Publishing provider" status="Needs setup" icon="link" warn /><HealthRow name="Slack" detail="Notifications" status="Connected" icon="slack" /></div></section>
        </div>
      </main>

      {selected && <DetailDrawer item={selected} useApi={useApi} onClose={() => setSelected(null)} onGenerate={() => generateCopy(selected)} onApprove={() => approveItem(selected)} onPublish={() => publishItem(selected)} onSchedule={(scheduledFor) => scheduleItem(selected, scheduledFor)} onRetry={() => retryItem(selected)} onMediaUpload={(file) => attachMedia(selected, file)} />}
      {showCreate && <CreateModal projects={projects} onClose={() => setShowCreate(false)} onSubmit={createItem} />}
      {toast && <div className="toast"><Check size={16} />{toast}</div>}
    </div>
  );
}

function MetricCard({ label, value, delta, detail, icon: Icon, tone, alert }: { label: string; value: string; delta: string; detail: string; icon: typeof FileText; tone: string; alert?: boolean }) {
  return <div className={`metric-card ${alert ? "metric-alert" : ""}`}><div className={`metric-icon ${tone}`}><Icon size={18} /></div><div className="metric-copy"><span>{label}</span><strong>{value}</strong><small><b>{delta}</b> {detail}</small></div><ArrowUpRight size={17} className="metric-arrow" /></div>;
}

function ApprovalRow({ title, project, who, color, onClick }: { title: string; project: string; who: string; color: string; onClick: () => void }) {
  return <button className="approval-row" onClick={onClick}><div className={`approval-avatar ${color}`}>{who}</div><div><strong>{title}</strong><span>{project}</span></div><ChevronRight size={16} /></button>;
}

function HealthRow({ name, detail, status, icon, warn }: { name: string; detail: string; status: string; icon: string; warn?: boolean }) {
  return <div className="health-row"><div className={`health-provider-icon ${icon}`}>{icon === "sparkles" ? <Sparkles size={15} /> : icon === "link" ? <Link2 size={15} /> : icon === "slack" ? <Command size={15} /> : <FolderKanban size={15} />}</div><div><strong>{name}</strong><span>{detail}</span></div><span className={`connection-status ${warn ? "warn" : ""}`}><i />{status}</span></div>;
}

function DetailDrawer({ item, useApi, onClose, onGenerate, onApprove, onPublish, onSchedule, onRetry: retryCallback, onMediaUpload }: { item: ContentItem; useApi: boolean; onClose: () => void; onGenerate: () => void; onApprove: () => void; onPublish: () => void; onSchedule: (scheduledFor: string) => void; onRetry: () => Promise<void> | void; onMediaUpload: (file: File) => Promise<void> | void }) {
  const isFailed = item.automationStatus === "FAILED";
  const [jobs, setJobs] = useState<PublishingJob[]>([]);
  const [uploading, setUploading] = useState(false);
  useEffect(() => {
    if (!useApi) return;
    let active = true;
    listPublishingJobs(item.id).then((nextJobs) => { if (active) setJobs(nextJobs); }).catch(() => { if (active) setJobs([]); });
    return () => { active = false; };
  }, [item.id, useApi]);
  const handleRetry = async () => { await retryCallback(); if (useApi) setJobs(await listPublishingJobs(item.id)); };
  const onRetry = handleRetry;
  const handleMediaChange = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try { await onMediaUpload(file); } finally { setUploading(false); event.target.value = ""; }
  };
  const [scheduledFor, setScheduledFor] = useState("");
  const canSchedule = item.automationStatus === "APPROVED" || item.automationStatus === "READY_TO_PUBLISH";
  const submitSchedule = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (scheduledFor) onSchedule(scheduledFor);
  };
  return <div className="drawer-backdrop" onClick={onClose}><aside className="detail-drawer" onClick={(event) => event.stopPropagation()}><div className="drawer-header"><div><span className="drawer-eyebrow">Content item / {item.id}</span><h2>{item.topic}</h2></div><button className="icon-button" onClick={onClose}><X size={18} /></button></div><div className="drawer-status-row"><StatusBadge status={item.automationStatus} /><span className={`priority ${priorityTone(item.priority)}`}><i />{item.priority.toLowerCase()}</span><span className="drawer-updated">Updated {item.updatedAt}</span></div><div className="drawer-scroll"><div className="drawer-section"><h3>Ownership</h3><div className="detail-grid"><Detail label="Project" value={item.project} /><Detail label="Writer" value={item.writer} /><Detail label="Publisher" value={item.publisher} /><Detail label="Planned publish" value={item.plannedDate} /></div></div><div className="drawer-section"><div className="section-title-row"><h3>Brief</h3><span className={`brief-state ${item.briefStatus === "BRIEF_READY" ? "ready" : ""}`}>{item.briefStatus.replaceAll("_", " ")}</span></div><p className="brief-copy">{item.briefText}</p>{item.briefStatus === "BRIEF_READY" && <button className="text-action" onClick={onGenerate}><Sparkles size={14} /> {item.channels ? "Regenerate social copy" : "Generate social copy"}</button>}</div><div className="drawer-section"><div className="section-title-row"><h3>Channel copy</h3><span className="copy-count">{item.channels}/5 channels</span></div>{Object.entries(item.copies).length > 0 ? <div className="copy-list">{Object.entries(item.copies).map(([channel, copy]) => <div className="copy-preview" key={channel}><div><strong>{channel}</strong><button onClick={() => { navigator.clipboard?.writeText(copy); }} aria-label={`Copy ${channel} text`}><Link2 size={13} /></button></div><p>{copy}</p></div>)}</div> : <div className="empty-copy"><Sparkles size={17} /><span>Generate channel-specific copy after the brief is ready.</span></div>}</div><div className="drawer-section"><h3>Publishing readiness</h3><div className="readiness-list"><ReadinessRow label="Approval gate" done={item.automationStatus === "APPROVED" || item.automationStatus === "READY_TO_PUBLISH" || item.automationStatus === "PUBLISHED"} /><ReadinessRow label="Live URL" done={Boolean(item.liveUrl)} /><ReadinessRow label="Media attached" done={item.media} /><ReadinessRow label="Publisher assigned" done={item.publisher !== "—" && item.publisher !== "Unassigned"} /></div></div><div className="drawer-section media-section"><div className="section-title-row"><h3>Media</h3><span className={`brief-state ${item.media ? "ready" : ""}`}>{item.media ? "Attached" : "Missing"}</span></div><label className="media-upload"><input type="file" accept="image/jpeg,image/png,image/gif,image/webp" onChange={handleMediaChange} disabled={uploading} /><span>{uploading ? "Uploading media..." : "Attach image"}</span></label></div>{jobs.length > 0 && <div className="drawer-section"><div className="section-title-row"><h3>Publishing jobs</h3><span className="copy-count">{jobs.length}</span></div><div className="job-list">{jobs.map((job) => <div className="job-row" key={job.id}><div><strong>{job.channel}</strong><span>{job.status}{job.scheduledFor ? ` · ${new Date(job.scheduledFor).toLocaleString()}` : ""}</span>{job.lastError && <small>{job.lastError}</small>}</div>{job.externalPostUrl && <a href={job.externalPostUrl} target="_blank" rel="noreferrer">Open</a>}</div>)}</div></div>}{canSchedule && <div className="drawer-section schedule-section"><h3>Schedule publishing</h3><form onSubmit={submitSchedule}><label htmlFor="scheduled-for">Publish at</label><div className="schedule-controls"><input id="scheduled-for" type="datetime-local" value={scheduledFor} onChange={(event) => setScheduledFor(event.target.value)} required /><button className="secondary-button" type="submit"><Clock3 size={15} /> Schedule</button></div></form></div>}</div><div className="drawer-footer">{isFailed ? <button className="secondary-button full-button" onClick={onRetry}><Loader2 size={16} /> Retry failed job</button> : item.automationStatus === "NEEDS_REVIEW" ? <button className="primary-button full-button" onClick={onApprove}><Check size={16} /> Approve copy</button> : item.automationStatus === "APPROVED" || item.automationStatus === "READY_TO_PUBLISH" ? <button className="primary-button full-button" onClick={onPublish}><Globe2 size={16} /> Publish approved content</button> : <button className="secondary-button full-button" onClick={onClose}>Close details</button>}</div></aside></div>;
}

function Detail({ label, value }: { label: string; value: string }) { return <div className="detail-field"><span>{label}</span><strong>{value}</strong></div>; }
function ReadinessRow({ label, done }: { label: string; done: boolean }) { return <div className="readiness-row"><span className={done ? "done" : "pending"}>{done ? <Check size={13} /> : <Clock3 size={13} />}</span><span>{label}</span><b>{done ? "Ready" : "Missing"}</b></div>; }

function CreateModal({ projects, onClose, onSubmit }: { projects: WorkspaceProject[]; onClose: () => void; onSubmit: (event: React.FormEvent<HTMLFormElement>) => void }) {
  const options = projects.length ? projects : [{ id: "project_demo", name: "AXIS Consulting" }, { id: "project_growth", name: "Growth Lab" }];
  return <div className="modal-backdrop" onClick={onClose}><div className="create-modal" onClick={(event) => event.stopPropagation()}><div className="modal-header"><div><span className="drawer-eyebrow">New workflow item</span><h2>Create content</h2><p>Start with a topic and assign it to a project. You can add the brief later.</p></div><button className="icon-button" onClick={onClose}><X size={18} /></button></div><form onSubmit={onSubmit}><label>Content topic<input name="topic" required minLength={3} maxLength={300} placeholder="e.g. How to build a safer content workflow" /></label><label>Project<select name="project" defaultValue={options[0].name}>{options.map((option) => <option key={option.id}>{option.name}</option>)}</select></label><div className="form-grid"><label>Funnel stage<select name="funnel" defaultValue="TOFU"><option>TOFU</option><option>MOFU</option><option>BOFU</option></select></label><label>Priority<select name="priority" defaultValue="NORMAL"><option>LOW</option><option>NORMAL</option><option>HIGH</option><option>URGENT</option></select></label></div><div className="modal-footer"><button type="button" className="secondary-button" onClick={onClose}>Cancel</button><button type="submit" className="primary-button"><Plus size={16} /> Create content</button></div></form></div></div>;
}
