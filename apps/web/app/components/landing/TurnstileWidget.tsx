"use client";

import Script from "next/script";
import { useCallback, useEffect, useRef, useState } from "react";

import { TURNSTILE_SITE_KEY } from "./turnstileConfig";

type TurnstileWidgetProps = {
  onToken: (token: string) => void;
  onExpire?: () => void;
  onError?: () => void;
  resetKey?: number;
};

type TurnstileApi = {
  render: (
    container: HTMLElement,
    options: {
      sitekey: string;
      callback: (token: string) => void;
      "expired-callback"?: () => void;
      "error-callback"?: () => void;
      theme?: "light" | "dark" | "auto";
    },
  ) => string;
  reset: (widgetId: string) => void;
  remove: (widgetId: string) => void;
};

declare global {
  interface Window {
    turnstile?: TurnstileApi;
  }
}

export function TurnstileWidget({ onToken, onExpire, onError, resetKey = 0 }: TurnstileWidgetProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const widgetIdRef = useRef<string | null>(null);
  const [scriptReady, setScriptReady] = useState(false);

  const renderWidget = useCallback(() => {
    const el = containerRef.current;
    if (!el || !window.turnstile || !TURNSTILE_SITE_KEY) return;

    if (widgetIdRef.current) {
      try {
        window.turnstile.remove(widgetIdRef.current);
      } catch {
        /* ignore */
      }
      widgetIdRef.current = null;
    }

    el.innerHTML = "";
    widgetIdRef.current = window.turnstile.render(el, {
      sitekey: TURNSTILE_SITE_KEY,
      theme: "light",
      callback: onToken,
      "expired-callback": onExpire,
      "error-callback": onError,
    });
  }, [onToken, onExpire, onError]);

  useEffect(() => {
    if (scriptReady) renderWidget();
    return () => {
      if (widgetIdRef.current && window.turnstile) {
        try {
          window.turnstile.remove(widgetIdRef.current);
        } catch {
          /* ignore */
        }
        widgetIdRef.current = null;
      }
    };
  }, [scriptReady, renderWidget, resetKey]);

  if (!TURNSTILE_SITE_KEY) {
    return (
      <p className="text-sm text-[var(--muted)]">
        Demo verification is not configured. Set{" "}
        <code className="text-xs">NEXT_PUBLIC_TURNSTILE_SITE_KEY</code> or contact support.
      </p>
    );
  }

  return (
    <>
      <Script
        src="https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit"
        strategy="afterInteractive"
        onLoad={() => setScriptReady(true)}
      />
      <div ref={containerRef} className="flex min-h-[65px] justify-center" />
    </>
  );
}
