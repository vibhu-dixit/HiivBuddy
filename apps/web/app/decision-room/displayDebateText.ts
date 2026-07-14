/** Strip swarm action markers and hide non-user-facing lines in the debate UI. */

const ACTION_PREFIX_RE =
  /^\((pass|propose_claim|utter|support_option|attack_option|link)\)\s*/i;

const PASS_ONLY_RE = /^\(pass\)\s*$/i;

/** Bare "option 1" style lines from support/attack without real speech */
const LOW_VALUE_OPTION_RE = /^option\s*\d+\s*$/i;

/** Internal claim-link shorthand (c3_2 → c1_1) */
const LINK_ONLY_RE = /^c\d+_\d+\s*(?:→|->)\s*c\d+_\d+\s*$/i;

export function sanitizeDebateTurnText(raw: string): { text: string; isPass: boolean } {
  const trimmed = (raw ?? "").trim();
  if (!trimmed || PASS_ONLY_RE.test(trimmed)) {
    return { text: "", isPass: true };
  }
  const text = trimmed.replace(ACTION_PREFIX_RE, "").trim();
  if (!text) {
    return { text: "", isPass: PASS_ONLY_RE.test(trimmed) };
  }
  return { text, isPass: false };
}

/** Whether this turn should appear in the transcript panel at all. */
export function isTurnVisibleToUser(raw: string): boolean {
  const { text, isPass } = sanitizeDebateTurnText(raw);
  if (isPass || !text) return false;
  if (LOW_VALUE_OPTION_RE.test(text)) return false;
  if (LINK_ONLY_RE.test(text)) return false;
  return true;
}
