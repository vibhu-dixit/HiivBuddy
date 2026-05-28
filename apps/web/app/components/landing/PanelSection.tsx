"use client";

import { useState } from "react";

import { LANDING_COPY, PANEL_MEMBERS } from "./landingCopy";
import { PERSONA_BADGE_STYLES } from "./personaStyles";
import { SplitSection } from "./SplitSection";
import { ChamberRingIllustration } from "./illustrations/ChamberRingIllustration";
import { PanelSectionBackground } from "./illustrations/PanelSectionBackground";

export function PanelSection() {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const { panel } = LANDING_COPY;

  return (
    <section className="relative overflow-hidden py-20 lg:py-24">
      <PanelSectionBackground />

      <SplitSection
        reverse
        title={panel.title}
        description={panel.description}
        visual={
          <ChamberRingIllustration
            activeIndex={hoveredIndex}
            onActiveIndexChange={setHoveredIndex}
          />
        }
        visualClassName="lg:justify-start"
      >
        <ul className="space-y-3">
          {PANEL_MEMBERS.map((m, i) => {
            const style = PERSONA_BADGE_STYLES[i];
            const isActive = hoveredIndex === i;
            return (
              <li key={m.name}>
                <button
                  type="button"
                  onMouseEnter={() => setHoveredIndex(i)}
                  onMouseLeave={() => setHoveredIndex(null)}
                  onFocus={() => setHoveredIndex(i)}
                  onBlur={() => setHoveredIndex(null)}
                  className={`flex w-full items-start gap-4 rounded-xl border px-4 py-3.5 text-left shadow-sm transition-all ${
                    isActive
                      ? `border-[var(--accent)]/40 bg-[var(--card)] shadow-md ring-2 ${style.ring}`
                      : `${style.soft} hover:border-[var(--accent)]/25 hover:shadow-md`
                  }`}
                >
                  <span
                    className={`mt-0.5 flex h-11 w-11 shrink-0 items-center justify-center rounded-full text-sm font-bold text-white shadow-sm ${style.gradient} ${
                      isActive ? "scale-110 ring-2 ring-white/50" : ""
                    }`}
                    aria-hidden
                  >
                    {m.name.slice(0, 1)}
                  </span>
                  <span className="min-w-0">
                    <span className="block font-semibold text-[var(--foreground)]">{m.name}</span>
                    <span className="mt-1 block text-sm leading-snug text-[var(--muted)]">
                      {m.role}
                    </span>
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      </SplitSection>
    </section>
  );
}
