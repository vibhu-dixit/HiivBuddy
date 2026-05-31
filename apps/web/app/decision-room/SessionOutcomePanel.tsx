"use client";

type Props = {
  status: "synthesizing" | "complete";
  highLevelResult: string;
  voteHint?: string | null;
  canDownload: boolean;
  onDownload: () => void;
};

export function SessionOutcomePanel({
  status,
  highLevelResult,
  voteHint,
  canDownload,
  onDownload,
}: Props) {
  return (
    <section
      className="rounded-xl border border-[var(--accent)]/35 bg-[var(--accent-muted)]/60 p-4"
      aria-live="polite"
    >
      <div className="flex items-center gap-2">
        <span
          className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[var(--accent)]/15 text-[var(--accent)]"
          aria-hidden
        >
          ✓
        </span>
        <h2 className="text-sm font-semibold text-[var(--foreground)]">Deliberation complete</h2>
      </div>

      {status === "synthesizing" && (
        <p className="mt-2 text-xs text-[var(--muted)]">Writing your decision brief…</p>
      )}

      {voteHint && status === "synthesizing" ? (
        <p className="mt-2 text-sm text-[var(--muted)]">{voteHint}</p>
      ) : null}

      <div className="mt-3 rounded-lg border border-[var(--border)] bg-[var(--card)] p-3">
        <p className="text-xs font-medium uppercase tracking-wide text-[var(--muted)]">
          High-level result
        </p>
        <p className="mt-2 text-sm leading-relaxed text-[var(--foreground)]">{highLevelResult}</p>
      </div>

      <button
        type="button"
        onClick={onDownload}
        disabled={!canDownload}
        title={
          canDownload
            ? "Download the full debate transcript and decision brief"
            : "Nothing to download yet"
        }
        className="mt-4 w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-4 py-2.5 text-sm font-medium text-[var(--foreground)] hover:bg-[var(--background)] disabled:cursor-not-allowed disabled:opacity-40 sm:w-auto"
      >
        Download Debate Transcript
      </button>
    </section>
  );
}
