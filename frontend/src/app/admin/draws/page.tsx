"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { cancelDraw, deleteDraw, listDraws } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import type { DrawView } from "@/lib/types";
import { formatDateTime, fullName } from "@/lib/format";
import { DrawFormModal } from "@/components/admin/DrawFormModal";
import { Button, ConfirmModal, EmptyRow, LoadingRow, StatusBadge, Table, Td, Th, useToast } from "@/components/ui";
import { t } from "@/i18n";

type Modal = { kind: "create" } | { kind: "edit"; draw: DrawView } | { kind: "delete"; draw: DrawView } | { kind: "cancel"; draw: DrawView } | null;

export default function DrawsPage() {
  const toast = useToast();
  const [draws, setDraws] = useState<DrawView[] | null>(null);
  const [modal, setModal] = useState<Modal>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      setDraws((await listDraws()).items);
    } catch (e) {
      toast.error(errorMessage(e));
    }
  }, [toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const runModalAction = async () => {
    if (!modal || (modal.kind !== "delete" && modal.kind !== "cancel")) return;
    setBusy(true);
    try {
      if (modal.kind === "delete") await deleteDraw(modal.draw.id);
      else await cancelDraw(modal.draw.id);
      setModal(null);
      await load();
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const cols = 9;

  return (
    <div className="mx-auto max-w-7xl">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">{t("admin.draws.title")}</h1>
        <Button onClick={() => setModal({ kind: "create" })}>{t("admin.draws.create")}</Button>
      </div>

      <div className="mt-6">
        <Table>
          <thead>
            <tr>
              <Th>{t("admin.draws.col.position")}</Th>
              <Th>{t("admin.draws.col.title")}</Th>
              <Th>{t("admin.draws.col.prize")}</Th>
              <Th>{t("admin.draws.col.status")}</Th>
              <Th>{t("admin.draws.col.scheduled_at")}</Th>
              <Th>{t("admin.draws.col.started_at")}</Th>
              <Th>{t("admin.draws.col.completed_at")}</Th>
              <Th>{t("admin.draws.col.winner")}</Th>
              <Th className="text-right">{t("common.actions")}</Th>
            </tr>
          </thead>
          <tbody>
            {draws === null && <LoadingRow colSpan={cols} />}
            {draws !== null && draws.length === 0 && <EmptyRow colSpan={cols} text={t("admin.draws.empty")} />}
            {draws?.map((d) => (
              <tr key={d.id}>
                <Td className="text-slate-500">{d.position}</Td>
                <Td>
                  <Link href={`/admin/draws/${d.id}`} className="font-medium text-sky-700 hover:underline">
                    {d.title}
                  </Link>
                </Td>
                <Td>{d.prize}</Td>
                <Td>
                  <StatusBadge value={d.status} kind="draw.status" />
                </Td>
                <Td className="text-slate-600">{formatDateTime(d.scheduled_at)}</Td>
                <Td className="text-slate-600">{formatDateTime(d.started_at)}</Td>
                <Td className="text-slate-600">{formatDateTime(d.completed_at)}</Td>
                <Td>
                  {d.winner ? (
                    <span>
                      <span className="numeric font-semibold">№ {d.winner.number}</span> {fullName(d.winner)}
                    </span>
                  ) : (
                    <span className="text-slate-400">{t("common.dash")}</span>
                  )}
                </Td>
                <Td className="text-right">
                  <div className="flex justify-end gap-1">
                    <Link
                      href={`/admin/draws/${d.id}`}
                      className="inline-flex h-8 items-center rounded-lg bg-slate-900 px-3 text-sm font-medium text-white hover:bg-slate-700"
                    >
                      {t("admin.draws.open")}
                    </Link>
                    {d.status === "DRAFT" && (
                      <>
                        <Button size="sm" variant="secondary" onClick={() => setModal({ kind: "edit", draw: d })}>
                          {t("common.edit")}
                        </Button>
                        <Button size="sm" variant="ghost" onClick={() => setModal({ kind: "cancel", draw: d })}>
                          {t("admin.draws.cancel_draw")}
                        </Button>
                        {!d.current_result && (
                          <Button size="sm" variant="ghost" className="text-red-700" onClick={() => setModal({ kind: "delete", draw: d })}>
                            {t("common.delete")}
                          </Button>
                        )}
                      </>
                    )}
                  </div>
                </Td>
              </tr>
            ))}
          </tbody>
        </Table>
      </div>

      <DrawFormModal
        open={modal?.kind === "create" || modal?.kind === "edit"}
        draw={modal?.kind === "edit" ? modal.draw : undefined}
        onClose={() => setModal(null)}
        onSaved={() => void load()}
      />

      <ConfirmModal
        open={modal?.kind === "delete"}
        title={t("admin.draws.delete_title", { title: modal?.kind === "delete" ? modal.draw.title : "" })}
        text={t("admin.draws.delete_text")}
        confirmLabel={t("common.delete")}
        danger
        loading={busy}
        onConfirm={runModalAction}
        onClose={() => !busy && setModal(null)}
      />

      <ConfirmModal
        open={modal?.kind === "cancel"}
        title={t("admin.draws.cancel_title", { title: modal?.kind === "cancel" ? modal.draw.title : "" })}
        text={t("admin.draws.cancel_text")}
        confirmLabel={t("admin.draws.cancel_draw")}
        danger
        loading={busy}
        onConfirm={runModalAction}
        onClose={() => !busy && setModal(null)}
      />
    </div>
  );
}
