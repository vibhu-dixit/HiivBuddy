"use client";

import { useId } from "react";

import { PANEL_MEMBERS } from "../landingCopy";
import { PERSONA_SVG_COLORS } from "../personaStyles";

type ChamberRingIllustrationProps = {
  activeIndex: number | null;
  onActiveIndexChange: (index: number | null) => void;
  className?: string;
};

/** Interactive circular panel layout with glow, orbits, and hover sync. */
export function ChamberRingIllustration({
  activeIndex: active,
  onActiveIndexChange: setActive,
  className = "",
}: ChamberRingIllustrationProps) {
  const uid = useId().replace(/:/g, "");

  const count = PANEL_MEMBERS.length;
  const radius = 132;
  const cx = 200;
  const cy = 200;

  return (
    <div className={`relative flex w-full max-w-md justify-center lg:max-w-lg ${className}`}>
      <div
        className="absolute left-1/2 top-1/2 h-64 w-64 -translate-x-1/2 -translate-y-1/2 rounded-full bg-[var(--accent)]/15 blur-3xl transition-opacity duration-500"
        style={{ opacity: active !== null ? 0.6 : 0.4 }}
        aria-hidden
      />

      <svg
        viewBox="0 0 400 400"
        className="relative h-auto w-full max-w-[400px] drop-shadow-md"
        role="img"
        aria-label="Five advisors connected to a central decision brief"
      >
        <defs>
          <linearGradient id={`${uid}-hub`} x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#14b8a6" />
            <stop offset="100%" stopColor="#0d9488" />
          </linearGradient>
          {PERSONA_SVG_COLORS.map((c, i) => (
            <linearGradient key={i} id={`${uid}-node-${i}`} x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor={c.fill} />
              <stop offset="100%" stopColor={c.fillDark} />
            </linearGradient>
          ))}
          <filter id={`${uid}-glow`} x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="4" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
          <filter id={`${uid}-soft`} x="-20%" y="-20%" width="140%" height="140%">
            <feGaussianBlur stdDeviation="2" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        <circle
          cx={cx}
          cy={cy}
          r={radius + 28}
          fill="none"
          stroke="#64748b"
          strokeOpacity="0.45"
          strokeWidth="2"
        />

        <circle
          cx={cx}
          cy={cy}
          r={radius - 8}
          fill="none"
          stroke="#0d9488"
          strokeOpacity="0.4"
          strokeWidth="1.5"
          className="panel-ring-pulse"
          style={{ transformOrigin: `${cx}px ${cy}px` }}
        />

        {PANEL_MEMBERS.map((m, i) => {
          const angle = (i / count) * Math.PI * 2 - Math.PI / 2;
          const x = cx + radius * Math.cos(angle);
          const y = cy + radius * Math.sin(angle);
          const isActive = active === i;
          const isDimmed = active !== null && !isActive;
          const palette = PERSONA_SVG_COLORS[i % PERSONA_SVG_COLORS.length];

          return (
            <g
              key={m.name}
              opacity={isDimmed ? 0.65 : 1}
              className="transition-opacity duration-300"
              onMouseEnter={() => setActive(i)}
              onMouseLeave={() => setActive(null)}
              style={{ cursor: "pointer" }}
            >
              <line
                x1={cx}
                y1={cy}
                x2={x}
                y2={y}
                stroke={palette.stroke}
                strokeOpacity={isActive ? 0.85 : 0.5}
                strokeWidth={isActive ? 2.5 : 1.75}
                strokeDasharray={isActive ? "none" : "5 4"}
              />
              {isActive && (
                <circle cx={x} cy={y} r="34" fill={palette.glow} filter={`url(#${uid}-soft)`} />
              )}
              <circle
                cx={x}
                cy={y}
                r={isActive ? 30 : 27}
                fill={`url(#${uid}-node-${i})`}
                stroke={palette.stroke}
                strokeWidth={2}
                className="transition-all duration-300"
              />
              <text
                x={x}
                y={y + 1}
                textAnchor="middle"
                dominantBaseline="middle"
                className="pointer-events-none select-none text-[14px] font-bold"
                fill="#ffffff"
              >
                {m.name.slice(0, 1)}
              </text>
              {isActive && (
                <text
                  x={x}
                  y={y + (y < cy ? -44 : 50)}
                  textAnchor="middle"
                  className="pointer-events-none text-[11px] font-semibold"
                  fill="#1a1a1f"
                >
                  {m.name}
                </text>
              )}
            </g>
          );
        })}

        <circle
          cx={cx}
          cy={cy}
          r={52}
          fill="var(--card)"
          stroke={`url(#${uid}-hub)`}
          strokeWidth="2.5"
          filter={active !== null ? `url(#${uid}-glow)` : undefined}
        />
        <circle cx={cx} cy={cy} r={42} fill="#ccfbf1" fillOpacity="0.85" />
        <text
          x={cx}
          y={cy - 4}
          textAnchor="middle"
          className="fill-[#0f766e] text-[11px] font-semibold uppercase tracking-wider"
        >
          Decision
        </text>
        <text
          x={cx}
          y={cy + 12}
          textAnchor="middle"
          className="fill-[#1a1a1f] text-[13px] font-bold"
        >
          Brief
        </text>
      </svg>
    </div>
  );
}
