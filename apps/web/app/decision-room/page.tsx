"use client";

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";

import { ChamberSeats, DEBATE_AGENTS } from "./ChamberSeats";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

type SessionStart = {
  type: "session_start";
  session_duration_sec: number;
  debate_budget_sec: number;
  synth_reserve_sec: number;
};
type AgentStart = { type: "agent_start"; agent: string; name: string; turn?: number };
type Token = { type: "token"; agent: string; text: string };
type ReasoningToken = { type: "reasoning_token"; agent: string; text: string };
type AgentEnd = { type: "agent_end"; agent: string; full_text: string; turn?: number };
type InterjectionEvent = {
  type: "interjection";
  agent: string;
  name: string;
  target_agent: string;
  target_name: string;
  turn: number;
  text: string;
};
type VotePhaseStart = { type: "vote_phase_start" };
type VoteOptions = {
  type: "vote_options";
  options: { id: string; title: string }[];
};
type VoteCast = {
  type: "vote_cast";
  agent: string;
  name: string;
  option_id: string;
  rationale?: string;
};
type VoteTally = {
  type: "vote_tally";
  tallies: Record<string, number>;
  votes: { agent_id: string; name: string; option_id: string; rationale?: string }[];
  consensus_reached: boolean;
  winning_option_id: string | null;
  winning_title: string;
  threshold: number;
};
type SynthesizerStart = { type: "synthesizer_start" };
type FinalReport = {
  type: "final_report";
  report: {
    summary: string;
    ranked_options: { title: string; score: number; rationale: string }[];
    risks: string[];
    next_steps: string[];
  };
};
type Saved = { type: "saved"; run_id: number };
type Done = { type: "done"; run_id?: number };

type StreamEvent =
  | AgentStart
  | Token
  | ReasoningToken
  | AgentEnd
  | InterjectionEvent
  | SessionStart
  | VotePhaseStart
  | VoteOptions
  | VoteCast
  | VoteTally
  | SynthesizerStart
  | FinalReport
  | Saved
  | Done
  | { type: string; [k: string]: unknown };

function parseSseBlock(block: string): StreamEvent | null {
  const lines = block.split("\n").filter(Boolean);
  for (const line of lines) {
    if (line.startsWith("data: ")) {
      const raw = line.slice(6);
      try {
        return JSON.parse(raw) as StreamEvent;
      } catch {
        return null;
      }
    }
  }
  return null;
}

type Turn = {
  kind: "primary" | "interjection";
  agent: string;
  name: string;
  turn: number;
  text: string;
  reasoning?: string;
  targetAgent?: string;
  targetName?: string;
};

