/**
 * Debate agent roster. Ids must match `apps/api/app/debate/orchestrator.py` `AGENTS`.
 * Kept in a server-safe module so UI pieces need not import `ChamberSeats` (client).
 */
export const DEBATE_AGENTS: { id: string; label: string }[] = [
  { id: "optimist", label: "Optimist" },
  { id: "devils_advocate", label: "Devil's Advocate" },
  { id: "data_analyst", label: "Data Analyst" },
  { id: "risk_guru", label: "Risk Guru" },
  { id: "ethical_guardian", label: "Ethical Guardian" },
];
