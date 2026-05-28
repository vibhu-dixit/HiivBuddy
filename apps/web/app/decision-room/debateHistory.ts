import type { Turn } from "./debateTypes";

export type StoredVoteTally = {
  tallies: Record<string, number>;
  votes: { agent_id: string; name: string; option_id: string; rationale?: string }[];
  consensus_reached: boolean;
  winning_option_id: string | null;
  winning_title: string;
  threshold: number;
};

export type StoredDebate = {
  id: string;
  savedAt: string;
  context: string;
  model: string;
  session_duration_sec: number;
  consensus_threshold: number;
  enable_interjections: boolean;
  session_mode?: "classic" | "swarm";
  /** @deprecated legacy localStorage entries */
  debate_mode?: "classic" | "swarm";
  track_environment?: boolean;
  synth_env_snapshot?: boolean;
  turns: Turn[];
  voteOptions: { id: string; title: string }[] | null;
  voteTally: StoredVoteTally | null;
  report: {
    summary: string;
    ranked_options: { title: string; score: number; rationale: string }[];
    risks: string[];
    next_steps: string[];
    env_snapshot?: unknown;
  } | null;
  error: string | null;
  /** Server-side SQLite row id when the API persisted this session */
  run_id?: number;
};

const MAX_ITEMS = 60;

export function debateStorageKey(userId: number): string {
  return `hiivbuddy-decision-debates-v1-u${userId}`;
}

function loadRaw(userId: number): StoredDebate[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(debateStorageKey(userId));
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed as StoredDebate[];
  } catch {
    return [];
  }
}

export function loadDebates(userId: number): StoredDebate[] {
  return loadRaw(userId).sort(
    (a, b) => new Date(b.savedAt).getTime() - new Date(a.savedAt).getTime(),
  );
}

export function appendDebate(userId: number, entry: StoredDebate): void {
  if (typeof window === "undefined") return;
  const prev = loadRaw(userId);
  const next = [entry, ...prev.filter((d) => d.id !== entry.id)].slice(0, MAX_ITEMS);
  localStorage.setItem(debateStorageKey(userId), JSON.stringify(next));
}

export function clearDebatesForUser(userId: number): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem(debateStorageKey(userId));
}

export function removeDebate(userId: number, id: string): void {
  if (typeof window === "undefined") return;
  const next = loadRaw(userId).filter((d) => d.id !== id);
  localStorage.setItem(debateStorageKey(userId), JSON.stringify(next));
}
