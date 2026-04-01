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
  turns: Turn[];
  voteOptions: { id: string; title: string }[] | null;
  voteTally: StoredVoteTally | null;
  report: {
    summary: string;
    ranked_options: { title: string; score: number; rationale: string }[];
    risks: string[];
    next_steps: string[];
  } | null;
  error: string | null;
};

const STORAGE_KEY = "hiivbuddy-decision-debates-v1";
const MAX_ITEMS = 60;

function loadRaw(): StoredDebate[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) return [];
    return parsed as StoredDebate[];
  } catch {
    return [];
  }
}

export function loadDebates(): StoredDebate[] {
  return loadRaw().sort(
    (a, b) => new Date(b.savedAt).getTime() - new Date(a.savedAt).getTime(),
  );
}

export function appendDebate(entry: StoredDebate): void {
  if (typeof window === "undefined") return;
  const prev = loadRaw();
  const next = [entry, ...prev.filter((d) => d.id !== entry.id)].slice(0, MAX_ITEMS);
  localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
}
