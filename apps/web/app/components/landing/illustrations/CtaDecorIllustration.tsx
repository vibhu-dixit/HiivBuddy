/** Minimal chamber silhouette for CTA split section. */

export function CtaDecorIllustration() {
  const cx = 100;
  const cy = 100;
  const r = 72;
  const nodes = 5;

  return (
    <svg
      viewBox="0 0 200 200"
      className="h-auto w-full max-w-[220px] text-[var(--accent)]"
      aria-hidden
    >
      <circle
        cx={cx}
        cy={cy}
        r={r}
        fill="none"
        stroke="currentColor"
        strokeOpacity="0.2"
        strokeWidth="1"
        strokeDasharray="6 8"
      />
      <circle cx={cx} cy={cy} r="22" fill="var(--accent-muted)" stroke="currentColor" strokeOpacity="0.5" />
      {Array.from({ length: nodes }).map((_, i) => {
        const angle = (i / nodes) * Math.PI * 2 - Math.PI / 2;
        const x = cx + r * Math.cos(angle);
        const y = cy + r * Math.sin(angle);
        return (
          <g key={i}>
            <line x1={cx} y1={cy} x2={x} y2={y} stroke="currentColor" strokeOpacity="0.15" />
            <circle cx={x} cy={y} r="10" fill="var(--card)" stroke="currentColor" strokeOpacity="0.35" />
          </g>
        );
      })}
    </svg>
  );
}
