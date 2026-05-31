"use client";

import Image from "next/image";
import { useMemo } from "react";

import { AGENT_ICON } from "./ChamberSeats";
import { PANEL_MEMBER_ROLES } from "./panelMemberCopy";

type Props = {
  phase: "connecting" | "preparing";
  activeAgentId: string | null;
};

export function RoomSetupPanel({ phase, activeAgentId }: Props) {
  const activeIndex = useMemo(() => {
    const i = PANEL_MEMBER_ROLES.findIndex((m) => m.id === activeAgentId);
    return i >= 0 ? i : 0;
  }, [activeAgentId]);

  const active = PANEL_MEMBER_ROLES[activeIndex] ?? PANEL_MEMBER_ROLES[0];

  return (
    <section
      className="flex min-h-[220px] flex-col items-center justify-center rounded-xl border border-[var(--border)] bg-[var(--card)]/80 px-4 py-6 sm:min-h-[260px] sm:px-6"
      aria-live="polite"
      aria-busy="true"
    >
      <p className="text-center text-xs font-medium uppercase tracking-wide text-[var(--muted)]">
        {phase === "connecting" ? "Setting up the room" : "Seating the panel"}
      </p>
      <h2 className="mt-1 text-center text-sm font-semibold text-[var(--foreground)]">
        {phase === "connecting"
          ? "Reading your brief…"
          : "Advisors are taking their seats"}
      </h2>

      <div className="relative mt-6 flex w-full max-w-sm flex-col items-center">
        <div
          key={active.id}
          className="room-setup-seat-enter flex w-full flex-col items-center text-center"
        >
          <div className="rounded-full bg-gradient-to-br from-zinc-50 via-white to-zinc-200 p-2 ring-2 ring-[var(--accent)]/40 ring-offset-2 ring-offset-[var(--card)]">
            <Image
              src={AGENT_ICON}
              alt=""
              width={56}
              height={56}
              className="rounded-full object-contain"
              aria-hidden
            />
          </div>
          <p className="mt-4 text-base font-semibold text-[var(--foreground)]">{active.name}</p>
          <p className="mt-2 max-w-[18rem] text-sm leading-relaxed text-[var(--muted)]">
            {active.role}
          </p>
          <p className="mt-3 text-xs text-[var(--accent)]">
            Seat {activeIndex + 1} of {PANEL_MEMBER_ROLES.length}
          </p>
        </div>
      </div>

      <div className="mt-6 flex items-center gap-2" aria-hidden>
        {PANEL_MEMBER_ROLES.map((member, i) => (
          <span
            key={member.id}
            className={`h-2 rounded-full transition-all duration-500 ${
              i === activeIndex
                ? "w-6 bg-[var(--accent)]"
                : i < activeIndex
                  ? "w-2 bg-[var(--accent)]/35"
                  : "w-2 bg-[var(--border)]"
            }`}
          />
        ))}
      </div>
    </section>
  );
}
