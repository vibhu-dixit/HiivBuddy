"use client";

import {
  Suspense,
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import Image from "next/image";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";

import { useAuth } from "../auth/AuthProvider";
import { DEMO_SAMPLE_CONTEXT } from "../components/landing/landingCopy";

import { ChamberSeats } from "./ChamberSeats";
import { DebateTranscript } from "./DebateTranscript";
import type { StoredDebate } from "./debateHistory";
import {
  appendDebate,
  clearDebatesForUser,
  loadDebates,
  removeDebate,
} from "./debateHistory";
import { isTurnVisibleToUser, sanitizeDebateTurnText } from "./displayDebateText";
import { buildSessionMarkdown, downloadMarkdownFile } from "./sessionExportMarkdown";
import type { Turn } from "./debateTypes";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
/** Must match API `MAX_EXTRACTED_CHARS` in context_ingest.py */
const MAX_CONTEXT_CHARS = 65536;

/** UI removed — fixed request shape; model IDs come from API `LLM_DEFAULT_MODEL` / tier env only. */
const FIXED_CONSENSUS_THRESHOLD = 3;
const FIXED_ENABLE_INTERJECTIONS = true;
const FIXED_TRACK_ENVIRONMENT = false;
const FIXED_SYNTH_ENV_SNAPSHOT = false;

type SessionModeChoice = "classic" | "swarm";

/** Default session mode (swarm). Set `NEXT_PUBLIC_DEFAULT_SESSION_MODE=classic` for streamed debate + interjections. */
const DEFAULT_SESSION_MODE: SessionModeChoice =
  process.env.NEXT_PUBLIC_DEFAULT_SESSION_MODE === "classic" ? "classic" : "swarm";

/** Inclusive random length per run (API still clamps 60–600). */
function randomSessionDurationSec(): number {
  return 120 + Math.floor(Math.random() * (200 - 120 + 1));
}

function authHeaders(token: string, extra?: HeadersInit): HeadersInit {
  return { ...extra, Authorization: `Bearer ${token}` };
}

type SessionStart = {
  type: "session_start";
  session_duration_sec: number;
  debate_budget_sec: number;
  synth_reserve_sec: number;
};
type AgentStart = { type: "agent_start"; agent: string; name: string; turn?: number };
type Token = { type: "token"; agent: string; text: string };
type ReasoningToken = { type: "reasoning_token"; agent: string; text: string };
type AgentEnd = {
  type: "agent_end";
  agent: string;
  full_text: string;
  turn?: number;
  /** Server-cleaned transcript; replaces streamed tokens so meta/planning is not left visible */
  reasoning_text?: string | null;
};
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
  env_snapshot?: unknown;
};
type EnvSnapshotEvent = {
  type: "env_snapshot";
  phase: string;
  snapshot: unknown;
};
type StreamError = { type: "stream_error"; message: string };
type Saved = { type: "saved"; run_id: number };
type Done = { type: "done"; run_id?: number };

type ReportState = NonNullable<StoredDebate["report"]>;

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
  | EnvSnapshotEvent
  | StreamError
  | Saved
  | Done
  | { type: string; [k: string]: unknown };

