import type { StoredVoteTally } from "./debateHistory";
import type { Turn } from "./debateTypes";
import { isTurnVisibleToUser, sanitizeDebateTurnText } from "./displayDebateText";

const esc = (s: string) => s.replace(/\|/g, "\\|").replace(/\n/g, " ");

type VoteOpts = { id: string; title: string }[] | null;

type Report = {
  summary: string;
  ranked_options: { title: string; score: number; rationale: string }[];
  risks: string[];
  next_steps: string[];
} | null;

export type SessionExportInput = {
  context: string;
  model: string;
  session_duration_sec: number;
  consensus_threshold: number;
  enable_interjections: boolean;
  session_mode?: "classic" | "swarm";
  debate_mode?: "classic" | "swarm";
  track_environment?: boolean;
  synth_env_snapshot?: boolean;
  savedAt?: string;
  turns: Turn[];
  voteOptions: VoteOpts;
  voteTally: StoredVoteTally | null;
  report: (Report & { env_snapshot?: unknown }) | null;
  error: string | null;
  runId?: number | null;
};

export function buildSessionMarkdown(s: SessionExportInput): string {
  const lines: string[] = [];
  lines.push("# Hiiv — Decision session export");
  lines.push("");
  if (s.savedAt) {
    lines.push(`- **Saved:** ${s.savedAt}`);
  }
  if (s.runId != null) {
    lines.push(`- **Run ID:** ${s.runId}`);
  }
  lines.push(
    `- **Model:** ${esc(s.model.trim() || "Server default (API LLM_DEFAULT_MODEL / tier env)")}`,
  );
  lines.push(`- **Session (sec):** ${s.session_duration_sec}`);
  lines.push(`- **Consensus threshold:** ${s.consensus_threshold}`);
  lines.push(`- **Parallel interjections:** ${s.enable_interjections ? "yes" : "no"}`);
  const mode = s.session_mode ?? s.debate_mode;
  lines.push(`- **Session mode:** ${mode ?? "(unspecified)"}`);
  if (s.track_environment) {
    lines.push(`- **Track environment:** yes`);
  }
  if (s.synth_env_snapshot) {
    lines.push(`- **Synthesizer env snapshot:** yes`);
  }
  lines.push("");
  lines.push("## Context");
  lines.push("");
  lines.push(s.context.trim() || "_(empty)_");
  lines.push("");

  if (s.error) {
    lines.push("## Error");
    lines.push("");
    lines.push(s.error);
    lines.push("");
  }

  if (s.voteOptions && s.voteOptions.length > 0) {
    lines.push("## Vote options");
    lines.push("");
    for (const o of s.voteOptions) {
      lines.push(`- **${o.id}:** ${o.title}`);
    }
    lines.push("");
  }

  lines.push("## Debate");
  lines.push("");
  if (s.turns.length === 0) {
    lines.push("_(no turns)_");
    lines.push("");
  } else {
    let lastTurn = -1;
    for (const t of s.turns) {
      if (t.kind !== "interjection" && !isTurnVisibleToUser(t.text ?? "")) continue;
      const body =
        t.kind === "interjection"
          ? t.text.trim()
          : sanitizeDebateTurnText(t.text ?? "").text.trim();
      if (!body) continue;
      if (t.turn !== lastTurn) {
        if (lastTurn >= 0) lines.push("");
        lines.push(`### Turn ${t.turn}`);
        lastTurn = t.turn;
      }
      const who =
        t.kind === "interjection" && t.targetName
          ? `${t.name} (interjects → ${t.targetName})`
          : t.name;
      lines.push(`**${who}**`);
      lines.push("");
      lines.push(body);
      lines.push("");
    }
  }

  if (s.voteTally) {
    lines.push("## Vote tally");
    lines.push("");
    lines.push(
      `Consensus: **${s.voteTally.consensus_reached ? "yes" : "no"}** (threshold ${s.voteTally.threshold})`,
    );
    if (s.voteTally.winning_option_id != null && s.voteTally.consensus_reached) {
      lines.push(`Winner: **${esc(s.voteTally.winning_title || s.voteTally.winning_option_id)}**`);
    }
    lines.push("");
    lines.push("| Option | Votes |");
    lines.push("| --- | --- |");
    for (const [id, n] of Object.entries(s.voteTally.tallies).sort((a, b) =>
      a[0].localeCompare(b[0], undefined, { numeric: true }),
    )) {
      lines.push(`| ${id} | ${n} |`);
    }
    lines.push("");
    for (const v of s.voteTally.votes) {
      lines.push(`- **${v.name}** → ${v.option_id}${v.rationale ? ` — ${v.rationale}` : ""}`);
    }
    lines.push("");
  }

  if (s.report) {
    lines.push("## Chief Synthesizer — report");
    lines.push("");
    lines.push(s.report.summary);
    lines.push("");
    lines.push("### Ranked options");
    lines.push("");
    for (const o of s.report.ranked_options) {
      const title = o.title.replace(/\*/g, "·");
      lines.push(`- **${title}** (${(o.score * 100).toFixed(0)}%): ${o.rationale.replace(/\*/g, "·")}`);
    }
    lines.push("");
    lines.push("### Risks");
    lines.push("");
    for (const r of s.report.risks) {
      lines.push(`- ${r}`);
    }
    lines.push("");
    lines.push("### Next steps");
    lines.push("");
    for (const n of s.report.next_steps) {
      lines.push(`- ${n}`);
    }
    lines.push("");
    const snap = s.report.env_snapshot;
    if (snap != null && typeof snap === "object") {
      lines.push("### Environment snapshot (JSON)");
      lines.push("");
      lines.push("```json");
      lines.push(JSON.stringify(snap, null, 2));
      lines.push("```");
      lines.push("");
    }
  }

  return lines.join("\n").trim() + "\n";
}

export function downloadMarkdownFile(content: string, basename: string): void {
  const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = basename.endsWith(".md") ? basename : `${basename}.md`;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
