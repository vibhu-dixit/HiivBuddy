/** Centralized landing page copy — GTM voice, SEO-friendly, no product jargon. */

export const LANDING_COPY = {
  contact: {
    href: "mailto:vibhu.dixit02@gmail.com?subject=Hiiv%20pricing&body=Hi%20—%20I%E2%80%99d%20like%20to%20learn%20about%20pricing%20for%20Hiiv.%0A%0AName:%0ACompany:%0AUse%20case:%0A",
    label: "Contact for pricing",
  },
  meta: {
    title: "Hiiv — Decision support for founders",
    description:
      "Run a focused advisory session on any business decision. Five perspectives debate, vote, and deliver a decision brief you can act on—built for founders and operators.",
  },

  hero: {
    eyebrow: "Decision support for founders",
    headline: "Make the call with confidence—",
    headlineAccent: "not guesswork",
    subhead:
      "When the stakes are high, one opinion is not enough. Hiiv runs a short advisory session on your real decision and hands you a written brief: ranked options, risks, and next steps.",
    deliverable:
      "About three minutes per session. Export a summary when you are ready to share it with your team or board.",
    ctaPrimary: "Try demo",
    ctaSecondary: "Contact for pricing",
    ctaNote: "Free guest demo. No credit card. Contact us when you’re ready to unlock accounts and history.",
  },

  tagline: {
    main: "Founders make better calls when the room pushes back.",
    chips: ["Founders", "Operators", "Product leaders", "Strategy"],
  },

  howItWorks: {
    eyebrow: "How it works",
    title: "From messy question to clear decision",
    description:
      "You bring the situation. Hiiv runs a timed working session and leaves you with something you can forward—not a wall of chat text.",
    steps: [
      {
        fig: "Step 1",
        title: "Describe the decision",
        body: "Share context, constraints, and what “good” looks like. Add a PDF or notes if you have them. Most founders spend two to five minutes here.",
      },
      {
        fig: "Step 2",
        title: "Let the room work it",
        body: "Five viewpoints challenge your options in a focused session—roughly three minutes. You watch the debate unfold; they have to commit to a point of view.",
      },
      {
        fig: "Step 3",
        title: "Leave with a brief",
        body: "You get ranked paths forward, the main risks, and concrete next steps—formatted so you can act this week or share with stakeholders.",
      },
    ],
  },

  panel: {
    title: "Who sits in the room",
    description:
      "Each voice has a job: stretch your thinking, poke holes, and force a vote before you walk away. Hover to see who is who.",
  },

  useCases: {
    title: "Built for the decisions that keep you up at night",
    description:
      "If the wrong call costs runway, morale, or a key relationship, you want structured disagreement—not another blank doc.",
    audience: "Common with seed to Series B teams and solo founders",
  },

  cta: {
    title: "Ready to pressure-test your next decision?",
    description:
      "Start with a guest demo—no account required. Contact us for pricing when you’re ready to unlock saved history.",
    button: "Try demo",
  },

  tryDemoModal: {
    title: "Start a guest demo",
    description:
      "Quick verification, then you will land in the Decision Room with a sample scenario you can edit or replace.",
    cancel: "Cancel",
    confirm: "Open Decision Room",
    confirmBusy: "Opening…",
  },
} as const;

export const PANEL_MEMBERS = [
  {
    name: "Optimist",
    role: "Champions upside, momentum, and the case for moving. Pushes you to name what you gain if you commit.",
  },
  {
    name: "Skeptic",
    role: "Tests whether the story holds. Asks what evidence you are trusting—and what happens if you are wrong.",
  },
  {
    name: "Analyst",
    role: "Pulls the debate back to numbers, timelines, and tradeoffs. Keeps options comparable so you can choose.",
  },
  {
    name: "Risk lead",
    role: "Maps downside, second-order effects, and failure modes. Makes sure “bold” still has guardrails.",
  },
  {
    name: "Ethics voice",
    role: "Checks fairness to customers, team, and partners. Flags reputational and values risk before you sign.",
  },
] as const;

export const USE_CASES = [
  {
    title: "Ship now or cut scope",
    body: "Clarify whether speed, quality, or runway wins—and what you are willing to defer.",
  },
  {
    title: "Hire now or wait",
    body: "Compare cost, timing, and what slows down if you hold the line on headcount.",
  },
  {
    title: "Take the partnership or build",
    body: "Weigh speed to market, control, and dependency before you ink a deal.",
  },
  {
    title: "Raise funding or extend runway",
    body: "Surface dilution, control, and timing so the path matches how you want to run the company.",
  },
] as const;

export const DEMO_SAMPLE_CONTEXT = `We are a 12-person B2B SaaS company at $1.2M ARR. Our largest customer wants a custom integration that would tie up one engineer for about three months and push back our core roadmap.

Options we are weighing:
1) Build the integration to protect roughly $400k ARR
2) Offer a lighter workaround and protect the roadmap
3) Walk away and accept churn risk

Constraints: about 14 months of runway, a tired team after a hard quarter, and a hire-vs-contractor call in Q3 we cannot postpone.

A good outcome: one decision we can commit to this week, with risks spelled out and clear next steps for sales and product.`;
