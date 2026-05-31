/** Panel roles shown during room setup — aligned with landing PANEL_MEMBERS / API agent ids. */
export const PANEL_MEMBER_ROLES: {
  id: string;
  name: string;
  role: string;
}[] = [
  {
    id: "optimist",
    name: "Optimist",
    role: "Champions upside, momentum, and the case for moving.",
  },
  {
    id: "devils_advocate",
    name: "Skeptic",
    role: "Tests whether the story holds and what happens if you are wrong.",
  },
  {
    id: "data_analyst",
    name: "Analyst",
    role: "Pulls the debate back to numbers, timelines, and tradeoffs.",
  },
  {
    id: "risk_guru",
    name: "Risk lead",
    role: "Maps downside, second-order effects, and failure modes.",
  },
  {
    id: "ethical_guardian",
    name: "Ethics voice",
    role: "Checks fairness to customers, team, and partners.",
  },
];
