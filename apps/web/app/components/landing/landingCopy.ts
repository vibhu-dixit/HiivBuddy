/** Centralized landing page copy — GTM voice, SEO-friendly, no product jargon. */

export const LANDING_COPY = {
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
      "Five AI advisors challenge your thinking, debate the trade-offs, and deliver a clear recommendation in under three minutes. Whether you're deciding to pivot, hire, raise prices, or raise funding, Hiiv helps you think like an experienced board—not a chatbot.",
    deliverable:
      "About three minutes per session. Export a summary when you are ready to share it with your team or board.",
    ctaPrimary: "Try demo",
    ctaNote: "Free guest demo. No credit card required.",
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
      "Start with a guest demo—no account required. Run a session and export your decision brief.",
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

  footer: {
    builtByLabel: "Built by",
    authorName: "Vibhu Dixit",
    githubUrl: "https://github.com/vibhu-dixit",
    linkedInUrl: "https://www.linkedin.com/in/vibhu-dixit-swe",
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

export const DEMO_SAMPLE_CONTEXT = `How do we build a product that customers actually love and will pay for?
And how do we survive long enough to scale it before running out of money?
`;
