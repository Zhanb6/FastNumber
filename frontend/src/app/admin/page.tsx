"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import QRCode from "qrcode";
import { getStats, liveIdle, updateSettings } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import type { AdminStats } from "@/lib/types";
import { formatInt } from "@/lib/format";
import { useLive } from "@/components/admin/LiveContext";
import { Button, StatusBadge, useToast } from "@/components/ui";
import { t } from "@/i18n";

const REFRESH_MS = 10_000;

export default function DashboardPage() {
  const toast = useToast();
  const { snapshot, status } = useLive();
  const [stats, setStats] = useState<AdminStats | null>(null);
  const [toggling, setToggling] = useState(false);
  const [idling, setIdling] = useState(false);

  const load = useCallback(async () => {
    try {
      setStats(await getStats());
    } catch (e) {
      toast.error(errorMessage(e));
    }
  }, [toast]);

  // Initial load + 10 s fallback
  useEffect(() => {
    void load();
    const timer = setInterval(() => void load(), REFRESH_MS);
    return () => clearInterval(timer);
  }, [load]);

  // Refresh on live events (state changes, participants_count)
  const liveState = snapshot?.state;
  const liveCount = snapshot?.participants_count;
  const first = useRef(true);
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    void load();
  }, [liveState, liveCount, load]);

  const toggleRegistration = async () => {
    if (!stats) return;
    setToggling(true);
    try {
      const s = await updateSettings({ registration_open: !stats.registration_open });
      setStats({ ...stats, registration_open: s.registration_open });
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setToggling(false);
    }
  };

  const sendIdle = async () => {
    setIdling(true);
    try {
      await liveIdle();
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setIdling(false);
    }
  };

  const registrationUrl = stats ? `${stats.public_base_url.replace(/\/$/, "")}/` : "";
  const currentState = snapshot?.state ?? stats?.live_state ?? "IDLE";

  return (
    <div className="mx-auto max-w-6xl">
      <h1 className="text-2xl font-semibold">{t("admin.dashboard.title")}</h1>

      <div className="mt-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <StatCard label={t("admin.dashboard.total")} value={stats?.total_participants} />
        <StatCard label={t("admin.dashboard.today")} value={stats?.today_participants} />
        <StatCard label={t("admin.dashboard.draws_completed")} value={stats?.draws_completed} />
        <StatCard label={t("admin.dashboard.winners")} value={stats?.winners_count} />
      </div>

      <div className="mt-6 grid gap-4 lg:grid-cols-3">
        <section className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="text-sm font-semibold text-slate-500 uppercase">{t("admin.dashboard.registration")}</h2>
          <p className="mt-2 text-xl font-semibold">
            {stats ? (
              <span className={stats.registration_open ? "text-emerald-700" : "text-red-700"}>
                {stats.registration_open ? t("admin.dashboard.registration_open") : t("admin.dashboard.registration_closed")}
              </span>
            ) : (
              "…"
            )}
          </p>
          {stats && (
            <Button
              className="mt-4"
              variant={stats.registration_open ? "danger" : "primary"}
              onClick={toggleRegistration}
              loading={toggling}
            >
              {stats.registration_open ? t("admin.dashboard.close_registration") : t("admin.dashboard.open_registration")}
            </Button>
          )}
          {registrationUrl && (
            <p className="mt-4 text-sm text-slate-600">
              <a href={registrationUrl} target="_blank" rel="noopener" className="break-all text-sky-700 underline">
                {registrationUrl}
              </a>
            </p>
          )}
        </section>

        <section className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="text-sm font-semibold text-slate-500 uppercase">{t("admin.dashboard.live_state")}</h2>
          <div className="mt-2 flex items-center gap-2">
            <StatusBadge value={currentState} kind="live" />
            <span
              className={`inline-block h-2 w-2 rounded-full ${status === "connected" ? "bg-emerald-500" : "bg-amber-500"}`}
              title={status === "connected" ? t("draw.connected") : t("draw.reconnecting")}
            />
          </div>
          {snapshot?.draw && (
            <p className="mt-3 text-sm text-slate-700">
              <span className="text-slate-500">{t("admin.dashboard.current_draw")}: </span>
              {snapshot.draw.title} — {snapshot.draw.prize}
            </p>
          )}
          {snapshot?.state === "IDLE" && snapshot.next_draw && (
            <p className="mt-3 text-sm text-slate-700">
              <span className="text-slate-500">{t("admin.dashboard.next_draw")}: </span>
              {snapshot.next_draw.title} — {snapshot.next_draw.prize}
            </p>
          )}
          <div className="mt-4 flex flex-wrap gap-2">
            <a
              href="/draw"
              target="_blank"
              rel="noopener"
              className="inline-flex h-10 items-center rounded-lg bg-slate-900 px-4 text-sm font-medium text-white hover:bg-slate-700"
            >
              {t("admin.dashboard.live_open")} ↗
            </a>
            {currentState !== "IDLE" && (
              <Button variant="secondary" onClick={sendIdle} loading={idling}>
                {t("admin.dashboard.live_idle")}
              </Button>
            )}
          </div>
        </section>

        <section className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="text-sm font-semibold text-slate-500 uppercase">{t("admin.dashboard.qr_title")}</h2>
          <p className="mt-1 text-sm text-slate-600">{t("admin.dashboard.qr_hint")}</p>
          {registrationUrl && <QrCode text={registrationUrl} />}
        </section>
      </div>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: number | undefined }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5">
      <p className="text-sm text-slate-500">{label}</p>
      <p className="numeric mt-2 text-4xl font-semibold text-slate-900">{value === undefined ? "…" : formatInt(value)}</p>
    </div>
  );
}

/** QR rendered locally with the bundled `qrcode` package (no network). */
function QrCode({ text }: { text: string }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [png, setPng] = useState<string>("");

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    QRCode.toCanvas(canvas, text, { width: 220, margin: 1, errorCorrectionLevel: "M" }, (err) => {
      if (!err) setPng(canvas.toDataURL("image/png"));
    });
  }, [text]);

  return (
    <div className="mt-3 flex flex-col items-start gap-3">
      <canvas ref={canvasRef} className="rounded-lg border border-slate-200" aria-label={text} />
      {png && (
        <a href={png} download="registration-qr.png" className="text-sm text-sky-700 underline">
          {t("admin.dashboard.qr_download")}
        </a>
      )}
    </div>
  );
}
