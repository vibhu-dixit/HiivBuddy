"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { useAuth } from "../../auth/AuthProvider";

type SiteHeaderProps = {
  onTryDemo?: () => void;
  demoBusy?: boolean;
};

/** One short scroll (~1 wheel tick) completes the morph */
const SCROLL_RANGE = 56;

/** Minimum space between logo (left) and actions (right) when collected */
const COMPACT_GROUP_GAP = 32;

function clamp01(n: number) {
  return Math.min(1, Math.max(0, n));
}

function smoothstep(t: number) {
  return t * t * (3 - 2 * t);
}

export function SiteHeader({ onTryDemo, demoBusy }: SiteHeaderProps) {
  const { user, loading } = useAuth();
  const [progress, setProgress] = useState(0);
  const [trackWidth, setTrackWidth] = useState(0);
  const [logoWidth, setLogoWidth] = useState(0);
  const [navWidth, setNavWidth] = useState(0);
  const trackRef = useRef<HTMLDivElement>(null);
  const logoRef = useRef<HTMLAnchorElement>(null);
  const navRef = useRef<HTMLElement>(null);

  useEffect(() => {
    let frame = 0;

    const update = () => {
      frame = 0;
      setProgress(clamp01(window.scrollY / SCROLL_RANGE));
    };

    const onScroll = () => {
      if (!frame) frame = window.requestAnimationFrame(update);
    };

    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      if (frame) window.cancelAnimationFrame(frame);
    };
  }, []);

  useEffect(() => {
    const track = trackRef.current;
    const logo = logoRef.current;
    const nav = navRef.current;
    if (!track || !logo || !nav) return;

    const measure = () => {
      setTrackWidth(track.clientWidth);
      setLogoWidth(logo.offsetWidth);
      setNavWidth(nav.offsetWidth);
    };

    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(track);
    ro.observe(logo);
    ro.observe(nav);
    return () => ro.disconnect();
  }, [user, loading]);

  const eased = smoothstep(progress);
  const barPadY = 20 - eased * 10;
  const barPadX = 24 - eased * 8;
  const logoSize = 18 - eased * 2;
  const topOffset = eased * 12;
  const pillOpacity = eased * 0.82;
  const padX2 = barPadX * 2;

  const spreadGroupGap =
    trackWidth > 0 && logoWidth > 0 && navWidth > 0
      ? Math.max(COMPACT_GROUP_GAP, trackWidth - logoWidth - navWidth - padX2)
      : COMPACT_GROUP_GAP;

  const groupGap = spreadGroupGap * (1 - eased) + COMPACT_GROUP_GAP * eased;

  const barWidth =
    logoWidth > 0 && navWidth > 0 ? logoWidth + navWidth + groupGap + padX2 : trackWidth || undefined;

  const marginLeft =
    trackWidth > 0 && barWidth !== undefined ? ((trackWidth - barWidth) / 2) * eased : 0;

  return (
    <header
      className="pointer-events-none fixed inset-x-0 top-0 z-50 bg-transparent"
      style={{ paddingTop: topOffset }}
    >
      <div ref={trackRef} className="pointer-events-auto mx-auto max-w-6xl px-6">
        <div
          className="relative flex items-center"
          style={{
            boxSizing: "border-box",
            width: barWidth,
            marginLeft,
            gap: groupGap,
            padding: `${barPadY}px ${barPadX}px`,
            borderRadius: 9999,
          }}
        >
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0 rounded-full border border-white/15 shadow-lg shadow-black/20 backdrop-blur-md"
            style={{
              backgroundColor: `rgba(10, 18, 24, ${pillOpacity})`,
              opacity: pillOpacity > 0.02 ? 1 : 0,
            }}
          />

          <Link
            ref={logoRef}
            href="/"
            className="relative z-10 grid shrink-0 items-center"
            aria-label="Hiiv home"
          >
            <span
              className="col-start-1 row-start-1 font-semibold tracking-tight text-white transition-opacity duration-200 ease-out"
              style={{ fontSize: logoSize, opacity: 1 - eased }}
              aria-hidden={eased > 0.5}
            >
              Hiiv
            </span>
            <Image
              src="/logo.png"
              alt=""
              width={36}
              height={36}
              className="col-start-1 row-start-1 h-8 w-8 rounded-lg transition-opacity duration-200 ease-out sm:h-9 sm:w-9"
              style={{ opacity: eased }}
              aria-hidden={eased < 0.5}
              priority
            />
          </Link>

          <nav
            ref={navRef}
            className="relative z-10 flex shrink-0 items-center gap-3 sm:gap-4"
          >
            {!loading && user ? (
              <Link
                href="/decision-room"
                className="rounded-lg bg-[var(--accent)] px-3 py-1.5 text-sm font-medium text-white hover:bg-[var(--accent-hover)] sm:px-4 sm:py-2"
              >
                Open Decision Room
              </Link>
            ) : (
              onTryDemo && (
                <button
                  type="button"
                  onClick={onTryDemo}
                  disabled={demoBusy}
                  className="rounded-lg bg-[var(--accent)] px-3 py-1.5 text-sm font-medium text-white hover:bg-[var(--accent-hover)] disabled:opacity-50 sm:px-4 sm:py-2"
                >
                  {demoBusy ? "Starting…" : "Try demo"}
                </button>
              )
            )}
          </nav>
        </div>
      </div>
    </header>
  );
}
