"use client";

import { useCallback, useEffect, useState } from "react";
import {
  deleteParticipant,
  disqualifyParticipant,
  exportParticipantsUrl,
  listParticipants,
  restoreParticipant,
} from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import type { Paginated, ParticipantAdmin, ParticipantSort, ParticipantStatusFilter } from "@/lib/types";
import { formatDateTime } from "@/lib/format";
import {
  Button,
  ConfirmModal,
  EmptyRow,
  Input,
  LoadingRow,
  Pagination,
  Select,
  StatusBadge,
  Table,
  Td,
  Th,
  useToast,
} from "@/components/ui";
import { t } from "@/i18n";

const PAGE_SIZE = 50;
const DEBOUNCE_MS = 350;

type WonFilter = "" | "true" | "false";
type PendingAction = { kind: "disqualify" | "delete"; participant: ParticipantAdmin } | null;

export default function ParticipantsPage() {
  const toast = useToast();
  const [search, setSearch] = useState("");
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<ParticipantStatusFilter>("");
  const [won, setWon] = useState<WonFilter>("");
  const [sort, setSort] = useState<ParticipantSort>("number");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Paginated<ParticipantAdmin> | null>(null);
  const [loading, setLoading] = useState(true);
  const [action, setAction] = useState<PendingAction>(null);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);

  // Debounced server-side search
  useEffect(() => {
    const timer = setTimeout(() => {
      setQ(search.trim());
      setPage(1);
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [search]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setData(await listParticipants({ q, status, won, sort, page, page_size: PAGE_SIZE }));
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [q, status, won, sort, page, toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const replaceRow = (p: ParticipantAdmin) =>
    setData((d) => (d ? { ...d, items: d.items.map((i) => (i.id === p.id ? p : i)) } : d));

  const runAction = async () => {
    if (!action) return;
    setBusy(true);
    try {
      if (action.kind === "disqualify") {
        replaceRow(await disqualifyParticipant(action.participant.id, reason.trim() || undefined));
      } else {
        await deleteParticipant(action.participant.id);
        await load();
      }
      setAction(null);
      setReason("");
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  const restore = async (p: ParticipantAdmin) => {
    try {
      replaceRow(await restoreParticipant(p.id));
      if (status === "DELETED") await load();
    } catch (e) {
      toast.error(errorMessage(e));
    }
  };

  const closeModal = () => {
    if (busy) return;
    setAction(null);
    setReason("");
  };

  const cols = 7;

  return (
    <div className="mx-auto max-w-6xl">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">{t("admin.participants.title")}</h1>
        <a
          href={exportParticipantsUrl({ q, status, won })}
          className="inline-flex h-10 items-center rounded-lg border border-slate-300 bg-white px-4 text-sm font-medium text-slate-800 hover:bg-slate-50"
        >
          {t("admin.participants.export")}
        </a>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Input
          label={t("common.search")}
          type="search"
          placeholder={t("admin.participants.search_placeholder")}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <Select
          label={t("admin.participants.filter_status")}
          value={status}
          onChange={(e) => {
            setStatus(e.target.value as ParticipantStatusFilter);
            setPage(1);
          }}
          options={[
            { value: "", label: t("admin.participants.filter_status_default") },
            { value: "ACTIVE", label: t("participant.status.ACTIVE") },
            { value: "DISQUALIFIED", label: t("participant.status.DISQUALIFIED") },
            { value: "DELETED", label: t("participant.status.DELETED") },
            { value: "all", label: t("admin.participants.filter_status_all") },
          ]}
        />
        <Select
          label={t("admin.participants.filter_won")}
          value={won}
          onChange={(e) => {
            setWon(e.target.value as WonFilter);
            setPage(1);
          }}
          options={[
            { value: "", label: t("admin.participants.filter_won_any") },
            { value: "true", label: t("common.yes") },
            { value: "false", label: t("common.no") },
          ]}
        />
        <Select
          label={t("admin.participants.sort")}
          value={sort}
          onChange={(e) => {
            setSort(e.target.value as ParticipantSort);
            setPage(1);
          }}
          options={[
            { value: "number", label: t("admin.participants.sort.number") },
            { value: "-number", label: t("admin.participants.sort.-number") },
            { value: "created_at", label: t("admin.participants.sort.created_at") },
            { value: "-created_at", label: t("admin.participants.sort.-created_at") },
          ]}
        />
      </div>

      <div className="mt-4">
        <Table>
          <thead>
            <tr>
              <Th>{t("admin.participants.col.number")}</Th>
              <Th>{t("admin.participants.col.first_name")}</Th>
              <Th>{t("admin.participants.col.last_name")}</Th>
              <Th>{t("admin.participants.col.created_at")}</Th>
              <Th>{t("admin.participants.col.status")}</Th>
              <Th>{t("admin.participants.col.won")}</Th>
              <Th className="text-right">{t("common.actions")}</Th>
            </tr>
          </thead>
          <tbody>
            {loading && data === null && <LoadingRow colSpan={cols} />}
            {data && data.items.length === 0 && <EmptyRow colSpan={cols} />}
            {data?.items.map((p) => (
              <tr key={p.id} className={loading ? "opacity-60" : ""}>
                <Td className="numeric font-semibold">{p.number}</Td>
                <Td>{p.first_name}</Td>
                <Td>{p.last_name}</Td>
                <Td className="text-slate-600">{formatDateTime(p.created_at)}</Td>
                <Td>
                  <div className="flex flex-col gap-1">
                    <span>
                      <StatusBadge value={p.status} kind="participant.status" />
                    </span>
                    {p.pending_result && (
                      <span className="text-xs text-amber-700">{t("admin.participants.pending_badge")}</span>
                    )}
                    {p.status_reason && <span className="text-xs text-slate-500">{p.status_reason}</span>}
                  </div>
                </Td>
                <Td>{p.has_won ? t("common.yes") : t("common.no")}</Td>
                <Td className="text-right">
                  <div className="flex justify-end gap-1">
                    {p.status === "ACTIVE" && (
                      <span title={p.pending_result ? t("admin.participants.pending_tooltip") : undefined}>
                        <Button
                          size="sm"
                          variant="secondary"
                          disabled={p.pending_result}
                          onClick={() => setAction({ kind: "disqualify", participant: p })}
                        >
                          {t("admin.participants.disqualify")}
                        </Button>
                      </span>
                    )}
                    {p.status !== "ACTIVE" && (
                      <Button size="sm" variant="secondary" onClick={() => restore(p)}>
                        {t("admin.participants.restore")}
                      </Button>
                    )}
                    {p.status !== "DELETED" && (
                      <span title={p.pending_result ? t("admin.participants.pending_tooltip") : undefined}>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="text-red-700"
                          disabled={p.pending_result}
                          onClick={() => setAction({ kind: "delete", participant: p })}
                        >
                          {t("admin.participants.delete")}
                        </Button>
                      </span>
                    )}
                  </div>
                </Td>
              </tr>
            ))}
          </tbody>
        </Table>
      </div>

      {data && (
        <div className="mt-4">
          <Pagination page={data.page} pageSize={data.page_size} total={data.total} onChange={setPage} />
        </div>
      )}

      <ConfirmModal
        open={action?.kind === "disqualify"}
        title={t("admin.participants.disqualify_title", { number: action?.participant.number ?? "" })}
        text={t("admin.participants.disqualify_text")}
        confirmLabel={t("admin.participants.disqualify")}
        onConfirm={runAction}
        onClose={closeModal}
        loading={busy}
      >
        <Input
          className="mt-4"
          label={t("common.reason_optional")}
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          maxLength={500}
        />
      </ConfirmModal>

      <ConfirmModal
        open={action?.kind === "delete"}
        title={t("admin.participants.delete_title", { number: action?.participant.number ?? "" })}
        text={t("admin.participants.delete_text")}
        confirmLabel={t("common.delete")}
        danger
        onConfirm={runAction}
        onClose={closeModal}
        loading={busy}
      />
    </div>
  );
}
