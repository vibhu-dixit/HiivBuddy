"use client";

import { useCallback, useEffect, useState } from "react";

import { LANDING_COPY } from "./landingCopy";
import { isTurnstileConfigured } from "./turnstileConfig";
import { TurnstileWidget } from "./TurnstileWidget";

type TryDemoModalProps = {
  open: boolean;
  busy: boolean;
  error: string | null;
  onClose: () => void;
  onConfirm: (captchaToken: string) => void;
};

export function TryDemoModal({ open, busy, error, onClose, onConfirm }: TryDemoModalProps) {
  const [captchaToken, setCaptchaToken] = useState<string | null>(null);
  const [resetKey, setResetKey] = useState(0);

  useEffect(() => {
    if (!open) {
      setCaptchaToken(null);
      setResetKey((k) => k + 1);
    }
  }, [open]);

  const handleToken = useCallback((token: string) => {
    setCaptchaToken(token);
  }, []);

  const handleExpire = useCallback(() => {
    setCaptchaToken(null);
  }, []);

  const handleError = useCallback(() => {
    setCaptchaToken(null);
    setResetKey((k) => k + 1);
  }, []);

  if (!open) return null;

  const { tryDemoModal } = LANDING_COPY;
  const canStart = isTurnstileConfigured() && captchaToken && !busy;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="try-demo-title"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="try-demo-title" className="text-lg font-semibold">
          {tryDemoModal.title}
        </h2>
        <p className="mt-2 text-sm text-[var(--muted)]">{tryDemoModal.description}</p>

        <div className="mt-5">
          <TurnstileWidget
            resetKey={resetKey}
            onToken={handleToken}
            onExpire={handleExpire}
            onError={handleError}
          />
        </div>

        {error && <p className="mt-3 text-sm text-red-600">{error}</p>}

        <div className="mt-6 flex flex-wrap justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            className="rounded-lg border border-[var(--border)] px-4 py-2 text-sm font-medium hover:bg-[var(--background)] disabled:opacity-50"
          >
            {tryDemoModal.cancel}
          </button>
          <button
            type="button"
            disabled={!canStart}
            onClick={() => captchaToken && onConfirm(captchaToken)}
            className="rounded-lg bg-[var(--accent)] px-4 py-2 text-sm font-semibold text-white hover:bg-[var(--accent-hover)] disabled:cursor-not-allowed disabled:opacity-50"
          >
            {busy ? tryDemoModal.confirmBusy : tryDemoModal.confirm}
          </button>
        </div>
      </div>
    </div>
  );
}
