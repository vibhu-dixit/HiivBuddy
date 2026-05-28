"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { useAuth } from "./auth/AuthProvider";
import { LANDING_COPY } from "./components/landing/landingCopy";
import { CtaBand } from "./components/landing/CtaBand";
import { Hero } from "./components/landing/Hero";
import { HowItWorks } from "./components/landing/HowItWorks";
import { PanelSection } from "./components/landing/PanelSection";
import { SiteHeader } from "./components/landing/SiteHeader";
import { TryDemoModal } from "./components/landing/TryDemoModal";
import { UseCases } from "./components/landing/UseCases";

export default function LandingPage() {
  const router = useRouter();
  const { user, loginAsGuest } = useAuth();
  const [demoModalOpen, setDemoModalOpen] = useState(false);
  const [demoBusy, setDemoBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function handleTryDemoClick() {
    if (user) {
      router.push("/decision-room");
      return;
    }
    setError(null);
    setDemoModalOpen(true);
  }

  async function handleDemoConfirm(captchaToken: string) {
    setError(null);
    setDemoBusy(true);
    try {
      await loginAsGuest(captchaToken);
      setDemoModalOpen(false);
      router.push("/decision-room?demo=1");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start demo.");
    } finally {
      setDemoBusy(false);
    }
  }

  return (
    <div className="min-h-screen">
      <SiteHeader onTryDemo={handleTryDemoClick} demoBusy={demoBusy} />
      <div className="landing-hero bg-[var(--landing-hero-bg)] pt-[4.5rem]">
        <Hero onTryDemo={handleTryDemoClick} demoBusy={demoBusy} />
      </div>
      <section className="relative border-y border-[var(--border)] bg-[var(--card)] py-8">
        <div className="mx-auto flex max-w-6xl flex-col gap-4 px-6 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-lg font-medium text-[var(--foreground)]">
            {LANDING_COPY.tagline.main}
          </p>
          <div className="flex flex-wrap gap-3">
            {LANDING_COPY.tagline.chips.map((label) => (
              <span
                key={label}
                className="rounded-full border border-[var(--border)] bg-[var(--background)] px-3 py-1 text-xs font-semibold uppercase tracking-wide text-[var(--muted)]"
              >
                {label}
              </span>
            ))}
          </div>
        </div>
      </section>
      <HowItWorks />
      <PanelSection />
      <UseCases />
      <CtaBand onTryDemo={handleTryDemoClick} demoBusy={demoBusy} />
      {error && !demoModalOpen && (
        <p className="mx-auto max-w-md px-6 pb-8 text-center text-sm text-red-600">{error}</p>
      )}
      <TryDemoModal
        open={demoModalOpen}
        busy={demoBusy}
        error={error}
        onClose={() => {
          if (!demoBusy) {
            setDemoModalOpen(false);
            setError(null);
          }
        }}
        onConfirm={handleDemoConfirm}
      />
      <footer className="border-t border-[var(--border)] bg-[var(--card)] py-8">
        <div className="mx-auto flex max-w-6xl flex-col items-start justify-between gap-4 px-6 text-sm text-[var(--muted)] sm:flex-row sm:items-center">
          <span>© {new Date().getFullYear()} Hiiv</span>
          <div className="flex gap-4">
            <a
              href={LANDING_COPY.contact.href}
              target="_blank"
              rel="noreferrer"
              className="hover:text-[var(--foreground)]"
            >
              {LANDING_COPY.contact.label}
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
