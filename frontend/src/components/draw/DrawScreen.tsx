"use client";

import { useEffect, useState } from "react";
import { DrawAnimation } from "@/components/DrawAnimation";
import { IdleView } from "./IdleView";
import { useLiveSocket } from "@/hooks/useLiveSocket";
import { t } from "@/i18n";

const CURSOR_IDLE_MS = 3000;
const HINT_VISIBLE_MS = 6000;

/**
 * Live screen (spec §9). Display only: state comes from the live socket / REST snapshot.
 * Designed to run for hours: no per-frame React state, no leftover timers, ambient
 * animation pauses when the tab is hidden.
 */
export function DrawScreen() {
  // `undefined` = not read yet (avoid connecting before we know the key).
  const [key, setKey] = useState<string | null | undefined>(undefined);
  useEffect(() => {
    setKey(new URLSearchParams(window.location.search).get("key"));
  }, []);

  const { snapshot, status, serverOffsetMs, forbidden } = useLiveSocket({
    key: key ?? null,
    enabled: key !== undefined,
  });

  const [cursorHidden, setCursorHidden] = useState(false);
  const [hintVisible, setHintVisible] = useState(true);
  const [tabHidden, setTabHidden] = useState(false);

  // Fullscreen on "F"
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "f" || e.key === "F" || e.key === "а" || e.key === "А") {
        if (document.fullscreenElement) void document.exitFullscreen();
        else void document.documentElement.requestFullscreen().catch(() => undefined);
        setHintVisible(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Hide the cursor after 3 s without movement
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | null = null;
    const arm = () => {
      setCursorHidden(false);
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => setCursorHidden(true), CURSOR_IDLE_MS);
    };
    arm();
    window.addEventListener("mousemove", arm);
    return () => {
      window.removeEventListener("mousemove", arm);
      if (timer) clearTimeout(timer);
    };
  }, []);

  // Fullscreen hint fades out on its own
  useEffect(() => {
    const timer = setTimeout(() => setHintVisible(false), HINT_VISIBLE_MS);
    return () => clearTimeout(timer);
  }, []);

  // Pause ambient animation when the tab is not visible
  useEffect(() => {
    const onVis = () => setTabHidden(document.hidden);
    onVis();
    document.addEventListener("visibilitychange", onVis);
    return () => document.removeEventListener("visibilitychange", onVis);
  }, []);

  const draw = snapshot?.draw ?? null;
  const winner = snapshot?.winner ?? null;
  const showDraw =
    snapshot !== null && snapshot.state !== "IDLE" && draw !== null && winner !== null && draw.started_at !== null;

  return (
    <div
      className={`brand-surface fixed inset-0 select-none overflow-hidden ${cursorHidden ? "cursor-hidden" : ""}`}
    >
      {showDraw && draw && winner && draw.started_at !== null ? (
        <DrawAnimation
          key={`${draw.id}:${draw.started_at}`}
          drawTitle={draw.title}
          prize={draw.prize}
          winner={{ number: winner.number, firstName: winner.first_name, lastName: winner.last_name }}
          startedAt={draw.started_at}
          serverOffsetMs={serverOffsetMs}
          durationMs={snapshot.animation_duration_ms || 8000}
        />
      ) : (
        <IdleView snapshot={snapshot} paused={tabHidden} />
      )}

      {/* Fullscreen hint */}
      <div
        aria-hidden="true"
        className={`pointer-events-none absolute bottom-[2.5vh] left-[2vw] text-[1.4vh] text-brand-muted transition-opacity duration-1000 ${
          hintVisible ? "opacity-70" : "opacity-0"
        }`}
      >
        {t("draw.fullscreen_hint")}
      </div>

      {/* Connection indicator: 8 px dot, bottom-right */}
      <div className="absolute bottom-3 right-3 flex items-center gap-2">
        {forbidden && <span className="text-[1.3vh] text-amber-300/80">{t("draw.key_required")}</span>}
        <span
          role="status"
          aria-label={status === "connected" ? t("draw.connected") : t("draw.reconnecting")}
          className={`block h-2 w-2 rounded-full ${status === "connected" ? "bg-emerald-400" : "bg-amber-400"}`}
        />
      </div>
    </div>
  );
}
