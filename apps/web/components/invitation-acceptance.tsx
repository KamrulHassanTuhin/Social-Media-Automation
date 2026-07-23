"use client";

import { ArrowRight, CheckCircle2, LockKeyhole, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { acceptInvitation } from "../lib/api";

export function InvitationAcceptance() {
  const [workspaceId, setWorkspaceId] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "success" | "error">("idle");
  const [message, setMessage] = useState("");
  useEffect(() => { const value = new URLSearchParams(window.location.search).get("workspace_id"); if (value) setWorkspaceId(value); }, []);
  const submit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault(); setStatus("loading"); setMessage("");
    try { await acceptInvitation(workspaceId.trim()); setStatus("success"); setMessage("Your workspace access is active."); } catch (error) { setStatus("error"); setMessage(error instanceof Error ? error.message : "Unable to accept invitation."); }
  };
  return <main className="auth-shell"><section className="auth-panel"><Link className="back-link" href="/">← Back to AXIS OS</Link><div className="auth-brand"><div className="brand-mark">A</div><div><strong>AXIS <span>OS</span></strong><small>Content operations</small></div></div><div className="auth-heading"><span className="auth-kicker"><ShieldCheck size={14} /> Workspace invitation</span><h1>Join your workspace</h1><p>Accept the invitation to collaborate on content, approvals, and publishing.</p></div><form className="auth-form" onSubmit={submit}><label>Workspace ID<input required value={workspaceId} onChange={(event) => setWorkspaceId(event.target.value)} placeholder="workspace UUID" /></label>{message && <div className={status === "error" ? "auth-error" : "auth-success"}>{status === "error" ? <LockKeyhole size={15} /> : <CheckCircle2 size={15} />}{message}</div>}{status === "success" ? <Link className="primary-button auth-submit" href="/">Open dashboard <ArrowRight size={16} /></Link> : <button className="primary-button auth-submit" disabled={status === "loading"}>{status === "loading" ? "Accepting..." : "Accept invitation"}<ArrowRight size={16} /></button>}</form></section><aside className="auth-aside"><div className="auth-aside-glow" /><span className="auth-aside-label">AXIS CONTENT OS</span><h2>Join the workflow with clear ownership.</h2><p>Every workspace action is scoped, reviewable, and protected by role permissions.</p></aside></main>;
}