function parseSseBlock(block: string): StreamEvent | null {
  const lines = block.split("\n").filter(Boolean);
  for (const line of lines) {
    if (line.startsWith("data: ")) {
      const raw = line.slice(6).trimEnd();
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

function DecisionRoomContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { token, user, loading: authLoading, logout } = useAuth();
  const isGuest = Boolean(user?.isGuest);

  useEffect(() => {
    if (!authLoading && (!token || !user)) {
      router.replace("/login");
    }
  }, [authLoading, token, user, router]);

  useEffect(() => {
    if (!user) return;
    if (isGuest) {
      clearDebatesForUser(user.userId);
      setDebateHistory([]);
      setSelectedArchiveId(null);
      return;
    }
    setDebateHistory(loadDebates(user.userId));
  }, [user, isGuest]);

  const [context, setContext] = useState("");

  /** Guest demo: always restore sample scenario after refresh (URL often loses ?demo=1). */
  useEffect(() => {
    if (authLoading || !user) return;
    if (isGuest) {
      setContext((current) => (current.trim().length === 0 ? DEMO_SAMPLE_CONTEXT : current));
      return;
    }
    if (searchParams.get("demo") === "1") {
      setContext((current) => (current.trim().length === 0 ? DEMO_SAMPLE_CONTEXT : current));
    }
  }, [authLoading, user, isGuest, searchParams]);
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
  const [report, setReport] = useState<ReportState | null>(null);
  const [environmentPeek, setEnvironmentPeek] = useState<{
    phase: string;
    snapshot: unknown;
  } | null>(null);
  const [runId, setRunId] = useState<number | null>(null);
  /** True after vote phase ends until final_report arrives (Chief Synthesizer HTTP call). */
  const [chiefSynthPending, setChiefSynthPending] = useState(false);
  const [voteOptions, setVoteOptions] = useState<VoteOptions["options"] | null>(null);
  const [voteTally, setVoteTally] = useState<VoteTally | null>(null);
  const [streamingAgentId, setStreamingAgentId] = useState<string | null>(null);
  /** Swarm mode has no token stream; keep seat ring lit briefly after each turn. */
  const [floorAgentId, setFloorAgentId] = useState<string | null>(null);
  const [flashAgentId, setFlashAgentId] = useState<string | null>(null);
  const flashClearRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const floorClearRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const runIdRef = useRef<number | null>(null);
  const debateScrollRef = useRef<HTMLDivElement | null>(null);

  const [debateHistory, setDebateHistory] = useState<StoredDebate[]>([]);
  const [selectedArchiveId, setSelectedArchiveId] = useState<string | null>(null);
  const [historyError, setHistoryError] = useState<string | null>(null);

  const contextFileInputRef = useRef<HTMLInputElement | null>(null);
  const [contextFileMessage, setContextFileMessage] = useState<string | null>(null);
  const [contextAttachMode, setContextAttachMode] = useState<"append" | "replace">("append");

  const runSeq = useRef(0);
  const savedUpToSeq = useRef(0);
  /** Set when a run starts; used as localStorage id so we can attach API `run_id` when persisting. */
  const pendingArchiveIdRef = useRef<string | null>(null);
  /** Filled on SSE `saved` before the persist effect runs. */
  const pendingServerRunIdRef = useRef<number | null>(null);

  const lastSessionMeta = useRef({
    context: "",
    model: "",
    session_duration_sec: 120,
    consensus_threshold: FIXED_CONSENSUS_THRESHOLD,
    enable_interjections: FIXED_ENABLE_INTERJECTIONS,
    session_mode: DEFAULT_SESSION_MODE satisfies SessionModeChoice,
    track_environment: FIXED_TRACK_ENVIRONMENT,
    synth_env_snapshot: FIXED_SYNTH_ENV_SNAPSHOT,
  });

  const [sessionMode, setSessionMode] = useState<SessionModeChoice>(DEFAULT_SESSION_MODE);

  const clearFlashTimer = useCallback(() => {
    if (flashClearRef.current) {
      clearTimeout(flashClearRef.current);
      flashClearRef.current = null;
    }
  }, []);

  const clearFloorTimer = useCallback(() => {
    if (floorClearRef.current) {
      clearTimeout(floorClearRef.current);
      floorClearRef.current = null;
    }
  }, []);

  const pulseFloorAgent = useCallback(
    (agentId: string, ms = 520) => {
      clearFloorTimer();
      setFloorAgentId(agentId);
      floorClearRef.current = setTimeout(() => {
        setFloorAgentId(null);
        floorClearRef.current = null;
      }, ms);
    },
    [clearFloorTimer],
  );

  useEffect(() => {
    runIdRef.current = runId;
  }, [runId]);

  useEffect(() => {
    if (!isGuest || !token) return;
    const deleteEphemeralRun = () => {
      const rid = runIdRef.current;
      if (typeof rid !== "number") return;
      void fetch(`${API_URL}/debate/runs/${rid}`, {
        method: "DELETE",
        headers: authHeaders(token),
        keepalive: true,
      });
    };
    window.addEventListener("pagehide", deleteEphemeralRun);
    return () => {
      window.removeEventListener("pagehide", deleteEphemeralRun);
      deleteEphemeralRun();
    };
  }, [isGuest, token]);

  useEffect(
    () => () => {
      clearFlashTimer();
      clearFloorTimer();
    },
    [clearFlashTimer, clearFloorTimer],
  );

  const canRun = useMemo(
    () => context.trim().length >= 10 && !running,
    [context, running],
  );

  const applyExtractedContext = useCallback(
    (text: string, filename: string, truncatedFromServer?: boolean) => {
      const incoming = text.replace(/\r\n/g, "\n").replace(/\r/g, "\n").trimEnd();
      let next: string;
      if (contextAttachMode === "replace") {
        next = incoming;
      } else {
        const sep = `\n\n--- from: ${filename} ---\n\n`;
        const base = context.trimEnd();
        next = base ? `${base}${sep}${incoming}` : incoming;
      }
      let truncated = Boolean(truncatedFromServer);
      if (next.length > MAX_CONTEXT_CHARS) {
        next = next.slice(0, MAX_CONTEXT_CHARS);
        truncated = true;
      }
      setContext(next);
      setContextFileMessage(
        truncated
          ? `Loaded “${filename}”; text truncated to ${MAX_CONTEXT_CHARS.toLocaleString()} characters.`
          : `Loaded “${filename}”.`,
      );
    },
    [context, contextAttachMode],
  );

  const onContextFileChange = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      e.target.value = "";
      if (!file) return;
      if (!token) {
        setContextFileMessage("Sign in to attach PDFs.");
        return;
      }
      setContextFileMessage(null);
      const name = file.name || "file";
      const ext = name.includes(".") ? (name.split(".").pop() ?? "").toLowerCase() : "";

      try {
        const isPdf =
          ext === "pdf" ||
          file.type === "application/pdf" ||
          file.type === "application/x-pdf";
        if (isPdf) {
          const fd = new FormData();
          fd.append("file", file, name);
          const res = await fetch(`${API_URL}/context/extract`, {
            method: "POST",
            headers: authHeaders(token),
            body: fd,
          });
          if (!res.ok) {
            const t = await res.text();
            throw new Error(t || res.statusText);
          }
          const data = (await res.json()) as { text: string; truncated?: boolean };
          applyExtractedContext(data.text, name, data.truncated);
          return;
        }
        const isText =
          ext === "txt" ||
          ext === "md" ||
          ext === "markdown" ||
          file.type.startsWith("text/") ||
          (file.type === "application/octet-stream" &&
            (ext === "txt" || ext === "md" || ext === "markdown"));
        if (isText) {
          const text = await file.text();
          applyExtractedContext(text, name, false);
          return;
        }
        setContextFileMessage("Unsupported file. Use .txt, .md, or .pdf.");
      } catch (err) {
        setContextFileMessage(err instanceof Error ? err.message : "Could not read file.");
      }
    },
    [applyExtractedContext, token],
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
    if (floorAgentId) return floorAgentId;
    if (flashAgentId) return flashAgentId;
    return activeMemberId;
  }, [synthesizerActive, flashAgentId, floorAgentId, streamingAgentId, activeMemberId]);

  const selectedArchive = useMemo(
    () => (selectedArchiveId ? debateHistory.find((d) => d.id === selectedArchiveId) : null),
    [debateHistory, selectedArchiveId],
  );

  const displayTurns = selectedArchive ? selectedArchive.turns : turns;
  const displayVoteOptions = selectedArchive ? selectedArchive.voteOptions : voteOptions;
  const displayVoteTally = selectedArchive ? selectedArchive.voteTally : voteTally;
  const displayReport = selectedArchive ? selectedArchive.report : report;
  const displayError = selectedArchive ? selectedArchive.error : error;

  const displayEnvironmentPeek = useMemo(() => {
    if (selectedArchive?.report?.env_snapshot != null) {
      return {
        phase: "stored",
        snapshot: selectedArchive.report.env_snapshot,
      };
    }
    if (selectedArchive) return null;
    if (report?.env_snapshot != null) {
      return { phase: "final", snapshot: report.env_snapshot };
    }
    return environmentPeek;
  }, [selectedArchive, report, environmentPeek]);

  const hasExportableBody = useMemo(
    () =>
      displayTurns.length > 0 ||
      displayVoteTally !== null ||
      displayReport !== null ||
      Boolean(displayError),
    [displayTurns.length, displayVoteTally, displayReport, displayError],
  );

  const canExportMarkdown = useMemo(
    () => hasExportableBody && (!running || selectedArchiveId !== null),
    [hasExportableBody, running, selectedArchiveId],
  );

  const handleExportMarkdown = useCallback(() => {
    if (selectedArchive) {
      const md = buildSessionMarkdown({
        context: selectedArchive.context,
        model: selectedArchive.model,
        session_duration_sec: selectedArchive.session_duration_sec,
        consensus_threshold: selectedArchive.consensus_threshold,
        enable_interjections: selectedArchive.enable_interjections,
        session_mode: selectedArchive.session_mode ?? selectedArchive.debate_mode,
        track_environment: selectedArchive.track_environment,
        synth_env_snapshot: selectedArchive.synth_env_snapshot,
        savedAt: selectedArchive.savedAt,
        turns: selectedArchive.turns,
        voteOptions: selectedArchive.voteOptions,
        voteTally: selectedArchive.voteTally,
        report: selectedArchive.report,
        error: selectedArchive.error,
        runId: null,
      });
      const safe = selectedArchive.savedAt.slice(0, 19).replace(/[:]/g, "-");
      downloadMarkdownFile(md, `hiivbuddy-${safe}`);
      return;
    }
    const md = buildSessionMarkdown({
      context,
      model: lastSessionMeta.current.model,
      session_duration_sec: lastSessionMeta.current.session_duration_sec,
      consensus_threshold: FIXED_CONSENSUS_THRESHOLD,
      enable_interjections: FIXED_ENABLE_INTERJECTIONS,
      session_mode: lastSessionMeta.current.session_mode,
      track_environment: FIXED_TRACK_ENVIRONMENT,
      synth_env_snapshot: FIXED_SYNTH_ENV_SNAPSHOT,
      savedAt: new Date().toISOString(),
      turns,
      voteOptions,
      voteTally,
      report,
      error,
      runId,
    });
    downloadMarkdownFile(md, `hiivbuddy-session-${Date.now()}`);
  }, [
    selectedArchive,
    context,
    turns,
    voteOptions,
    voteTally,
    report,
    error,
    runId,
  ]);

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
    displayEnvironmentPeek,
  ]);

  useEffect(() => {
    if (isGuest || running) return;
    const seq = runSeq.current;
    if (seq <= savedUpToSeq.current) return;
    const hasBody =
      turns.length > 0 || voteTally !== null || report !== null || error !== null;
    if (!hasBody) {
      savedUpToSeq.current = seq;
      return;
    }
    savedUpToSeq.current = seq;
    const serverRunId = pendingServerRunIdRef.current;
    pendingServerRunIdRef.current = null;
    const archiveId = pendingArchiveIdRef.current ?? crypto.randomUUID();
    const entry: StoredDebate = {
      id: archiveId,
      savedAt: new Date().toISOString(),
      context: lastSessionMeta.current.context,
      model: lastSessionMeta.current.model,
      session_duration_sec: lastSessionMeta.current.session_duration_sec,
      consensus_threshold: lastSessionMeta.current.consensus_threshold,
      enable_interjections: lastSessionMeta.current.enable_interjections,
      session_mode: lastSessionMeta.current.session_mode,
      track_environment: lastSessionMeta.current.track_environment,
      synth_env_snapshot: lastSessionMeta.current.synth_env_snapshot,
      ...(typeof serverRunId === "number" ? { run_id: serverRunId } : {}),
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
    if (!user) return;
    appendDebate(user.userId, entry);
    setDebateHistory(loadDebates(user.userId));
  }, [isGuest, running, turns, voteTally, report, voteOptions, error, user]);

  const applySanitizedTurnText = useCallback((raw: string): string | null => {
    if (!isTurnVisibleToUser(raw)) return null;
    const { text } = sanitizeDebateTurnText(raw);
    return text;
  }, []);

  const handleDeleteArchive = useCallback(
    async (d: StoredDebate) => {
      if (!token || !user) return;
      setHistoryError(null);
      if (typeof d.run_id === "number") {
        try {
          const res = await fetch(`${API_URL}/debate/runs/${d.run_id}`, {
            method: "DELETE",
            headers: authHeaders(token),
          });
          if (!res.ok && res.status !== 404) {
            const t = await res.text();
            throw new Error(t || res.statusText);
          }
        } catch (e) {
          setHistoryError(e instanceof Error ? e.message : "Could not delete saved run on the server.");
          return;
        }
      }
      removeDebate(user.userId, d.id);
      setDebateHistory(loadDebates(user.userId));
      setSelectedArchiveId((cur) => (cur === d.id ? null : cur));
    },
    [token, user],
  );

  const runDebate = useCallback(async () => {
    runSeq.current += 1;
    pendingArchiveIdRef.current = crypto.randomUUID();
    pendingServerRunIdRef.current = null;
    setSelectedArchiveId(null);
    setRunning(true);
    setChiefSynthPending(false);
    setError(null);
    setTurns([]);
    setCurrentAgent(null);
    setReport(null);
    setRunId(null);
    setVoteOptions(null);
    setVoteTally(null);
    setSessionClock(null);
    setDebatePhaseOver(false);
    setEnvironmentPeek(null);
    setStreamingAgentId(null);
    setFlashAgentId(null);
    clearFlashTimer();
    setNowMs(Date.now());

    const sessionDur = randomSessionDurationSec();

    lastSessionMeta.current = {
      context,
      model: "",
      session_duration_sec: sessionDur,
      consensus_threshold: FIXED_CONSENSUS_THRESHOLD,
      enable_interjections: FIXED_ENABLE_INTERJECTIONS,
      session_mode: sessionMode,
      track_environment: FIXED_TRACK_ENVIRONMENT,
      synth_env_snapshot: FIXED_SYNTH_ENV_SNAPSHOT,
    };

    if (!token) {
      setError("Not signed in.");
      setRunning(false);
      return;
    }

    try {
      const res = await fetch(`${API_URL}/debate/stream`, {
        method: "POST",
        headers: authHeaders(token, { "Content-Type": "application/json" }),
        body: JSON.stringify({
          context,
          session_duration_sec: sessionDur,
          consensus_threshold: FIXED_CONSENSUS_THRESHOLD,
          enable_interjections: FIXED_ENABLE_INTERJECTIONS,
          session_mode: sessionMode,
          track_environment: FIXED_TRACK_ENVIRONMENT,
          synth_env_snapshot: FIXED_SYNTH_ENV_SNAPSHOT,
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
        // Normalize CRLF so SSE event boundaries (\n\n) split correctly (HTTP often uses \r\n).
        carry = carry.replace(/\r\n/g, "\n").replace(/\r/g, "\n");

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
              clearFloorTimer();
              setFloorAgentId(e.agent);
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
            case "reasoning_token":
              /* Reasoning/thinking traces not shown in UI; skip accumulating. */
              break;
            case "token": {
              const e = ev as Token;
              setStreamingAgentId(e.agent);
              setFloorAgentId(e.agent);
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
            case "agent_end": {
              const e = ev as AgentEnd;
              setCurrentAgent(null);
              setStreamingAgentId(null);
              pulseFloorAgent(e.agent);
              // Always replace streamed tokens with server-cleaned text (including ""), or raw meta stays visible.
              if (typeof e.full_text === "string") {
                const cleaned = applySanitizedTurnText(e.full_text);
                setTurns((prev) => {
                  if (prev.length === 0) return prev;
                  if (cleaned === null) {
                    const last = prev[prev.length - 1];
                    if (last.agent === e.agent) {
                      return prev.slice(0, -1);
                    }
                    return prev;
                  }
                  const next = [...prev];
                  const last = next[next.length - 1];
                  if (last.agent === e.agent) {
                    next[next.length - 1] = {
                      ...last,
                      text: cleaned,
                      reasoning: "",
                    };
                  }
                  return next;
                });
              }
              break;
            }
            case "interjection": {
              const e = ev as InterjectionEvent;
              setStreamingAgentId(null);
              setFlashAgentId(e.agent);
              clearFlashTimer();
              flashClearRef.current = setTimeout(() => {
                setFlashAgentId(null);
                flashClearRef.current = null;
              }, 2500);
              setTurns((prev) => {
                const cleaned = applySanitizedTurnText(e.text);
                if (cleaned === null) return prev;
                return [
                  ...prev,
                  {
                    kind: "interjection",
                    agent: e.agent,
                    name: e.name,
                    turn: e.turn,
                    text: cleaned,
                    targetAgent: e.target_agent,
                    targetName: e.target_name,
                  },
                ];
              });
              break;
            }
            case "vote_options":
              setVoteOptions((ev as VoteOptions).options);
              break;
            case "vote_tally":
              setVoteTally(ev as VoteTally);
              break;
            case "env_snapshot": {
              const e = ev as EnvSnapshotEvent;
              setEnvironmentPeek({ phase: e.phase, snapshot: e.snapshot });
              break;
            }
            case "synthesizer_start":
              setStreamingAgentId(null);
              setFlashAgentId(null);
              clearFlashTimer();
              setChiefSynthPending(true);
              setCurrentAgent({ id: "synthesizer", name: "Chief Synthesizer" });
              break;
            case "final_report": {
              const e = ev as FinalReport;
              setReport(
                e.env_snapshot != null
                  ? { ...e.report, env_snapshot: e.env_snapshot }
                  : e.report,
              );
              setChiefSynthPending(false);
              setEnvironmentPeek(null);
              setCurrentAgent(null);
              break;
            }
            case "saved": {
              const sid = (ev as Saved).run_id;
              pendingServerRunIdRef.current = sid;
              setRunId(sid);
              break;
            }
            case "done": {
              const e = ev as Done;
              if (typeof e.run_id === "number") setRunId(e.run_id);
              break;
            }
            case "stream_error": {
              const e = ev as StreamError;
              setError(e.message || "The session ended unexpectedly.");
              break;
            }
            default:
              break;
          }
        }
      }

    } catch (e) {
      setChiefSynthPending(false);
      setError(e instanceof Error ? e.message : "Request failed");
    } finally {
      setRunning(false);
      setChiefSynthPending(false);
      setCurrentAgent(null);
      setStreamingAgentId(null);
      setFlashAgentId(null);
      clearFlashTimer();
    }
  }, [context, applySanitizedTurnText, clearFlashTimer, pulseFloorAgent, clearFloorTimer, token, sessionMode]);

  if (authLoading || !token || !user) {
    return (
      <main className="flex min-h-screen flex-col items-center justify-center p-8">
        <p className="text-sm text-[var(--muted)]">Loading…</p>
      </main>
    );
  }

  return (
    <main className="mx-auto box-border flex min-h-0 w-full max-w-[min(100%,92rem)] flex-1 flex-col gap-4 overflow-hidden p-4 sm:p-6">
      {isGuest && (
        <div className="shrink-0 rounded-lg border border-[var(--accent)]/30 bg-[var(--accent-muted)] px-4 py-3 text-sm text-[var(--foreground)]">
          You&apos;re in demo mode.{" "}
          <Link href="/login" className="font-medium text-[var(--accent)] underline hover:text-[var(--accent-hover)]">
            Sign up
          </Link>{" "}
          to save your sessions and history.
        </div>
      )}
      <header className="shrink-0 flex flex-col gap-3 border-b border-[var(--border)] pb-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Link href="/" className="shrink-0">
              <Image
                src="/logo.png"
                alt="Hiiv home"
                width={32}
                height={32}
                className="h-8 w-8 rounded-lg"
              />
            </Link>
            <h1 className="text-xl font-semibold tracking-tight">Decision Room</h1>
          </div>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-[var(--muted)]">
            {isGuest ? (
              <>
                Your panel will deliberate for a few minutes, vote on the clearest paths, then deliver a
                decision brief. Edit the sample scenario below or paste your own.
              </>
            ) : (
              <>
                Timed panel session (about two to three minutes). Each advisor speaks in short turns, then
                the room votes and produces a structured brief. Closing synthesis uses the last{" "}
                {sessionClock?.synth_reserve_sec ?? 30}s of the session clock.
              </>
            )}
          </p>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-2 sm:flex-row sm:items-center sm:gap-4">
          {!isGuest && <span className="text-xs text-[var(--muted)]">{user.username}</span>}
          <button
            type="button"
            onClick={() => {
              logout();
              router.replace(isGuest ? "/" : "/login");
            }}
            className="text-sm text-[var(--muted)] hover:text-[var(--foreground)]"
          >
            {isGuest ? "End demo" : "Log out"}
          </button>
          <Link href="/" className="text-sm text-[var(--muted)] hover:text-[var(--foreground)]">
            Home
          </Link>
        </div>
      </header>

      {/* Mobile: chamber → history → form → debate. Desktop: chamber+timer | history; debate | form */}
      <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-hidden lg:grid lg:min-h-0 lg:grid-cols-[minmax(0,1fr)_minmax(320px,440px)] lg:grid-rows-[auto_minmax(0,1fr)] lg:gap-6">
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

        {/* Row 1 col 2 — History (registered users only; demo sessions are ephemeral) */}
        {!isGuest && (
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
          {historyError && (
            <p className="shrink-0 border-b border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-200">
              {historyError}
            </p>
          )}
          <nav className="min-h-0 flex-1 overflow-x-auto overflow-y-auto px-2 py-2 lg:px-3">
            <ul className="flex flex-row gap-2 lg:flex-col lg:gap-1.5">
              {debateHistory.map((d) => (
                <li
                  key={d.id}
                  className="flex max-w-[200px] shrink-0 items-stretch gap-1 lg:max-w-none"
                >
                  <button
                    type="button"
                    onClick={() => setSelectedArchiveId(d.id)}
                    className={`min-w-0 flex-1 rounded-lg px-2.5 py-2 text-left text-xs transition-colors ${
                      selectedArchiveId === d.id
                        ? "bg-[var(--accent)]/20 text-[var(--foreground)]"
                        : "text-[var(--muted)] hover:bg-white/5 hover:text-[var(--foreground)]"
                    }`}
                  >
                    <span className="block text-[10px] uppercase tracking-wide text-[var(--muted)]">
                      {formatSavedAt(d.savedAt)}
                      {d.session_mode || d.debate_mode ? (
                        <span className="ml-1.5 normal-case text-[var(--accent)]">
                          · {(d.session_mode ?? d.debate_mode) === "swarm" ? "swarm" : "classic"}
                        </span>
                      ) : null}
                    </span>
                    <span className="mt-0.5 line-clamp-2 break-words leading-snug">
                      {previewContext(d.context, 72)}
                    </span>
                  </button>
                  <button
                    type="button"
                    aria-label="Delete this saved session"
                    title="Delete from history"
                    onClick={(e) => {
                      e.stopPropagation();
                      void handleDeleteArchive(d);
                    }}
                    className="shrink-0 rounded-lg px-1.5 text-[var(--muted)] transition-colors hover:bg-red-500/15 hover:text-red-200"
                  >
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      className="h-4 w-4"
                      aria-hidden
                    >
                      <path d="M3 6h18" />
                      <path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6" />
                      <path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2" />
                      <line x1="10" x2="10" y1="11" y2="17" />
                      <line x1="14" x2="14" y1="11" y2="17" />
                    </svg>
                  </button>
                </li>
              ))}
            </ul>
          </nav>
        </section>
        )}

        {/* Row 2 col 1 — Debate transcript (full width of column) */}
        <section
          className="order-4 flex min-h-[min(42vh,360px)] min-w-0 flex-col overflow-hidden rounded-xl border border-white/10 bg-[var(--card)]/30 lg:col-start-1 lg:row-start-2 lg:min-h-0 lg:self-stretch"
          aria-label="Debate transcript"
        >
          <div className="flex shrink-0 flex-wrap items-center justify-end gap-2 border-b border-white/10 px-3 py-2">
            <button
              type="button"
              onClick={handleExportMarkdown}
              disabled={!canExportMarkdown}
              title={
                canExportMarkdown
                  ? "Download this session as a Markdown file"
                  : "Run a session or open History to export"
              }
              className="rounded-lg border border-white/15 px-3 py-1.5 text-xs font-medium text-[var(--foreground)] hover:bg-white/5 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Export Markdown
            </button>
          </div>
          <DebateTranscript
            error={displayError}
            currentAgent={selectedArchive ? null : currentAgent}
            running={selectedArchive ? false : running}
            turns={displayTurns}
            voteOptions={displayVoteOptions}
            voteTally={displayVoteTally}
            report={displayReport}
            chiefSynthPending={selectedArchive ? false : chiefSynthPending}
            environmentPeek={displayEnvironmentPeek}
            hideTechnical={isGuest}
            runId={selectedArchive ? null : runId}
            debateScrollRef={debateScrollRef}
          />
        </section>

        {/* Row 2 col 2 — Context & controls */}
        <section
          className={`order-3 flex min-h-0 flex-col gap-4 overflow-y-auto lg:col-start-2 lg:max-h-full lg:self-stretch ${
            isGuest ? "lg:row-start-1" : "lg:row-start-2"
          }`}
        >
          <div className="flex shrink-0 flex-col gap-3 rounded-xl border border-white/10 bg-[var(--card)]/40 p-4">
            <div className="flex w-full flex-col gap-2">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <span className="text-sm font-medium">Context</span>
                <span
                  className={
                    context.length > MAX_CONTEXT_CHARS * 0.9
                      ? "text-xs font-medium text-amber-400"
                      : "text-xs text-[var(--muted)]"
                  }
                >
                  {context.length.toLocaleString()} / {MAX_CONTEXT_CHARS.toLocaleString()} characters
                </span>
              </div>
              <input
                ref={contextFileInputRef}
                type="file"
                accept=".txt,.md,.markdown,.pdf,text/plain,text/markdown,application/pdf"
                className="sr-only"
                aria-label="Attach context file"
                onChange={onContextFileChange}
                disabled={running}
              />
              <div className="flex flex-wrap items-center gap-3 text-xs">
                <button
                  type="button"
                  onClick={() => contextFileInputRef.current?.click()}
                  disabled={running}
                  className="rounded-lg border border-white/15 px-2.5 py-1.5 font-medium text-[var(--foreground)] hover:bg-white/5 disabled:opacity-40"
                >
                  Attach .txt / .md / .pdf
                </button>
                <label className="flex cursor-pointer items-center gap-1.5 text-[var(--muted)]">
                  <input
                    type="radio"
                    name="contextAttachMode"
                    checked={contextAttachMode === "append"}
                    onChange={() => setContextAttachMode("append")}
                    disabled={running}
                    className="border-white/20"
                  />
                  Append
                </label>
                <label className="flex cursor-pointer items-center gap-1.5 text-[var(--muted)]">
                  <input
                    type="radio"
                    name="contextAttachMode"
                    checked={contextAttachMode === "replace"}
                    onChange={() => setContextAttachMode("replace")}
                    disabled={running}
                    className="border-white/20"
                  />
                  Replace
                </label>
              </div>
              {contextFileMessage ? (
                <p className="text-xs text-[var(--muted)]">{contextFileMessage}</p>
              ) : null}
              <textarea
                rows={4}
                className="min-h-[5.5rem] w-full resize-y rounded-lg border border-white/10 bg-[var(--card)] p-2.5 text-sm outline-none ring-[var(--accent)] focus:ring-2"
                placeholder="Describe the decision, constraints, and what a good outcome looks like…"
                value={context}
                onChange={(e) => {
                  const v = e.target.value;
                  setContext(
                    v.length > MAX_CONTEXT_CHARS ? v.slice(0, MAX_CONTEXT_CHARS) : v,
                  );
                }}
                disabled={running}
              />
            </div>

            <div className="flex flex-wrap items-end gap-4">
              {!isGuest && (
                <div className="flex min-w-[min(100%,14rem)] flex-col gap-1">
                  <label htmlFor="session-mode" className="text-xs font-medium text-[var(--muted)]">
                    Session mode
                  </label>
                  <select
                    id="session-mode"
                    value={sessionMode}
                    onChange={(e) => setSessionMode(e.target.value as SessionModeChoice)}
                    disabled={running}
                    className="rounded-lg border border-[var(--border)] bg-[var(--card)] px-2.5 py-2 text-sm text-[var(--foreground)] outline-none ring-[var(--accent)] focus:ring-2 disabled:opacity-40"
                  >
                    <option value="classic">Classic — dialogue with interjections</option>
                    <option value="swarm">Structured panel turns</option>
                  </select>
                </div>
              )}
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

export default function DecisionRoomPage() {
  return (
    <Suspense
      fallback={
        <main className="flex min-h-screen flex-col items-center justify-center p-8">
          <p className="text-sm text-[var(--muted)]">Loading…</p>
        </main>
      }
    >
      <DecisionRoomContent />
    </Suspense>
  );
}
