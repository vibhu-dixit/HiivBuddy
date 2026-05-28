/** Stylized Decision Room preview for the hero (no real screenshot needed). */

const ADVISORS = ["O", "S", "A", "R", "E"] as const;

type ProductPreviewMockProps = {
  compact?: boolean;
};

export function ProductPreviewMock({ compact = false }: ProductPreviewMockProps) {
  return (
    <div
      className={`landing-preview-rise relative w-full ${compact ? "max-w-xl" : "mx-auto mt-12 max-w-4xl px-4"}`}
    >      <div className="absolute -inset-4 rounded-3xl bg-[var(--accent)]/20 blur-2xl" aria-hidden />
      <div
        className={`relative overflow-hidden rounded-2xl border border-white/10 bg-[#16161c] shadow-2xl shadow-black/40 ring-1 ring-white/10 ${compact ? "max-h-[420px] overflow-y-auto" : ""}`}
      >
        {/* Window chrome */}
        <div className="flex items-center gap-2 border-b border-white/10 bg-[#1c1c24] px-4 py-2.5">
          <span className="h-2.5 w-2.5 rounded-full bg-red-400/80" />
          <span className="h-2.5 w-2.5 rounded-full bg-amber-400/80" />
          <span className="h-2.5 w-2.5 rounded-full bg-emerald-400/80" />
          <span className="ml-3 text-xs text-white/40">Decision Room — Hiiv</span>
        </div>

        <div className="grid gap-4 p-4 sm:grid-cols-[1fr_1.1fr] sm:p-5">
          {/* Chamber */}
          <div className="rounded-xl border border-white/10 bg-[#121218] p-4">
            <p className="text-[10px] font-medium uppercase tracking-wider text-white/35">
              Advisory chamber
            </p>
            <div className="mt-4 flex flex-wrap justify-center gap-3">
              {ADVISORS.map((letter, i) => (
                <div
                  key={letter}
                  className={`flex h-11 w-11 items-center justify-center rounded-full text-xs font-semibold transition-all ${
                    i === 2
                      ? "bg-emerald-500/20 text-emerald-300 ring-2 ring-emerald-400/60 ring-offset-2 ring-offset-[#121218]"
                      : "bg-white/5 text-white/70 ring-1 ring-white/10"
                  }`}
                >
                  {letter}
                </div>
              ))}
            </div>
            <div className="mt-4 flex justify-center">
              <div className="rounded-full bg-indigo-500/20 px-3 py-1 text-[10px] text-indigo-200 ring-1 ring-indigo-400/30">
                Chief Synthesizer
              </div>
            </div>
            <p className="mt-3 text-center text-[10px] tabular-nums text-white/40">
              Debate phase · <span className="text-white/80">2:14</span> left
            </p>
          </div>

          {/* Transcript + brief */}
          <div className="flex flex-col gap-3">
            <div className="rounded-xl border border-white/10 bg-[#121218] p-3">
              <p className="text-[10px] uppercase tracking-wider text-white/35">Live transcript</p>
              <div className="mt-2 space-y-2">
                <p className="text-[11px] leading-relaxed text-white/55">
                  <span className="text-teal-300/90">Skeptic:</span> The integration delays roadmap
                  by a quarter—have we priced that against churn risk?
                </p>
                <p className="text-[11px] leading-relaxed text-white/55">
                  <span className="text-violet-300/90">Analyst:</span> ARR at risk is $400k; build
                  cost is roughly 1.2 eng-months if scoped tightly.
                </p>
                <p className="landing-shimmer h-2 w-3/4 rounded bg-white/10" />
              </div>
            </div>
            <div className="rounded-xl border border-teal-500/20 bg-teal-950/30 p-3">
              <p className="text-[10px] font-medium uppercase tracking-wider text-teal-300/70">
                Decision brief
              </p>
              <ul className="mt-2 space-y-1 text-[11px] text-teal-100/80">
                <li>1. Lightweight workaround + success criteria (score 8.2)</li>
                <li>2. Full build with milestone gate (score 6.1)</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
