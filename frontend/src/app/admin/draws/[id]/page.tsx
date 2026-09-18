"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { cancelDraw, confirmDraw, getDraw, isApiError, liveIdle, redrawDraw, startDraw } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import type { DrawDetail } from "@/lib/types";
import { formatDateTime, formatInt, fullName } from "@/lib/format";
import { useLive } from "@/components/admin/LiveContext";
import { Button, ConfirmModal, EmptyRow, Input, StatusBadge, Table, Td, Th, useToast } from "@/components/ui";
import { t, tDynamic } from "@/i18n";

const DEFAULT_ANIMATION_MS = 8000;

type Modal = { kind: "start"; eligible: number } | { kind: "redraw" } | { kind: "cancel" } | null;

export default function DrawDetailPage() {
  const { id } = useParams<{ id: string }>();
  const toast = useToast();
  const { snapshot, serverOffsetMs } = useLive();

  const [draw, setDraw] = useState<DrawDetail | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [modal, setModal] = useState<Modal>(null);
  const [busy, setBusy] = useState<"start" | "confirm" | "redraw" | "cancel" | "idle" | "refresh" | null>(null);
  const [reason, setReason] = useState("");
  const [remainingS, setRemainingS] = useState(0);

  const load = useCallback(async () => {
    try {
      setDraw(await getDraw(id));
      setNotFound(false);
    } catch (e) {
      if (isApiError(e) && e.status === 404) setNotFound(true);
      else toast.error(errorMessage(e));
    }
  }, [id, toast]);

  useEffect(() => {
    void load();
  }, [load]);

  // Refresh when the live state changes (e.g. draw run from the CLI or another tab).
  const liveKey = `${snapshot?.state ?? ""}:${snapshot?.draw?.id ?? ""}:${snapshot?.draw?.started_at ?? ""}`;
  const firstLive = useRef(true);
  useEffect(() => {
    if (firstLive.current) {
      firstLive.current = false;
      return;
    }
    void load();
  }, [liveKey, load]);

  // Confirm/redraw are locked until the animation on the screen has finished (spec §12.4).
  const pendingResult = draw?.status === "PENDING_CONFIRMATION" ? draw.current_result : null;
  const resultCreatedAt = pendingResult?.created_at ?? null;
  const animationMs = snapshot?.animation_duration_ms ?? DEFAULT_ANIMATION_MS;
  useEffect(() => {
    if (!resultCreatedAt) {
      setRemainingS(0);
      return;
    }
    const enableAt = new Date(resultCreatedAt).getTime() + animationMs;
    const update = () => {
      const left = enableAt - (Date.now() + serverOffsetMs);
      setRemainingS(left > 0 ? Math.ceil(left / 1000) : 0);
      return left > 0;
    };
    if (!update()) return;
    const timer = setInterval(() => {
      if (!update()) clearInterval(timer);
    }, 250);
    return () => clearInterval(timer);
  }, [resultCreatedAt, animationMs, serverOffsetMs]);

  const openStartModal = async () => {
    setBusy("refresh");
    try {
      const fresh = await getDraw(id); // fresh eligible_count for the confirmation
      setDraw(fresh);
      setModal({ kind: "start", eligible: fresh.eligible_count });
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(null);
    }
  };

  const handleApiError = (e: unknown) => {
    if (isApiError(e) && e.status === 409) {
      if (e.code === "INVALID_STATUS" && typeof e.details.status === "string") {
        toast.error(`${t("error.INVALID_STATUS")}: ${tDynamic("draw.status", e.details.status)}`);
      } else {
        toast.error(errorMessage(e));
      }
      void load();
      return;
    }
    toast.error(errorMessage(e));
  };

  const start = async () => {
    setBusy("start");
    try {
      setDraw(await startDraw(id));
      setModal(null);
    } catch (e) {
      setModal(null);
      handleApiError(e);
    } finally {
      setBusy(null);
    }
  };

  const confirm = async () => {
    setBusy("confirm");
    try {
      setDraw(await confirmDraw(id));
    } catch (e) {
      handleApiError(e);
    } finally {
      setBusy(null);
    }
  };

  const redraw = async () => {
    setBusy("redraw");
    try {
      setDraw(await redrawDraw(id, reason.trim() || undefined));
      setModal(null);
      setReason("");
    } catch (e) {
      setModal(null);
      handleApiError(e);
    } finally {
      setBusy(null);
    }
  };

  const cancel = async () => {
    setBusy("cancel");
    try {
      await cancelDraw(id, reason.trim() || undefined);
      setDraw(await getDraw(id));
      setModal(null);
      setReason("");
      toast.success(t("admin.draw.cancelled_toast"));
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(null);
    }
  };

  const idle = async () => {
    setBusy("idle");
    try {
      await liveIdle();
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(null);
    }
  };

  if (notFound) {
    return (
      <div className="mx-auto max-w-4xl">
        <Link href="/admin/draws" className="text-sm text-sky-700 hover:underline">
          {t("admin.draw.back")}
        </Link>
        <p className="mt-4 text-slate-600">{t("admin.draw.not_found")}</p>
      </div>
    );
  }
  if (!draw) return <p className="text-slate-500">{t("common.loading")}</p>;

  const locked = remainingS > 0;
  const isOnScreen = snapshot?.draw?.id === draw.id && snapshot.state !== "IDLE";

  return (
    <div className="mx-auto max-w-4xl">
      <Link href="/admin/draws" className="text-sm text-sky-700 hover:underline">
        {t("admin.draw.back")}
      </Link>

      <section className="mt-3 rounded-xl border border-slate-200 bg-white p-6">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <h1 className="text-3xl font-semibold">{draw.title}</h1>
            <p className="mt-2 text-lg text-slate-700">
              <span className="text-slate-500">{t("admin.draw.prize")}: </span>
              {draw.prize}
            </p>
            {draw.description && (
              <p className="mt-2 text-sm whitespace-pre-line text-slate-600">{draw.description}</p>
            )}
            {(draw.status === "DRAFT" || draw.status === "PENDING_CONFIRMATION") && (
              <p className="mt-2 text-lg text-slate-700">
                <span className="text-slate-500">{t("admin.draw.eligible")}: </span>
                <span className="numeric font-semibold">{formatInt(draw.eligible_count)}</span>
              </p>
            )}
            <p className="mt-1 text-sm text-slate-500">
              {draw.effective_exclude_previous_winners ? t("admin.draw.exclude_on") : t("admin.draw.exclude_off")}
            </p>
          </div>
          <div className="flex flex-col items-end gap-2">
            <div className="flex items-center gap-2 text-sm text-slate-500">
              {t("admin.draw.status")}: <StatusBadge value={draw.status} kind="draw.status" />
            </div>
            {isOnScreen && (
              <span className="text-xs text-sky-700">
                {t("admin.draw.live_now")}: {tDynamic("live", snapshot?.state ?? "")}
              </span>
            )}
          </div>
        </div>

        {draw.status === "DRAFT" && (
          <div className="mt-8 flex justify-center">
            <Button
              size="lg"
              onClick={openStartModal}
              loading={busy === "refresh"}
              className="h-20 w-full max-w-md text-2xl font-bold tracking-wide sm:h-24 sm:text-3xl"
            >
              {t("admin.draw.start")}
            </Button>
          </div>
        )}

        {draw.status === "PENDING_CONFIRMATION" && pendingResult && (
          <div className="mt-8 rounded-xl bg-slate-50 p-6 text-center">
            <p className="text-xs font-semibold tracking-widest text-slate-500 uppercase">{t("admin.draw.result_title")}</p>
            <p className="numeric mt-2 text-6xl font-bold text-slate-900">№ {pendingResult.participant.number}</p>
            <p className="mt-2 text-2xl font-medium">{fullName(pendingResult.participant)}</p>
            <div className="mt-6 flex flex-wrap justify-center gap-3">
              <Button size="lg" onClick={confirm} disabled={locked || busy !== null} loading={busy === "confirm"}>
                {t("admin.draw.confirm_winner")}
              </Button>
              <Button size="lg" variant="secondary" onClick={() => setModal({ kind: "redraw" })} disabled={locked || busy !== null}>
                {t("admin.draw.redraw")}
              </Button>
              <Button size="lg" variant="danger" onClick={() => setModal({ kind: "cancel" })} disabled={busy !== null}>
                {t("admin.draw.cancel")}
              </Button>
            </div>
            {locked && (
              <p className="mt-3 text-sm text-slate-500" aria-live="polite">
                {t("admin.draw.wait_seconds", { s: remainingS })}
              </p>
            )}
          </div>
        )}

        {draw.status === "COMPLETED" && draw.winner && (
          <div className="mt-8 rounded-xl bg-emerald-50 p-6 text-center">
            <p className="text-xs font-semibold tracking-widest text-emerald-700 uppercase">{t("admin.draw.winner")}</p>
            <p className="numeric mt-2 text-6xl font-bold text-slate-900">№ {draw.winner.number}</p>
            <p className="mt-2 text-2xl font-medium">{fullName(draw.winner)}</p>
            <p className="mt-3 text-sm text-slate-600">
              {t("admin.draw.completed_note")} {formatDateTime(draw.completed_at)}
            </p>
          </div>
        )}

        {draw.status === "CANCELLED" && <p className="mt-6 text-center text-slate-600">{t("admin.draw.cancelled_note")}</p>}

        {snapshot && snapshot.state !== "IDLE" && (
          <div className="mt-6 flex justify-center">
            <Button variant="secondary" onClick={idle} loading={busy === "idle"} disabled={busy !== null && busy !== "idle"}>
              {t("admin.draw.idle_screen")}
            </Button>
          </div>
        )}
      </section>

      <section className="mt-6">
        <h2 className="text-lg font-semibold">{t("admin.draw.history")}</h2>
        <div className="mt-3">
          <Table>
            <thead>
              <tr>
                <Th>{t("admin.draw.col.time")}</Th>
                <Th>{t("admin.draw.col.participant")}</Th>
                <Th>{t("admin.draw.col.status")}</Th>
                <Th>{t("admin.draw.col.eligible")}</Th>
                <Th>{t("admin.draw.col.reason")}</Th>
                <Th>{t("admin.draw.col.hash")}</Th>
              </tr>
            </thead>
            <tbody>
              {draw.results.length === 0 && <EmptyRow colSpan={6} />}
              {draw.results.map((r) => (
                <tr key={r.id}>
                  <Td className="whitespace-nowrap text-slate-600">{formatDateTime(r.created_at, true)}</Td>
                  <Td>
                    <span className="numeric font-semibold">№ {r.participant.number}</span> {fullName(r.participant)}
                  </Td>
                  <Td>
                    <StatusBadge value={r.status} kind="result.status" />
                  </Td>
                  <Td className="numeric">{formatInt(r.eligible_count)}</Td>
                  <Td className="max-w-xs text-slate-600">{r.reason ?? t("common.dash")}</Td>
                  <Td>
                    <code title={r.eligible_hash} className="font-mono text-xs text-slate-500">
                      {r.eligible_hash.slice(0, 12)}…
                    </code>
                  </Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </div>
      </section>

      <ConfirmModal
        open={modal?.kind === "start"}
        title={t("admin.draw.start_confirm_title", { n: modal?.kind === "start" ? formatInt(modal.eligible) : "" })}
        text={t("admin.draw.start_confirm_text")}
        confirmLabel={busy === "start" ? t("admin.draw.starting") : t("admin.draw.start_confirm")}
        loading={busy === "start"}
        onConfirm={start}
        onClose={() => busy !== "start" && setModal(null)}
      />

      <ConfirmModal
        open={modal?.kind === "cancel"}
        title={t("admin.draw.cancel_title")}
        text={t("admin.draw.cancel_text", { number: pendingResult?.participant.number ?? "" })}
        confirmLabel={t("admin.draw.cancel")}
        danger
        loading={busy === "cancel"}
        onConfirm={cancel}
        onClose={() => {
          if (busy === "cancel") return;
          setModal(null);
          setReason("");
        }}
      >
        <Input
          className="mt-4"
          label={t("common.reason_optional")}
          placeholder={t("admin.draw.cancel_reason_placeholder")}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          maxLength={500}
        />
      </ConfirmModal>

      <ConfirmModal
        open={modal?.kind === "redraw"}
        title={t("admin.draw.redraw_title")}
        text={t("admin.draw.redraw_text", { number: pendingResult?.participant.number ?? "" })}
        confirmLabel={t("admin.draw.redraw")}
        danger
        loading={busy === "redraw"}
        onConfirm={redraw}
        onClose={() => {
          if (busy === "redraw") return;
          setModal(null);
          setReason("");
        }}
      >
        <Input
          className="mt-4"
          label={t("common.reason_optional")}
          placeholder={t("admin.draw.redraw_reason_placeholder")}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          maxLength={500}
        />
      </ConfirmModal>
    </div>
  );
}
