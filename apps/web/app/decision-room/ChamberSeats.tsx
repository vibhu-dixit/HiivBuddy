"use client";

import Image from "next/image";
import type { ReactNode } from "react";
import { useMemo } from "react";

import { DEBATE_AGENTS } from "./debateAgents";

export { DEBATE_AGENTS };

/** Maximum seats per row; extra agents wrap into balanced rows (e.g. 6 → 3+3, 20 → 5×4). */
export const DEFAULT_MAX_SEATS_PER_ROW = 5;

export const CHIEF_ICON = "/images/chief_synthesizer_icon.png";
export const AGENT_ICON = "/images/agent_icon.png";

/**
 * Split a list into rows of at most `maxPerRow` items, with counts as even as possible.
 */
export function agentsIntoRows<T>(items: T[], maxPerRow: number): T[][] {
  const n = items.length;
  if (n === 0) return [];
  const numRows = Math.ceil(n / maxPerRow);
  const baseSize = Math.floor(n / numRows);
  const widerRows = n % numRows;
  const rows: T[][] = [];
  let start = 0;
  for (let r = 0; r < numRows; r++) {
    const sz = r < widerRows ? baseSize + 1 : baseSize;
    rows.push(items.slice(start, start + sz));
    start += sz;
  }
  return rows;
}

type ChamberSeatsProps = {
  synthesizerActive: boolean;
  /** Which agent shows the green speaking ring (stream / flash / floor). */
  agentHighlightId: string | null;
  maxSeatsPerRow?: number;
  /** e.g. debate-phase countdown, anchored bottom-right inside the chamber card */
  bottomRight?: ReactNode;
};

/** Light disc behind PNGs so dark marks read on the dark chamber UI. */
function avatarDiscClass(variant: "chief" | "advisor") {
  if (variant === "chief") {
    return "bg-gradient-to-br from-indigo-50 via-white to-violet-100 ring-1 ring-indigo-950/10";
  }
  return "bg-gradient-to-br from-zinc-50 via-white to-zinc-200 ring-1 ring-zinc-900/10";
}

function AvatarSeat({
  src,
  alt,
  label,
  subtitle,
  speaking,
  size,
  variant,
}: {
  src: string;
  alt: string;
  label: string;
  subtitle?: string;
  speaking: boolean;
  size: number;
  variant: "chief" | "advisor";
}) {
  return (
    <div className="flex flex-col items-center gap-1.5 text-center">
      <div
        className={`rounded-full p-0.5 transition-[box-shadow,ring] duration-150 ${
          speaking
            ? "ring-2 ring-green-500 ring-offset-2 ring-offset-[var(--background)] shadow-[0_0_12px_rgba(34,197,94,0.45)]"
            : "ring-2 ring-white/10 ring-offset-2 ring-offset-[var(--background)]"
        }`}
      >
        <div
          className={`rounded-full p-1.5 shadow-[inset_0_1px_0_rgba(255,255,255,0.75)] ${avatarDiscClass(variant)}`}
        >
          <Image
            src={src}
            alt={alt}
            width={size}
            height={size}
            className="rounded-full object-contain"
            sizes={`${size}px`}
          />
        </div>
      </div>
      <span className="max-w-[7rem] text-[11px] font-medium leading-tight text-[var(--foreground)]">
        {label}
      </span>
      {subtitle ? (
        <span className="max-w-[7rem] text-[9px] leading-tight text-[var(--muted)]">{subtitle}</span>
      ) : null}
    </div>
  );
}

export function ChamberSeats({
  synthesizerActive,
  agentHighlightId,
  maxSeatsPerRow = DEFAULT_MAX_SEATS_PER_ROW,
  bottomRight,
}: ChamberSeatsProps) {
  const rows = useMemo(
    () => agentsIntoRows(DEBATE_AGENTS, maxSeatsPerRow),
    [maxSeatsPerRow],
  );

  return (
    <div
      className={`relative flex min-h-[280px] flex-col rounded-2xl border border-white/10 bg-[var(--card)]/50 p-5 ${
        bottomRight != null ? "pb-14 sm:pb-16" : ""
      }`}
      aria-label="Chief Synthesizer and advisor seats"
    >
      {bottomRight != null && (
        <div className="pointer-events-none absolute bottom-3 right-3 z-10 max-w-[min(100%,18rem)] sm:max-w-[20rem]">
          <div className="pointer-events-auto">{bottomRight}</div>
        </div>
      )}
      <div className="flex justify-center pb-4">
        <AvatarSeat
          src={CHIEF_ICON}
          alt="Chief Synthesizer"
          label="Chief Synthesizer"
          subtitle="Final report"
          speaking={synthesizerActive}
          size={64}
          variant="chief"
        />
      </div>
      <div className="flex flex-col gap-4">
        {rows.map((row, ri) => (
          <div key={ri} className="flex flex-wrap justify-center gap-4">
            {row.map((a) => (
              <AvatarSeat
                key={a.id}
                src={AGENT_ICON}
                alt={a.label}
                label={a.label}
                speaking={agentHighlightId === a.id}
                size={52}
                variant="advisor"
              />
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
