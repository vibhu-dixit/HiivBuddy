/** Shared persona colors — list badges (Tailwind) and wheel SVG (hex). */

export const PERSONA_SVG_COLORS = [
  { fill: "#0d9488", fillDark: "#0f766e", stroke: "#0f766e", glow: "rgba(13,148,136,0.5)" },
  { fill: "#4f46e5", fillDark: "#4338ca", stroke: "#4338ca", glow: "rgba(79,70,229,0.45)" },
  { fill: "#d97706", fillDark: "#b45309", stroke: "#b45309", glow: "rgba(217,119,6,0.45)" },
  { fill: "#e11d48", fillDark: "#be123c", stroke: "#be123c", glow: "rgba(225,29,72,0.45)" },
  { fill: "#059669", fillDark: "#047857", stroke: "#047857", glow: "rgba(5,150,105,0.45)" },
] as const;

export const PERSONA_BADGE_STYLES = [
  {
    gradient: "bg-gradient-to-br from-teal-600 to-teal-700",
    ring: "ring-teal-600/30",
    soft: "bg-teal-50 border-teal-200/80",
  },
  {
    gradient: "bg-gradient-to-br from-indigo-600 to-indigo-700",
    ring: "ring-indigo-600/30",
    soft: "bg-indigo-50 border-indigo-200/80",
  },
  {
    gradient: "bg-gradient-to-br from-amber-600 to-amber-700",
    ring: "ring-amber-600/30",
    soft: "bg-amber-50 border-amber-200/80",
  },
  {
    gradient: "bg-gradient-to-br from-rose-600 to-rose-700",
    ring: "ring-rose-600/30",
    soft: "bg-rose-50 border-rose-200/80",
  },
  {
    gradient: "bg-gradient-to-br from-emerald-600 to-emerald-700",
    ring: "ring-emerald-600/30",
    soft: "bg-emerald-50 border-emerald-200/80",
  },
] as const;
