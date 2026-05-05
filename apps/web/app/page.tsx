"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { useAuth } from "./auth/AuthProvider";

type Mode = "login" | "signup";

export default function Home() {
  const router = useRouter();
  const { user, loading, login, register, logout } = useAuth();
  const [mode, setMode] = useState<Mode>("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const signupPasswordsMatch =
    mode !== "signup" || (confirmPassword.length > 0 && password === confirmPassword);
  const canSubmitSignup =
    mode !== "signup" ||
    (username.trim().length >= 3 &&
      password.length >= 8 &&
      confirmPassword.length >= 8 &&
      password === confirmPassword);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (mode === "signup" && password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }
    setBusy(true);
    try {
      if (mode === "login") {
        await login(username, password);
      } else {
        await register(username, password);
      }
      router.push("/decision-room");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  if (loading) {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center p-8">
        <p className="text-sm text-[var(--muted)]">Loading…</p>
      </main>
    );
  }

  if (user) {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center gap-6 p-8">
        <div className="text-center">
          <h1 className="text-2xl font-semibold tracking-tight">HiivBuddy</h1>
          <p className="mt-2 text-[var(--muted)]">
            Signed in as <span className="text-[var(--foreground)]">{user.username}</span>
          </p>
        </div>
        <div className="flex flex-wrap items-center justify-center gap-3">
          <Link
            href="/decision-room"
            className="rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white hover:opacity-90"
          >
            Decision Room
          </Link>
          <button
            type="button"
            onClick={() => logout()}
            className="rounded-lg border border-white/15 px-4 py-2 text-sm font-medium text-[var(--foreground)] hover:bg-white/5"
          >
            Log out
          </button>
        </div>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-8 p-6">
      <div className="text-center">
        <h1 className="text-2xl font-semibold tracking-tight">HiivBuddy</h1>
        <p className="mt-2 max-w-md text-[var(--muted)]">
          Open a decision room to run a multi-agent debate. Sign in or create an account.
        </p>
      </div>

      <div className="w-full max-w-md overflow-hidden rounded-xl border border-white/10 bg-[var(--card)]/40 shadow-lg backdrop-blur-sm">
        <div className="flex border-b border-white/10">
          <button
            type="button"
            onClick={() => {
              setMode("login");
              setError(null);
            }}
            className={`flex-1 px-4 py-3 text-sm font-medium transition-colors ${
              mode === "login"
                ? "bg-[var(--accent)]/15 text-[var(--foreground)]"
                : "text-[var(--muted)] hover:bg-white/5 hover:text-[var(--foreground)]"
            }`}
          >
            Log in
          </button>
          <button
            type="button"
            onClick={() => {
              setMode("signup");
              setError(null);
            }}
            className={`flex-1 px-4 py-3 text-sm font-medium transition-colors ${
              mode === "signup"
                ? "bg-[var(--accent)]/15 text-[var(--foreground)]"
                : "text-[var(--muted)] hover:bg-white/5 hover:text-[var(--foreground)]"
            }`}
          >
            Sign up
          </button>
        </div>

        <div className="relative overflow-hidden">
          <div
            className="flex w-[200%] transition-transform duration-500 ease-out motion-reduce:transition-none"
            style={{
              transform: mode === "login" ? "translateX(0)" : "translateX(-50%)",
            }}
          >
            <section className="w-1/2 shrink-0 px-6 py-6">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
                Log in
              </h2>
              <form className="mt-4 flex flex-col gap-4" onSubmit={onSubmit}>
                <label className="flex flex-col gap-1.5">
                  <span className="text-xs text-[var(--muted)]">Username</span>
                  <input
                    name="username"
                    autoComplete="username"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    className="rounded-lg border border-white/15 bg-[var(--background)] px-3 py-2 text-sm outline-none ring-[var(--accent)] focus:ring-2"
                    required
                  />
                </label>
                <label className="flex flex-col gap-1.5">
                  <span className="text-xs text-[var(--muted)]">Password</span>
                  <input
                    name="password"
                    type="password"
                    autoComplete="current-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="rounded-lg border border-white/15 bg-[var(--background)] px-3 py-2 text-sm outline-none ring-[var(--accent)] focus:ring-2"
                    required
                  />
                </label>
                <button
                  type="submit"
                  disabled={busy || mode !== "login"}
                  className="mt-2 rounded-lg bg-[var(--accent)] px-4 py-2.5 text-sm font-medium text-white hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {busy && mode === "login" ? "Signing in…" : "Sign in"}
                </button>
              </form>
            </section>

            <section className="w-1/2 shrink-0 px-6 py-6">
              <h2 className="text-sm font-semibold uppercase tracking-wide text-[var(--muted)]">
                Create account
              </h2>
              <form className="mt-4 flex flex-col gap-4" onSubmit={onSubmit}>
                <label className="flex flex-col gap-1.5">
                  <span className="text-xs text-[var(--muted)]">Username</span>
                  <input
                    name="register-username"
                    autoComplete="username"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    className="rounded-lg border border-white/15 bg-[var(--background)] px-3 py-2 text-sm outline-none ring-[var(--accent)] focus:ring-2"
                    required
                    minLength={3}
                  />
                  <span className="text-[10px] text-[var(--muted)]">
                    3–32 characters: letters, numbers, underscore
                  </span>
                </label>
                <label className="flex flex-col gap-1.5">
                  <span className="text-xs text-[var(--muted)]">Password</span>
                  <input
                    name="register-password"
                    type="password"
                    autoComplete="new-password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="rounded-lg border border-white/15 bg-[var(--background)] px-3 py-2 text-sm outline-none ring-[var(--accent)] focus:ring-2"
                    required
                    minLength={8}
                  />
                </label>
                <label className="flex flex-col gap-1.5">
                  <span className="text-xs text-[var(--muted)]">Confirm password</span>
                  <input
                    name="confirm-password"
                    type="password"
                    autoComplete="new-password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    className="rounded-lg border border-white/15 bg-[var(--background)] px-3 py-2 text-sm outline-none ring-[var(--accent)] focus:ring-2"
                    required
                    minLength={8}
                  />
                  {mode === "signup" && confirmPassword.length > 0 && !signupPasswordsMatch && (
                    <span className="text-[10px] text-amber-200">Passwords must match</span>
                  )}
                </label>
                <button
                  type="submit"
                  disabled={busy || mode !== "signup" || !canSubmitSignup}
                  className="mt-2 rounded-lg bg-[var(--accent)] px-4 py-2.5 text-sm font-medium text-white hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  {busy && mode === "signup" ? "Creating account…" : "Create account"}
                </button>
              </form>
            </section>
          </div>
        </div>

        {error && (
          <p className="border-t border-white/10 bg-red-500/10 px-6 py-3 text-sm text-red-200">
            {error}
          </p>
        )}
      </div>
    </main>
  );
}
