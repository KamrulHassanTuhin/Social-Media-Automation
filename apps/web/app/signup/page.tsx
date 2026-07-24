"use client";

import { ArrowRight, CheckCircle2, LockKeyhole, Sparkles } from "lucide-react";
import { FormEvent, useState } from "react";
import { createSupabaseBrowserClient } from "../../lib/supabase/browser";

export default function SignupPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setMessage(null);
    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setLoading(true);
    const client = createSupabaseBrowserClient();
    if (!client) {
      setError("Supabase is not configured yet.");
      setLoading(false);
      return;
    }

    const { data, error: authError } = await client.auth.signUp({ email, password });
    if (authError) {
      setError(authError.message);
      setLoading(false);
      return;
    }

    if (data.session) {
      window.location.href = "/";
      return;
    }

    setMessage("Account created. Check your email to confirm the account, then sign in.");
    setLoading(false);
  };

  return <main className="auth-shell"><section className="auth-panel"><div className="auth-brand"><div className="brand-mark">N</div><div><strong>NOVA <span>STUDIO</span></strong><small>Content operations</small></div></div><div className="auth-heading"><span className="auth-kicker"><Sparkles size={14} /> New workspace member</span><h1>Create your account</h1><p>Set up your secure workspace access in a few seconds.</p></div><form className="auth-form" onSubmit={submit}><label>Email address<input value={email} onChange={(event) => setEmail(event.target.value)} type="email" required placeholder="you@company.com" /></label><label>Password<input value={password} onChange={(event) => setPassword(event.target.value)} type="password" minLength={6} required placeholder="At least 6 characters" /></label><label>Confirm password<input value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} type="password" minLength={6} required placeholder="Repeat your password" /></label>{error && <div className="auth-error"><LockKeyhole size={15} />{error}</div>}{message && <div className="auth-success"><CheckCircle2 size={15} />{message}</div>}<button className="primary-button auth-submit" disabled={loading}>{loading ? "Creating account..." : "Create account"}<ArrowRight size={16} /></button></form><p className="auth-note">Already have an account? <a href="/login">Sign in</a></p></section><aside className="auth-aside"><div className="auth-aside-glow" /><span className="auth-aside-label">NOVA CONTENT STUDIO</span><h2>Make every publishing decision visible.</h2><p>Join the workspace where briefs, reviews, approvals, and publishing stay connected.</p><div className="auth-aside-list"><span><CheckCircle2 size={16} /> Role-aware access</span><span><CheckCircle2 size={16} /> Secure Supabase Auth</span><span><CheckCircle2 size={16} /> Traceable workflows</span></div></aside></main>;
}