export default function DecisionRoomPage() {
  const [context, setContext] = useState("");
  const [model, setModel] = useState(
    () => process.env.NEXT_PUBLIC_DEFAULT_MODEL ?? "stepfun-ai/step-3.5-flash",
  );
  /** Free-typed seconds; clamped on blur and when starting a run */
  const [sessionDurationInput, setSessionDurationInput] = useState("120");
  const [consensusThreshold, setConsensusThreshold] = useState(3);
  const [enableInterjections, setEnableInterjections] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [currentAgent, setCurrentAgent] = useState<{
    id: string;
    name: string;
    turn?: number;
  } | null>(null);
  const [sessionClock, setSessionClock] = useState<{
    receivedAt: number;
    session_duration_sec: number;
    debate_budget_sec: number;
    synth_reserve_sec: number;
  } | null>(null);
  const [debatePhaseOver, setDebatePhaseOver] = useState(false);
  const [report, setReport] = useState<FinalReport["report"] | null>(null);
  const [runId, setRunId] = useState<number | null>(null);
  const [voteOptions, setVoteOptions] = useState<VoteOptions["options"] | null>(null);
  const [voteTally, setVoteTally] = useState<VoteTally | null>(null);
  const [streamingAgentId, setStreamingAgentId] = useState<string | null>(null);
  const [flashAgentId, setFlashAgentId] = useState<string | null>(null);
  const flashClearRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const debateScrollRef = useRef<HTMLDivElement | null>(null);

  const clearFlashTimer = useCallback(() => {
    if (flashClearRef.current) {
      clearTimeout(flashClearRef.current);
      flashClearRef.current = null;
    }
  }, []);

  useEffect(() => () => clearFlashTimer(), [clearFlashTimer]);

  const canRun = useMemo(
    () => context.trim().length >= 10 && !running,
    [context, running],
  );

  const [nowMs, setNowMs] = useState(() => Date.now());
  useEffect(() => {
    if (!running) return;
    const id = setInterval(() => setNowMs(Date.now()), 1000);
    return () => clearInterval(id);
  }, [running]);

  const debateSecondsLeft = useMemo(() => {
    if (!sessionClock || debatePhaseOver) return null;
    const end = sessionClock.receivedAt + sessionClock.debate_budget_sec * 1000;
    return Math.max(0, Math.ceil((end - nowMs) / 1000));
  }, [sessionClock, debatePhaseOver, nowMs]);

  const activeMemberId =
    currentAgent && currentAgent.id !== "synthesizer" ? currentAgent.id : null;
  const synthesizerActive = currentAgent?.id === "synthesizer";

  const agentHighlightId = useMemo(() => {
    if (synthesizerActive) return null;
    if (streamingAgentId) return streamingAgentId;
    if (flashAgentId) return flashAgentId;
    return activeMemberId;
  }, [synthesizerActive, flashAgentId, streamingAgentId, activeMemberId]);

  useLayoutEffect(() => {
    const el = debateScrollRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: "auto" });
  }, [turns, error, voteOptions, voteTally, report, runId, currentAgent, debatePhaseOver]);

  const runDebate = useCallback(async () => {
    setRunning(true);
    setError(null);
    setTurns([]);
    setCurrentAgent(null);
    setReport(null);
    setRunId(null);
    setVoteOptions(null);
    setVoteTally(null);
    setSessionClock(null);
    setDebatePhaseOver(false);
    setStreamingAgentId(null);
    setFlashAgentId(null);
    clearFlashTimer();
    setNowMs(Date.now());

    try {
      const res = await fetch(`${API_URL}/debate/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          context,
          model,
          session_duration_sec: (() => {
            const n = parseInt(sessionDurationInput.replace(/\D/g, ""), 10);
            if (!Number.isFinite(n)) return 120;
            return Math.min(600, Math.max(60, n));
          })(),
          consensus_threshold: consensusThreshold,
          enable_interjections: enableInterjections,
        }),
      });

      if (!res.ok) {
        const t = await res.text();
        throw new Error(t || res.statusText);
      }

      const reader = res.body?.getReader();
      if (!reader) throw new Error("No response body");

      const decoder = new TextDecoder();
      let carry = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        carry += decoder.decode(value, { stream: true });

        const parts = carry.split("\n\n");
        carry = parts.pop() ?? "";

        for (const block of parts) {
          const ev = parseSseBlock(block);
          if (!ev) continue;

          switch (ev.type) {
            case "session_start": {
              const e = ev as SessionStart;
              setSessionClock({
                receivedAt: Date.now(),
                session_duration_sec: e.session_duration_sec,
                debate_budget_sec: e.debate_budget_sec,
                synth_reserve_sec: e.synth_reserve_sec,
              });
              break;
            }
            case "debate_phase_end":
              setDebatePhaseOver(true);
              break;
            case "agent_start": {
              const e = ev as AgentStart;
              const tn = typeof e.turn === "number" ? e.turn : 1;
              setFlashAgentId(null);
              clearFlashTimer();
              setCurrentAgent({ id: e.agent, name: e.name, turn: tn });
              setTurns((prev) => [
                ...prev,
                {
                  kind: "primary",
                  agent: e.agent,
                  name: e.name,
                  turn: tn,
                  text: "",
                  reasoning: "",
                },
              ]);
              break;
            }
            case "reasoning_token": {
              const e = ev as ReasoningToken;
              setStreamingAgentId(e.agent);
              setTurns((prev) => {
                if (prev.length === 0) return prev;
                const next = [...prev];
                const last = next[next.length - 1];
                if (last.agent === e.agent) {
                  const rr = (last.reasoning ?? "") + e.text;
                  next[next.length - 1] = { ...last, reasoning: rr };
                }
                return next;
              });
              break;
            }
            case "token": {
              const e = ev as Token;
              setStreamingAgentId(e.agent);
              setTurns((prev) => {
                if (prev.length === 0) return prev;
                const next = [...prev];
                const last = next[next.length - 1];
                if (last.agent === e.agent) {
                  next[next.length - 1] = { ...last, text: last.text + e.text };
                }
                return next;
              });
              break;
            }
            case "agent_end":
              setCurrentAgent(null);
              setStreamingAgentId(null);
              break;
            case "interjection": {
              const e = ev as InterjectionEvent;
              setStreamingAgentId(null);
              setFlashAgentId(e.agent);
              clearFlashTimer();
              flashClearRef.current = setTimeout(() => {
                setFlashAgentId(null);
                flashClearRef.current = null;
              }, 2500);
              setTurns((prev) => [
                ...prev,
                {
                  kind: "interjection",
                  agent: e.agent,
                  name: e.name,
                  turn: e.turn,
                  text: e.text,
                  targetAgent: e.target_agent,
                  targetName: e.target_name,
                },
              ]);
              break;
            }
            case "vote_options":
              setVoteOptions((ev as VoteOptions).options);
              break;
            case "vote_tally":
              setVoteTally(ev as VoteTally);
              break;
            case "synthesizer_start":
              setStreamingAgentId(null);
              setFlashAgentId(null);
              clearFlashTimer();
              setCurrentAgent({ id: "synthesizer", name: "Chief Synthesizer" });
              break;
            case "final_report":
              setReport((ev as FinalReport).report);
              setCurrentAgent(null);
              break;
            case "saved":
              setRunId((ev as Saved).run_id);
              break;
            case "done": {
              const e = ev as Done;
              if (typeof e.run_id === "number") setRunId(e.run_id);
              break;
            }
            default:
              break;
          }
        }
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setRunning(false);
      setCurrentAgent(null);
      setStreamingAgentId(null);
      setFlashAgentId(null);
      clearFlashTimer();
    }
  }, [
    context,
    model,
    sessionDurationInput,
    consensusThreshold,
    enableInterjections,
    clearFlashTimer,
  ]);

  return (
    <main className="mx-auto box-border flex min-h-0 w-full max-w-7xl flex-1 flex-col gap-4 overflow-hidden p-6">
      <header className="shrink-0 flex flex-col gap-3 border-b border-white/10 pb-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Decision Room</h1>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-[var(--muted)]">
            Timed debate (max three sentences per turn), optional interjections, then vote and Chief Synthesizer
            in the last {sessionClock?.synth_reserve_sec ?? 30}s of the session.
          </p>
        </div>
        <Link href="/" className="shrink-0 text-sm text-[var(--muted)] hover:text-[var(--foreground)]">
          Home
        </Link>
      </header>

      <div className="flex min-h-0 flex-1 flex-col gap-4 lg:flex-row lg:items-stretch lg:gap-6">
        <aside className="order-1 flex min-h-0 min-w-0 flex-[1.15] flex-col overflow-y-auto lg:order-1">
          <ChamberSeats
            synthesizerActive={synthesizerActive}
            agentHighlightId={agentHighlightId}
          />
        </aside>

        <div className="order-2 flex min-h-0 w-full min-w-0 flex-1 flex-col gap-4 lg:order-2 lg:h-full lg:w-[420px] lg:max-w-[420px] lg:shrink-0 lg:flex-none">
          <section className="shrink-0 flex flex-col gap-4 rounded-xl border border-white/10 bg-[var(--card)]/40 p-4">
      <label className="flex flex-col gap-2">
        <span className="text-sm font-medium">Context</span>
        <textarea
          className="min-h-[140px] rounded-lg border border-white/10 bg-[var(--card)] p-3 text-sm outline-none ring-[var(--accent)] focus:ring-2"
          placeholder="Describe the decision, constraints, and what a good outcome looks like…"
          value={context}
          onChange={(e) => setContext(e.target.value)}
          disabled={running}
        />
      </label>

      {running && sessionClock && debateSecondsLeft !== null && !debatePhaseOver && (
        <p className="text-xs text-[var(--muted)]">
          Debate segment: ~<span className="text-[var(--foreground)]">{debateSecondsLeft}s</span> left (session{" "}
          {sessionClock.session_duration_sec}s; last {sessionClock.synth_reserve_sec}s for synthesizer)
        </p>
      )}

      <div className="flex flex-wrap items-end gap-4">
        <label className="flex flex-col gap-1">
          <span className="text-xs text-[var(--muted)]">Model</span>
          <input
            className="rounded-lg border border-white/10 bg-[var(--card)] px-3 py-2 text-sm"
            value={model}
            onChange={(e) => setModel(e.target.value)}
            disabled={running}
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs text-[var(--muted)]">Session (sec)</span>
          <input
            type="text"
            inputMode="numeric"
            autoComplete="off"
            className="w-24 rounded-lg border border-white/10 bg-[var(--card)] px-3 py-2 text-sm"
            value={sessionDurationInput}
            onChange={(e) => {
              const raw = e.target.value.replace(/\D/g, "");
              setSessionDurationInput(raw);
            }}
            onBlur={() => {
              if (sessionDurationInput === "") {
                setSessionDurationInput("120");
                return;
              }
              const n = parseInt(sessionDurationInput, 10);
              const clamped = Number.isFinite(n)
                ? Math.min(600, Math.max(60, n))
                : 120;
              setSessionDurationInput(String(clamped));
            }}
            disabled={running}
          />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-xs text-[var(--muted)]">Consensus (votes)</span>
          <input
            type="number"
            min={1}
            max={DEBATE_AGENTS.length}
            className="w-20 rounded-lg border border-white/10 bg-[var(--card)] px-3 py-2 text-sm"
            value={consensusThreshold}
            onChange={(e) => setConsensusThreshold(Number(e.target.value) || 3)}
            disabled={running}
          />
        </label>
        <label className="flex cursor-pointer items-center gap-2 text-sm">
          <input
            type="checkbox"
            className="rounded border-white/20"
            checked={enableInterjections}
            onChange={(e) => setEnableInterjections(e.target.checked)}
            disabled={running}
          />
          <span className="text-[var(--muted)]">Parallel interjections</span>
        </label>
        <button
          type="button"
          onClick={runDebate}
          disabled={!canRun}
          className="w-fit rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
        >
          {running ? "Running…" : "Run debate"}
        </button>
      </div>
          </section>

          <section
            className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-white/10 bg-[var(--card)]/30"
            aria-label="Session output: status, debate, votes, report"
          >
            <div
              ref={debateScrollRef}
              className="min-h-0 flex-1 space-y-4 overflow-y-auto overscroll-contain p-4 [scrollbar-gutter:stable]"
            >
      {error && (
        <p className="rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm text-red-200">
          {error}
        </p>
      )}

      {currentAgent && (
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
                  <span className="text-[var(--muted)]">
                    {(o.score * 100).toFixed(0)}%
                  </span>
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

      {runId !== null && (
        <p className="text-xs text-[var(--muted)]">Saved as run #{runId}</p>
      )}
            </div>
          </section>
        </div>
      </div>
    </main>
  );
}
