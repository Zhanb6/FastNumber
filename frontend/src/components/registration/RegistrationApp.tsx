"use client";

import { useCallback, useEffect, useState } from "react";
import { getMe, getPublicConfig, isApiError } from "@/lib/api";
import { clearDeviceToken, getDeviceToken, saveDeviceToken } from "@/lib/device-token";
import { errorMessage } from "@/lib/errors";
import type { FieldsConfig, ParticipantPublic, PublicConfig } from "@/lib/types";
import { t } from "@/i18n";
import { BrandHeader } from "./BrandHeader";
import { NumberScreen } from "./NumberScreen";
import { RegisterForm } from "./RegisterForm";

const DEFAULT_FIELDS: FieldsConfig = {
  phone: { enabled: false, required: false },
  email: { enabled: false, required: false },
  company: { enabled: false, required: false },
};

type Screen =
  | { kind: "loading" }
  | { kind: "form" }
  | { kind: "closed" }
  | { kind: "number"; participant: ParticipantPublic }
  | { kind: "error"; message: string };

export function RegistrationApp() {
  const [screen, setScreen] = useState<Screen>({ kind: "loading" });
  const [config, setConfig] = useState<PublicConfig | null>(null);
  const [token, setToken] = useState<string | null>(null);

  const load = useCallback(async () => {
    setScreen({ kind: "loading" });
    const storedToken = getDeviceToken();
    setToken(storedToken);

    const configPromise = getPublicConfig().then(
      (c) => c,
      () => null,
    );

    let participant: ParticipantPublic | null = null;
    let fatal: string | null = null;
    if (storedToken) {
      try {
        participant = await getMe(storedToken);
      } catch (e) {
        if (isApiError(e) && e.status === 404) {
          // Deleted or unknown token: forget it and show the form.
          clearDeviceToken();
          setToken(null);
        } else {
          // Network / server error: keep the token, let the user retry.
          fatal = errorMessage(e);
        }
      }
    }

    const cfg = await configPromise;
    setConfig(cfg);

    if (participant) {
      setScreen({ kind: "number", participant });
    } else if (fatal) {
      setScreen({ kind: "error", message: fatal });
    } else if (cfg && !cfg.registration_open) {
      setScreen({ kind: "closed" });
    } else {
      setScreen({ kind: "form" });
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const handleRegistered = (p: ParticipantPublic) => {
    saveDeviceToken(p.token);
    setToken(p.token);
    setScreen({ kind: "number", participant: p });
  };

  const handleNotMe = () => {
    clearDeviceToken();
    setToken(null);
    setScreen(config && !config.registration_open ? { kind: "closed" } : { kind: "form" });
  };

  return (
    <main className="brand-surface flex min-h-dvh flex-col items-center px-4 py-8 sm:py-12">
      <div className="flex w-full max-w-md flex-1 flex-col">
        <BrandHeader compact={screen.kind === "number"} />
        <div className="flex flex-1 flex-col justify-center py-8">
          {screen.kind === "loading" && <Skeleton />}
          {screen.kind === "form" && (
            <RegisterForm
              fields={config?.fields ?? DEFAULT_FIELDS}
              nameMode={config?.name_mode ?? "full"}
              deviceToken={token}
              onRegistered={handleRegistered}
              onClosed={() => setScreen({ kind: "closed" })}
            />
          )}
          {screen.kind === "closed" && <ClosedScreen />}
          {screen.kind === "number" && <NumberScreen participant={screen.participant} onNotMe={handleNotMe} />}
          {screen.kind === "error" && <ErrorScreen message={screen.message} onRetry={load} onNotMe={handleNotMe} />}
        </div>
      </div>
    </main>
  );
}

function Skeleton() {
  return (
    <div className="animate-pulse space-y-4" aria-busy="true" aria-label={t("common.loading")}>
      <div className="mx-auto h-4 w-40 rounded bg-white/10" />
      <div className="mx-auto h-24 w-48 rounded-xl bg-white/10" />
      <div className="mx-auto h-4 w-56 rounded bg-white/10" />
    </div>
  );
}

function ClosedScreen() {
  return (
    <section className="text-center">
      <h1 className="text-2xl font-semibold">{t("register.closed_title")}</h1>
      <p className="mt-3 text-base leading-relaxed text-brand-muted">{t("register.closed_text")}</p>
    </section>
  );
}

function ErrorScreen({ message, onRetry, onNotMe }: { message: string; onRetry: () => void; onNotMe: () => void }) {
  return (
    <section className="text-center">
      <h1 className="text-xl font-semibold">{t("register.me_error")}</h1>
      <p className="mt-2 text-brand-muted">{message}</p>
      <button
        type="button"
        onClick={onRetry}
        className="mt-6 inline-flex h-12 items-center justify-center rounded-xl bg-brand-accent px-6 text-base font-semibold text-slate-950"
      >
        {t("common.retry")}
      </button>
      <div className="mt-6">
        <button type="button" onClick={onNotMe} className="text-sm text-brand-muted underline underline-offset-4">
          {t("register.not_me")}
        </button>
      </div>
    </section>
  );
}
