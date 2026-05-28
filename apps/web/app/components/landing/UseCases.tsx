import { LANDING_COPY, USE_CASES } from "./landingCopy";
import { PERSONA_BADGE_STYLES } from "./personaStyles";
import { SplitSection } from "./SplitSection";

const ICONS = ["↗", "◎", "⇄", "◇"] as const;

export function UseCases() {
  const { useCases } = LANDING_COPY;

  return (
    <section className="border-t border-[var(--border)] bg-[var(--background)] py-20 lg:py-24">
      <SplitSection
        title={useCases.title}
        description={useCases.description}
        visual={
          <ul className="grid w-full max-w-lg gap-4 sm:grid-cols-2">
            {USE_CASES.map((c, i) => {
              const badge = PERSONA_BADGE_STYLES[i % PERSONA_BADGE_STYLES.length];
              return (
                <li
                  key={c.title}
                  className="group relative overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--card)] p-5 shadow-sm transition-all hover:-translate-y-0.5 hover:border-[var(--accent)]/25 hover:shadow-md"
                >
                  <div className="relative">
                    <span
                      className={`inline-flex h-10 w-10 items-center justify-center rounded-lg text-base font-bold text-white shadow-sm ${badge.gradient}`}
                      aria-hidden
                    >
                      {ICONS[i]}
                    </span>
                    <h3 className="mt-4 font-semibold text-[var(--foreground)]">{c.title}</h3>
                    <p className="mt-2 text-sm leading-relaxed text-[var(--muted)]">{c.body}</p>
                  </div>
                </li>
              );
            })}
          </ul>
        }
        visualClassName="lg:justify-end"
      >
        <p className="text-sm font-medium text-[var(--accent)]">{useCases.audience}</p>
      </SplitSection>
    </section>
  );
}
