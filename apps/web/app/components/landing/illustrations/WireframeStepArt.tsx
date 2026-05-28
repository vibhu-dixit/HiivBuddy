/** Linear-style isometric wireframe illustrations per step. */

type WireframeStepArtProps = {
  variant: "describe" | "deliberate" | "decide";
  className?: string;
};

export function WireframeStepArt({ variant, className = "" }: WireframeStepArtProps) {
  return (
    <div className={`flex h-36 items-center justify-center ${className}`}>
      <svg
        viewBox="0 0 160 120"
        className="h-full w-full max-w-[140px] text-teal-400/80"
        fill="none"
        stroke="currentColor"
        strokeWidth="1"
        aria-hidden
      >
        {variant === "describe" && (
          <>
            <path d="M40 85 L80 55 L120 85 L80 115 Z" strokeOpacity="0.35" />
            <path d="M55 75 L80 58 L105 75 L80 92 Z" />
            <path d="M68 68 L80 60 L92 68" strokeOpacity="0.6" />
            <rect x="72" y="48" width="16" height="8" rx="1" strokeOpacity="0.5" />
            <line x1="80" y1="92" x2="80" y2="102" strokeOpacity="0.4" />
          </>
        )}
        {variant === "deliberate" && (
          <>
            <path d="M35 90 L55 70 L55 50 L75 40 L95 50 L95 70 L115 90" strokeOpacity="0.4" />
            <path d="M48 82 L58 72 L58 58 L75 50 L92 58 L92 72 L102 82" />
            <path d="M58 72 L75 62 L92 72" strokeOpacity="0.5" />
            <circle cx="75" cy="62" r="6" strokeOpacity="0.7" />
            <path d="M62 95 L88 95 M75 95 L75 108" strokeOpacity="0.35" />
          </>
        )}
        {variant === "decide" && (
          <>
            <path d="M45 95 L65 75 L85 85 L105 65 L125 85" strokeOpacity="0.35" />
            <path d="M55 88 L72 72 L88 80 L105 68 L118 82" />
            <path d="M72 72 L88 80" strokeOpacity="0.6" />
            <rect x="70" y="38" width="20" height="28" rx="2" strokeOpacity="0.5" />
            <line x1="75" y1="48" x2="85" y2="48" strokeOpacity="0.4" />
            <line x1="75" y1="54" x2="82" y2="54" strokeOpacity="0.4" />
          </>
        )}
      </svg>
    </div>
  );
}
