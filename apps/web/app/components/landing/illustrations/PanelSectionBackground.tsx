/** Layered backdrop for the "Your panel" chamber section. */

export function PanelSectionBackground() {
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden>
      {/* Base wash */}
      <div className="absolute inset-0 bg-gradient-to-b from-[var(--accent-muted)]/30 via-[var(--background)] to-[var(--background)]" />

      {/* Central spotlight behind wheel */}
      <div className="absolute left-1/2 top-[38%] h-[min(520px,70vw)] w-[min(520px,90vw)] -translate-x-1/2 -translate-y-1/2 rounded-full bg-[radial-gradient(circle,rgba(13,148,136,0.14)_0%,rgba(99,102,241,0.06)_45%,transparent_70%)]" />

      {/* Soft color blobs */}
      <div className="panel-blob-drift absolute -left-24 top-20 h-72 w-72 rounded-full bg-teal-400/15 blur-3xl" />
      <div className="panel-blob-drift-reverse absolute -right-16 top-32 h-80 w-80 rounded-full bg-indigo-400/12 blur-3xl" />
      <div className="absolute bottom-0 left-1/2 h-48 w-[120%] -translate-x-1/2 bg-gradient-to-t from-[var(--accent-muted)]/25 to-transparent" />

      {/* Dot grid */}
      <div
        className="absolute inset-0 opacity-[0.35]"
        style={{
          backgroundImage: "radial-gradient(circle, rgba(13,148,136,0.35) 1px, transparent 1px)",
          backgroundSize: "28px 28px",
          maskImage: "radial-gradient(ellipse 70% 55% at 50% 42%, black 20%, transparent 75%)",
          WebkitMaskImage:
            "radial-gradient(ellipse 70% 55% at 50% 42%, black 20%, transparent 75%)",
        }}
      />

      {/* Corner wire arcs */}
      <svg
        className="absolute left-0 top-0 h-full w-full text-[var(--accent)]"
        viewBox="0 0 1200 600"
        preserveAspectRatio="xMidYMid slice"
        fill="none"
      >
        <path
          d="M0 120 Q200 80 320 200 T480 80"
          stroke="currentColor"
          strokeOpacity="0.12"
          strokeWidth="1.5"
          className="landing-path-dash"
        />
        <path
          d="M1200 480 Q1000 520 880 400 T720 520"
          stroke="currentColor"
          strokeOpacity="0.1"
          strokeWidth="1.5"
          strokeDasharray="8 12"
        />
        <circle cx="180" cy="480" r="3" fill="currentColor" fillOpacity="0.2" />
        <circle cx="1020" cy="100" r="2" fill="currentColor" fillOpacity="0.15" />
      </svg>

      {/* Floor ellipse under wheel */}
      <div className="absolute left-1/2 top-[42%] h-8 w-[min(340px,85vw)] -translate-x-1/2 rounded-[100%] bg-[radial-gradient(ellipse,rgba(13,148,136,0.2)_0%,transparent_70%)] blur-sm" />
    </div>
  );
}
