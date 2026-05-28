import { LANDING_COPY } from "./landingCopy";
import { SplitSection } from "./SplitSection";
import { CtaDecorIllustration } from "./illustrations/CtaDecorIllustration";

type CtaBandProps = {
  onTryDemo: () => void;
  demoBusy: boolean;
};

export function CtaBand({ onTryDemo, demoBusy }: CtaBandProps) {
  const { cta } = LANDING_COPY;

  return (
    <section className="relative overflow-hidden border-t border-[var(--border)] py-20 lg:py-24">
      <div
        className="absolute inset-0 bg-gradient-to-br from-[var(--accent-muted)]/60 via-[var(--background)] to-indigo-50/50"
        aria-hidden
      />
      <div
        className="absolute -right-20 top-1/2 h-72 w-72 -translate-y-1/2 rounded-full bg-[var(--accent)]/10 blur-3xl"
        aria-hidden
      />
      <div className="relative">
        <SplitSection
          title={cta.title}
          description={cta.description}
          visual={
            <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-8 shadow-sm">
              <CtaDecorIllustration />
            </div>
          }
          visualClassName="lg:justify-end"
        >
          <button
            type="button"
            onClick={onTryDemo}
            disabled={demoBusy}
            className="min-h-[48px] rounded-lg bg-[var(--accent)] px-10 py-3 text-sm font-semibold text-white shadow-lg shadow-teal-900/20 hover:bg-[var(--accent-hover)] disabled:opacity-50"
          >
            {demoBusy ? "Starting…" : cta.button}
          </button>
        </SplitSection>
      </div>
    </section>
  );
}
