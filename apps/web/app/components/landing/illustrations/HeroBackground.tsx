/** Decorative hero backdrop — winding path + floating doodles (Notion-inspired). */

export function HeroBackground() {
  return (
    <div
      className="pointer-events-none absolute inset-0 overflow-hidden"
      aria-hidden
    >
      {/* Spotlight */}
      <div className="absolute left-1/2 top-0 h-[min(90vh,720px)] w-[min(140vw,900px)] -translate-x-1/2 -translate-y-1/4 rounded-full bg-[radial-gradient(ellipse_at_center,rgba(13,148,136,0.35)_0%,transparent_65%)]" />

      {/* Grid texture */}
      <div
        className="absolute inset-0 opacity-[0.07]"
        style={{
          backgroundImage: `
            linear-gradient(rgba(255,255,255,0.5) 1px, transparent 1px),
            linear-gradient(90deg, rgba(255,255,255,0.5) 1px, transparent 1px)
          `,
          backgroundSize: "48px 48px",
        }}
      />

      <svg
        className="absolute inset-0 h-full w-full"
        viewBox="0 0 1200 800"
        preserveAspectRatio="xMidYMid slice"
        fill="none"
      >
        <defs>
          <linearGradient id="pathGrad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stopColor="#0d9488" stopOpacity="0.2" />
            <stop offset="50%" stopColor="#5eead4" stopOpacity="0.55" />
            <stop offset="100%" stopColor="#0d9488" stopOpacity="0.2" />
          </linearGradient>
        </defs>

        {/* Conveyor / decision path */}
        <path
          d="M-40 420 C 180 380, 220 520, 400 480 S 700 340, 900 400 S 1100 560, 1240 440"
          stroke="url(#pathGrad)"
          strokeWidth="3"
          strokeLinecap="round"
          className="landing-path-dash"
        />
        <path
          d="M-40 430 C 180 390, 220 530, 400 490 S 700 350, 900 410 S 1100 570, 1240 450"
          stroke="rgba(94,234,212,0.15)"
          strokeWidth="12"
          strokeLinecap="round"
        />

        {/* Doodle nodes along path */}
        <g className="landing-float-slow" style={{ transformOrigin: "200px 400px" }}>
          <circle cx="200" cy="400" r="28" fill="rgba(13,148,136,0.2)" stroke="rgba(94,234,212,0.4)" strokeWidth="1.5" />
          <text x="200" y="406" textAnchor="middle" fill="#ccfbf1" fontSize="22">
            ?
          </text>
        </g>
        <g className="landing-float-delayed" style={{ transformOrigin: "520px 470px" }}>
          <rect x="492" y="442" width="56" height="56" rx="12" fill="rgba(99,102,241,0.15)" stroke="rgba(165,180,252,0.35)" strokeWidth="1.5" />
          <path d="M508 468 h32 M508 478 h24 M508 488 h16" stroke="#a5b4fc" strokeWidth="2" strokeLinecap="round" />
        </g>
        <g className="landing-float" style={{ transformOrigin: "780px 380px" }}>
          <circle cx="780" cy="380" r="26" fill="rgba(251,191,36,0.12)" stroke="rgba(252,211,77,0.45)" strokeWidth="1.5" />
          <path
            d="M768 380 h24 M780 368 v24"
            stroke="#fcd34d"
            strokeWidth="2"
            strokeLinecap="round"
          />
        </g>
        <g className="landing-float-slow" style={{ transformOrigin: "1000px 430px" }}>
          <path
            d="M980 450 L1020 410 L1060 450 L1020 490 Z"
            fill="rgba(13,148,136,0.15)"
            stroke="rgba(94,234,212,0.5)"
            strokeWidth="1.5"
            strokeLinejoin="round"
          />
        </g>

        {/* Corner graffiti */}
        <g opacity="0.5" className="landing-float-delayed">
          <path
            d="M1050 120 L1080 90 L1110 120 L1080 150 Z"
            stroke="#5eead4"
            strokeWidth="1"
            fill="none"
          />
          <circle cx="90" cy="140" r="4" fill="#5eead4" />
          <circle cx="110" cy="160" r="3" fill="#818cf8" />
          <path d="M60 200 Q100 180 140 200" stroke="rgba(148,163,184,0.4)" strokeWidth="1" fill="none" />
        </g>
      </svg>
    </div>
  );
}
