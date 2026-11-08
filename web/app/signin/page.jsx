"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { describeError, signIn, signUp } from "@/lib/api";

export default function SignInPage() {
  const router = useRouter();
  const [mode, setMode] = useState("signin"); 
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const creating = mode === "signup";

  function switchMode(next) {
    setMode(next);
    setError(null);
  }

  async function onSubmit(e) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await (creating ? signUp : signIn)(email.trim(), password);
      router.push("/");
      router.refresh();
    } catch (err) {
      setError(describeError(err));
      setBusy(false);
    }
  }

  return (
    <main className="page narrow">
      <h1>{creating ? "Create your account" : "Welcome back"}</h1>
      <p className="lede">
        {creating
          ? "An account keeps your chats and memories across devices. Anything you've already shared in this browser comes with you."
          : "Sign in to pick up where you left off on any device."}
      </p>

      <div className="segmented" role="group" aria-label="Choose what to do">
        <button type="button" aria-pressed={!creating} onClick={() => switchMode("signin")}>
          Sign in
        </button>
        <button type="button" aria-pressed={creating} onClick={() => switchMode("signup")}>
          Create account
        </button>
      </div>

      <form className="authform" onSubmit={onSubmit}>
        <div className="field">
          <label htmlFor="email">Email</label>
          <input
            id="email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            maxLength={254}
            required
          />
        </div>
        <div className="field">
          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            autoComplete={creating ? "new-password" : "current-password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            minLength={creating ? 10 : undefined}
            maxLength={128}
            required
            aria-describedby={creating ? "password-hint" : undefined}
          />
          {creating && (
            <p id="password-hint" className="hint">
              At least 10 characters. A few random words work well.
            </p>
          )}
        </div>

        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}

        <button type="submit" className="primary" disabled={busy}>
          {busy ? "One moment…" : creating ? "Create account" : "Sign in"}
        </button>
      </form>

      <p className="fineprint">
        Passwords are stored as salted scrypt hashes, never in plain text. Forgotten passwords can&apos;t be reset yet, so
        keep yours somewhere safe.
      </p>
    </main>
  );
}