import { LANDING_COPY } from "./landingCopy";
import { SplitSection } from "./SplitSection";
import { WireframeStepArt } from "./illustrations/WireframeStepArt";

const STEP_VARIANTS = ["describe", "deliberate", "decide"] as const;

export function HowItWorks() {
  const { howItWorks } = LANDING_COPY;

  return (
    <section className="landing-hero border-y border-white/10 bg-[#0a0e14] py-20 lg:py-24 text-[var(--landing-hero-fg)]">
      <SplitSection
        className="[&_h2]:text-[var(--landing-hero-fg)] [&_.split-desc]:text-[var(--landing-hero-muted)]"
        eyebrow={howItWorks.eyebrow}
        title={howItWorks.title}
        description={howItWorks.description}
        visual={
          <ol className="w-full max-w-md space-y-4">
            {howItWorks.steps.map((s, i) => (
              <li
                key={s.fig}
                className="flex gap-4 rounded-xl border border-white/10 bg-white/[0.04] p-4 text-left backdrop-blur-sm transition-colors hover:border-teal-500/30 hover:bg-white/[0.06]"
              >
                <WireframeStepArt
                  variant={STEP_VARIANTS[i]}
                  className="h-20 w-20 shrink-0 opacity-90"
                />
                <div className="min-w-0 pt-0.5">
                  <p className="text-[10px] font-semibold uppercase tracking-widest text-teal-400/90">
                    {s.fig}
                  </p>
                  <h3 className="mt-1 text-base font-semibold text-[var(--landing-hero-fg)]">
                    {s.title}
                  </h3>
                  <p className="split-desc mt-1.5 text-sm leading-relaxed text-[var(--landing-hero-muted)]">
                    {s.body}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        }
        visualClassName="lg:justify-end"
      />
    </section>
  );
}
