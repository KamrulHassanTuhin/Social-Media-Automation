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
    event.preventDefault();
    setError(null);
    setLoading(true);
    const client = createSupabaseBrowserClient();
    if (!client) {
      setError("Supabase is not configured yet. Use the local dashboard while environment setup is pending.");
      setLoading(false);
      return;
    }
    const { error: authError } = await client.auth.signInWithPassword({ email, password });
    if (authError) {
      setError(authError.message);
      setLoading(false);
      return;
    }
    window.location.href = "/";
  };

  return <main className="auth-shell"><section className="auth-panel"><div className="auth-brand"><div className="brand-mark">A</div><div><strong>AXIS <span>OS</span></strong><small>Content operations</small></div></div><div className="auth-heading"><span className="auth-kicker"><Sparkles size={14} /> Internal workspace</span><h1>Welcome back</h1><p>Sign in to manage content, approvals, and publishing safely.</p></div><form className="auth-form" onSubmit={submit}><label>Email address<input value={email} onChange={(event) => setEmail(event.target.value)} type="email" required placeholder="you@axisconsulting.com" /></label><label>Password<input value={password} onChange={(event) => setPassword(event.target.value)} type="password" required placeholder="Your password" /></label>{error && <div className="auth-error"><LockKeyhole size={15} />{error}</div>}<button className="primary-button auth-submit" disabled={loading}>{loading ? "Signing in..." : "Sign in"}<ArrowRight size={16} /></button></form><button className="demo-login" onClick={() => { window.location.href = "/"; }}><CheckCircle2 size={15} /> Continue with local demo</button><p className="auth-note">Access is workspace-scoped. Your role controls generation, review, and publishing actions.</p></section><aside className="auth-aside"><div className="auth-aside-glow" /><span className="auth-aside-label">AXIS CONTENT OS</span><h2>One workflow from brief to publish.</h2><p>Keep ownership visible, enforce review gates, and make every publishing action traceable.</p><div className="auth-aside-list"><span><CheckCircle2 size={16} /> Approval before publishing</span><span><CheckCircle2 size={16} /> Retryable provider jobs</span><span><CheckCircle2 size={16} /> Workspace-level isolation</span></div></aside></main>;
}
