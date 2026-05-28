import { LANDING_COPY } from "./landingCopy";
import { HeroBackground } from "./illustrations/HeroBackground";
import { ProductPreviewMock } from "./illustrations/ProductPreviewMock";
import { SplitSection } from "./SplitSection";

type HeroProps = {
  onTryDemo: () => void;
  demoBusy: boolean;
};

export function Hero({ onTryDemo, demoBusy }: HeroProps) {
  const { hero, contact } = LANDING_COPY;

  return (
    <section className="landing-hero relative overflow-hidden bg-[var(--landing-hero-bg)] text-[var(--landing-hero-fg)]">
      <HeroBackground />

      <div className="relative z-10 py-10 sm:py-14 lg:py-16">
        <SplitSection
          className="[&_h2]:text-[var(--landing-hero-fg)] [&_p]:text-[var(--landing-hero-muted)]"
          eyebrow={hero.eyebrow}
          visual={<ProductPreviewMock compact />}
          visualClassName="lg:justify-end"
        >
          <h1 className="font-serif text-4xl font-semibold leading-tight tracking-tight sm:text-5xl lg:text-[3.25rem]">
            {hero.headline}
            <span className="block bg-gradient-to-r from-teal-200 via-white to-teal-200 bg-clip-text text-transparent">
              {hero.headlineAccent}
            </span>
          </h1>
          <p className="mt-5 max-w-lg text-lg leading-relaxed text-[var(--landing-hero-muted)]">
            {hero.subhead}
          </p>
          <p className="mt-3 max-w-lg text-sm text-[var(--landing-hero-muted)]">{hero.deliverable}</p>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={onTryDemo}
              disabled={demoBusy}
              className="min-h-[44px] rounded-lg bg-[var(--accent)] px-6 py-3 text-sm font-semibold text-white shadow-lg shadow-teal-900/40 hover:bg-[var(--accent-hover)] disabled:opacity-50"
            >
              {demoBusy ? "Starting…" : hero.ctaPrimary}
            </button>
            <a
              href={contact.href}
              target="_blank"
              rel="noreferrer"
              className="min-h-[44px] rounded-lg border border-white/20 bg-white/5 px-6 py-3 text-sm font-semibold text-white backdrop-blur-sm hover:bg-white/10"
            >
              {contact.label}
            </a>
          </div>
          <p className="mt-4 text-sm text-[var(--landing-hero-muted)]">{hero.ctaNote}</p>
        </SplitSection>
      </div>

      <div className="relative z-10 h-12 bg-gradient-to-b from-transparent to-[var(--background)] sm:h-16" />
    </section>
  );
}
