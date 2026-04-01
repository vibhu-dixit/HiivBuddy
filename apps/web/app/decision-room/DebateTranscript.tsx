"use client";

import type { RefObject } from "react";

import { DEBATE_AGENTS } from "./debateAgents";
import type { Turn } from "./debateTypes";
import type { StoredVoteTally } from "./debateHistory";

type VoteOpts = { id: string; title: string }[] | null;

type Report = {
  summary: string;
  ranked_options: { title: string; score: number; rationale: string }[];
  risks: string[];
  next_steps: string[];
} | null;

type Props = {
  error: string | null;
  currentAgent: { id: string; name: string; turn?: number } | null;
  running: boolean;
  turns: Turn[];
  voteOptions: VoteOpts;
  voteTally: StoredVoteTally | null;
  report: Report;
  runId: number | null;
  debateScrollRef: RefObject<HTMLDivElement | null>;
};

export function DebateTranscript({
  error,
  currentAgent,
  running,
  turns,
  voteOptions,
  voteTally,
  report,
  runId,
  debateScrollRef,
}: Props) {
  return (
    <div
      ref={debateScrollRef}
      className="min-h-0 flex-1 space-y-4 overflow-y-auto overscroll-contain p-3 sm:p-4 [scrollbar-gutter:stable]"
    >
      {error && (
        <p className="rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-200">
          {error}
        </p>
      )}

      {currentAgent && running && (
        <p className="text-xs text-[var(--muted)]">
          Now:{" "}
          {typeof currentAgent.turn === "number" && (
            <span className="text-[var(--foreground)]">Turn {currentAgent.turn} · </span>
          )}
          <span className="text-[var(--foreground)]">{currentAgent.name}</span>
          {currentAgent.id === "synthesizer" && " — writing final report…"}
        </p>
      )}

      {voteOptions && voteOptions.length > 0 && (
        <section className="rounded-lg border border-white/10 bg-[var(--card)] p-4">
          <h2 className="text-sm font-semibold text-[var(--foreground)]">Vote options</h2>
          <ul className="mt-2 flex flex-col gap-1 text-sm text-[var(--muted)]">
            {voteOptions.map((o) => (
              <li key={o.id}>
                <span className="font-mono text-[var(--accent)]">{o.id}</span>: {o.title}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="flex flex-col gap-4">
        <h2 className="text-sm font-medium text-[var(--muted)]">Debate</h2>
        <div className="flex flex-col gap-4">
          {turns.map((t, idx) => (
            <div key={`${t.turn}-${idx}-${t.agent}`}>
              {(idx === 0 || turns[idx - 1].turn !== t.turn) && (
                <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">
                  Turn {t.turn}
                </h3>
              )}
              <article
                className={
                  t.kind === "interjection"
                    ? "rounded-lg border border-amber-500/40 bg-amber-950/20 p-4"
                    : "rounded-lg border border-white/10 bg-[var(--card)] p-4"
                }
              >
                <h4 className="text-sm font-semibold text-[var(--accent)]">{t.name}</h4>
                {t.kind === "interjection" && t.targetName && (
                  <p className="mt-1 text-xs text-amber-200/90">
                    Interjects to <span className="font-medium">{t.targetName}</span>
                  </p>
                )}
                {t.reasoning && t.reasoning.length > 0 && (
                  <details className="mt-2 text-xs">
                    <summary className="cursor-pointer text-[var(--muted)] hover:text-[var(--foreground)]">
                      Model reasoning (thinking)
                    </summary>
                    <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap rounded-md border border-white/5 bg-black/20 p-2 text-[var(--muted)]">
                      {t.reasoning}
                    </pre>
                  </details>
                )}
                <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed">{t.text}</p>
              </article>
            </div>
          ))}
        </div>
      </section>

      {voteTally && (
        <section className="rounded-lg border border-white/10 bg-[var(--card)] p-4">
          <h2 className="text-sm font-semibold text-[var(--foreground)]">Vote tally</h2>
          <p className="mt-2 text-sm text-[var(--muted)]">
            Threshold: at least <strong className="text-[var(--foreground)]">{voteTally.threshold}</strong> of{" "}
            {DEBATE_AGENTS.length} on one option.
            {voteTally.consensus_reached ? (
              <span className="ml-2 text-green-400">Consensus reached.</span>
            ) : (
              <span className="ml-2 text-amber-400">No single-option majority at threshold.</span>
            )}
          </p>
          {voteTally.winning_option_id != null && voteTally.consensus_reached && (
            <p className="mt-1 text-sm">
              Winner:{" "}
              <span className="font-medium text-[var(--foreground)]">
                {voteTally.winning_title || `option ${voteTally.winning_option_id}`}
              </span>
            </p>
          )}
          <ul className="mt-3 flex flex-wrap gap-3 text-sm">
            {Object.entries(voteTally.tallies).map(([id, n]) => (
              <li
                key={id}
                className="rounded-md border border-white/10 px-3 py-1 font-mono text-[var(--muted)]"
              >
                {id}: {n}
              </li>
            ))}
          </ul>
          <ul className="mt-3 flex flex-col gap-2 border-t border-white/10 pt-3 text-sm text-[var(--muted)]">
            {voteTally.votes.map((v) => (
              <li key={v.agent_id}>
                <span className="text-[var(--foreground)]">{v.name}</span> →{" "}
                <span className="font-mono text-[var(--accent)]">{v.option_id}</span>
                {v.rationale ? ` — ${v.rationale}` : null}
              </li>
            ))}
          </ul>
        </section>
      )}

      {report && (
        <section className="rounded-lg border border-white/10 bg-[var(--card)] p-4">
          <h2 className="text-sm font-semibold text-[var(--foreground)]">Chief Synthesizer — report</h2>
          <p className="mt-3 text-sm leading-relaxed">{report.summary}</p>
          <h3 className="mt-4 text-xs font-medium uppercase tracking-wide text-[var(--muted)]">
            Ranked options
          </h3>
          <ul className="mt-2 flex flex-col gap-2">
            {report.ranked_options.map((o) => (
              <li key={o.title} className="rounded-md border border-white/5 p-3 text-sm">
                <div className="flex justify-between gap-2">
                  <span className="font-medium">{o.title}</span>
                  <span className="text-[var(--muted)]">{(o.score * 100).toFixed(0)}%</span>
                </div>
                <p className="mt-1 text-[var(--muted)]">{o.rationale}</p>
              </li>
            ))}
          </ul>
          <h3 className="mt-4 text-xs font-medium uppercase tracking-wide text-[var(--muted)]">
            Risks
          </h3>
          <ul className="mt-1 list-inside list-disc text-sm text-[var(--muted)]">
            {report.risks.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
          <h3 className="mt-4 text-xs font-medium uppercase tracking-wide text-[var(--muted)]">
            Next steps
          </h3>
          <ul className="mt-1 list-inside list-decimal text-sm">
            {report.next_steps.map((s) => (
              <li key={s}>{s}</li>
            ))}
          </ul>
        </section>
      )}

      {runId !== null && running === false && (
        <p className="text-xs text-[var(--muted)]">Saved as run #{runId}</p>
      )}
    </div>
  );
}
