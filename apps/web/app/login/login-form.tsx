"use client";

import { ArrowRight, CheckCircle2, LockKeyhole, Sparkles } from "lucide-react";
import { FormEvent, useState } from "react";
import { createSupabaseBrowserClient } from "../../lib/supabase/browser";

export function LoginForm() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); setError(null); setLoading(true);
    const client = createSupabaseBrowserClient();
    if (!client) { setError("Supabase is not configured yet. Use the local dashboard while environment setup is pending."); setLoading(false); return; }
    const { error: authError } = await client.auth.signInWithPassword({ email, password });
    if (authError) { setError(authError.message); setLoading(false); return; }
    window.location.href = "/";
  };

  return <main className="auth-shell"><section className="auth-panel"><div className="auth-brand"><div className="brand-mark">N</div><div><strong>NOVA <span>STUDIO</span></strong><small>Content operations</small></div></div><div className="auth-heading"><span className="auth-kicker"><Sparkles size={14} /> Internal workspace</span><h1>Welcome back</h1><p>Bring every brief, approval, and publishing decision into one calm workspace.</p></div><form className="auth-form" onSubmit={submit}><label>Email address<input value={email} onChange={(event) => setEmail(event.target.value)} type="email" required placeholder="you@company.com" /></label><label>Password<input value={password} onChange={(event) => setPassword(event.target.value)} type="password" required placeholder="Your password" /></label>{error && <div className="auth-error"><LockKeyhole size={15} />{error}</div>}<button className="primary-button auth-submit" disabled={loading}>{loading ? "Signing in..." : "Sign in"}<ArrowRight size={16} /></button></form><button className="demo-login" onClick={() => { window.location.href = "/"; }}><CheckCircle2 size={15} /> Continue with local demo</button><p className="auth-note">Workspace access is role-aware. Every generation, review, and publishing action stays traceable.</p></section><aside className="auth-aside"><div className="auth-aside-glow" /><span className="auth-aside-label">NOVA CONTENT STUDIO</span><h2>Turn ideas into a steady publishing rhythm.</h2><p>Keep ownership visible, make review effortless, and move approved work forward with confidence.</p><div className="auth-aside-list"><span><CheckCircle2 size={16} /> Approval before publishing</span><span><CheckCircle2 size={16} /> Retryable provider jobs</span><span><CheckCircle2 size={16} /> Workspace-level isolation</span></div></aside></main>;
}
