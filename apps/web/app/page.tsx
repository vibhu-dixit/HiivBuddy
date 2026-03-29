import Link from "next/link";

export default function Home() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-8">
      <h1 className="text-2xl font-semibold tracking-tight">HiivBuddy</h1>
      <p className="mt-2 text-[var(--muted)]">
        Open a decision room to run a multi-agent debate.
      </p>
      <Link
        href="/decision-room"
        className="mt-6 rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white hover:opacity-90"
      >
        Decision Room
      </Link>
    </main>
  );
}
