"use client";

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";

import { ChamberSeats } from "./ChamberSeats";
import { DEBATE_AGENTS } from "./debateAgents";
import { DebateTranscript } from "./DebateTranscript";
import type { StoredDebate } from "./debateHistory";
import { appendDebate, loadDebates } from "./debateHistory";
import type { Turn } from "./debateTypes";

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

function previewContext(s: string, max = 52): string {
  const t = s.trim().replace(/\s+/g, " ");
  if (t.length <= max) return t || "(empty)";
  return `${t.slice(0, max)}…`;
}

function formatSavedAt(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export default function DecisionRoomPage() {
  const [context, setContext] = useState("");
  const [model, setModel] = useState(
    () => process.env.NEXT_PUBLIC_DEFAULT_MODEL ?? "stepfun-ai/step-3.5-flash",
  );
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

  const [debateHistory, setDebateHistory] = useState<StoredDebate[]>([]);
  const [selectedArchiveId, setSelectedArchiveId] = useState<string | null>(null);

  const runSeq = useRef(0);
  const savedUpToSeq = useRef(0);

  const lastSessionMeta = useRef({
    context: "",
    model: "",
    session_duration_sec: 120,
    consensus_threshold: 3,
    enable_interjections: true,
  });

  useEffect(() => {
    setDebateHistory(loadDebates());
  }, []);

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

  const selectedArchive = useMemo(
    () => (selectedArchiveId ? debateHistory.find((d) => d.id === selectedArchiveId) : null),
    [debateHistory, selectedArchiveId],
  );

  const displayTurns = selectedArchive ? selectedArchive.turns : turns;
  const displayVoteOptions = selectedArchive ? selectedArchive.voteOptions : voteOptions;
  const displayVoteTally = selectedArchive ? selectedArchive.voteTally : voteTally;
  const displayReport = selectedArchive ? selectedArchive.report : report;
  const displayError = selectedArchive ? selectedArchive.error : error;
  useLayoutEffect(() => {
    const el = debateScrollRef.current;
    if (!el) return;
    el.scrollTo({ top: el.scrollHeight, behavior: "auto" });
  }, [
    displayTurns,
    displayError,
    displayVoteOptions,
    displayVoteTally,
    displayReport,
    runId,
    currentAgent,
    debatePhaseOver,
    selectedArchiveId,
  ]);

  useEffect(() => {
    if (running) return;
    const seq = runSeq.current;
    if (seq <= savedUpToSeq.current) return;
    const hasBody =
      turns.length > 0 || voteTally !== null || report !== null || error !== null;
    if (!hasBody) {
      savedUpToSeq.current = seq;
      return;
    }
    savedUpToSeq.current = seq;
    const entry: StoredDebate = {
      id: crypto.randomUUID(),
      savedAt: new Date().toISOString(),
      context: lastSessionMeta.current.context,
      model: lastSessionMeta.current.model,
      session_duration_sec: lastSessionMeta.current.session_duration_sec,
      consensus_threshold: lastSessionMeta.current.consensus_threshold,
      enable_interjections: lastSessionMeta.current.enable_interjections,
      turns,
      voteOptions,
      voteTally: voteTally
        ? {
            tallies: voteTally.tallies,
            votes: voteTally.votes,
            consensus_reached: voteTally.consensus_reached,
            winning_option_id: voteTally.winning_option_id,
            winning_title: voteTally.winning_title,
            threshold: voteTally.threshold,
          }
        : null,
      report,
      error,
    };
    appendDebate(entry);
    setDebateHistory(loadDebates());
  }, [running, turns, voteTally, report, voteOptions, error]);

  const runDebate = useCallback(async () => {
    runSeq.current += 1;
    setSelectedArchiveId(null);
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

    const sessionDur = (() => {
      const n = parseInt(sessionDurationInput.replace(/\D/g, ""), 10);
      if (!Number.isFinite(n)) return 120;
      return Math.min(600, Math.max(60, n));
    })();

    lastSessionMeta.current = {
      context,
      model,
      session_duration_sec: sessionDur,
      consensus_threshold: consensusThreshold,
      enable_interjections: enableInterjections,
    };

    try {
      const res = await fetch(`${API_URL}/debate/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          context,
          model,
          session_duration_sec: sessionDur,
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
    <main className="mx-auto box-border flex min-h-0 w-full max-w-[min(100%,92rem)] flex-1 flex-col gap-4 overflow-y-auto p-6">
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

      {/* Mobile: chamber → history → form → debate. Desktop: chamber+timer | history; debate | form */}
      <div className="flex min-h-0 flex-1 flex-col gap-4 lg:grid lg:min-h-0 lg:grid-cols-[minmax(0,1fr)_minmax(320px,440px)] lg:grid-rows-[auto_minmax(0,1fr)] lg:gap-6">
        {/* Row 1 col 1 — Chamber + debate-phase timer bottom-right */}
        <aside className="order-1 flex min-h-0 min-w-0 flex-col lg:col-start-1 lg:row-start-1">
          <ChamberSeats
            synthesizerActive={synthesizerActive}
            agentHighlightId={agentHighlightId}
            bottomRight={
              running && sessionClock && debateSecondsLeft !== null && !debatePhaseOver ? (
                <div
                  className="rounded-lg border border-white/15 bg-[var(--background)]/95 px-2.5 py-2 text-left shadow-lg backdrop-blur-sm"
                  aria-live="polite"
                >
                  <p className="text-[9px] font-medium uppercase tracking-wide text-[var(--muted)]">
                    Debate phase
                  </p>
                  <p className="mt-1 text-[11px] leading-snug text-[var(--muted)] sm:text-xs">
                    <span className="font-semibold tabular-nums text-[var(--foreground)]">
                      {debateSecondsLeft}s
                    </span>{" "}
                    left · {sessionClock.session_duration_sec}s session · {sessionClock.synth_reserve_sec}s closing
                  </p>
                </div>
              ) : undefined
            }
          />
        </aside>

        {/* Row 1 col 2 — History (wider panel) */}
        <section
          className="order-2 flex max-h-40 min-h-0 flex-col overflow-hidden rounded-xl border border-white/10 bg-[var(--card)]/30 lg:col-start-2 lg:row-start-1 lg:max-h-none lg:min-h-0 lg:self-stretch"
          aria-label="Saved debates"
        >
          <div className="flex shrink-0 items-center justify-between gap-2 border-b border-white/10 px-3 py-2">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-[var(--muted)]">History</h2>
            {selectedArchiveId !== null && (
              <button
                type="button"
                onClick={() => setSelectedArchiveId(null)}
                className="shrink-0 rounded-md px-2 py-1 text-xs font-medium text-[var(--accent)] hover:bg-white/5"
              >
                Live
              </button>
            )}
          </div>
          <nav className="min-h-0 flex-1 overflow-x-auto overflow-y-auto px-2 py-2 lg:px-3">
            <ul className="flex flex-row gap-2 lg:flex-col lg:gap-1.5">
              {debateHistory.map((d) => (
                <li key={d.id} className="max-w-[200px] shrink-0 lg:max-w-none">
                  <button
                    type="button"
                    onClick={() => setSelectedArchiveId(d.id)}
                    className={`w-full rounded-lg px-2.5 py-2 text-left text-xs transition-colors ${
                      selectedArchiveId === d.id
                        ? "bg-[var(--accent)]/20 text-[var(--foreground)]"
                        : "text-[var(--muted)] hover:bg-white/5 hover:text-[var(--foreground)]"
                    }`}
                  >
                    <span className="block text-[10px] uppercase tracking-wide text-[var(--muted)]">
                      {formatSavedAt(d.savedAt)}
                    </span>
                    <span className="mt-0.5 line-clamp-2 break-words leading-snug">
                      {previewContext(d.context, 72)}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </nav>
        </section>

        {/* Row 2 col 1 — Debate transcript (full width of column) */}
        <section
          className="order-4 flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden rounded-xl border border-white/10 bg-[var(--card)]/30 lg:col-start-1 lg:row-start-2"
          aria-label="Debate transcript"
        >
          <DebateTranscript
            error={displayError}
            currentAgent={selectedArchive ? null : currentAgent}
            running={selectedArchive ? false : running}
            turns={displayTurns}
            voteOptions={displayVoteOptions}
            voteTally={displayVoteTally}
            report={displayReport}
            runId={selectedArchive ? null : runId}
            debateScrollRef={debateScrollRef}
          />
        </section>

        {/* Row 2 col 2 — Context & controls */}
        <section className="order-3 flex min-h-0 flex-col gap-4 lg:col-start-2 lg:row-start-2">
          <div className="flex shrink-0 flex-col gap-3 rounded-xl border border-white/10 bg-[var(--card)]/40 p-4">
            <label className="flex w-full flex-col gap-1.5">
              <span className="text-sm font-medium">Context</span>
              <textarea
                rows={4}
                className="min-h-[5.5rem] w-full resize-y rounded-lg border border-white/10 bg-[var(--card)] p-2.5 text-sm outline-none ring-[var(--accent)] focus:ring-2"
                placeholder="Describe the decision, constraints, and what a good outcome looks like…"
                value={context}
                onChange={(e) => setContext(e.target.value)}
                disabled={running}
              />
            </label>

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
              <div className="flex flex-col gap-1">
                <button
                  type="button"
                  onClick={runDebate}
                  disabled={!canRun}
                  title={
                    context.trim().length < 10
                      ? "Add at least 10 characters in Context"
                      : running
                        ? "Debate in progress"
                        : "Start debate"
                  }
                  className="w-fit rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white disabled:opacity-40"
                >
                  {running ? "Running…" : "Run debate"}
                </button>
                {context.trim().length < 10 && !running && (
                  <p className="max-w-full text-[11px] text-amber-200/90">
                    Type at least 10 characters in Context to enable Run.
                  </p>
                )}
              </div>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}
