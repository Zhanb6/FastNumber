"use client";

import { useCallback, useEffect, useState } from "react";
import { exportAuditUrl, getAudit, getAuditActions } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import type { AuditView, Paginated } from "@/lib/types";
import { formatDateTime } from "@/lib/format";
import { EmptyRow, Input, LoadingRow, Pagination, Select, Table, Td, Th, useToast } from "@/components/ui";
import { t } from "@/i18n";

const PAGE_SIZE = 50;
const DEBOUNCE_MS = 400;

export default function AuditPage() {
  const toast = useToast();
  const [actions, setActions] = useState<string[]>([]);
  const [action, setAction] = useState("");
  const [drawInput, setDrawInput] = useState("");
  const [participantInput, setParticipantInput] = useState("");
  const [drawId, setDrawId] = useState("");
  const [participantId, setParticipantId] = useState("");
  const [page, setPage] = useState(1);
  const [data, setData] = useState<Paginated<AuditView> | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getAuditActions().then(
      (r) => setActions(r.items),
      () => undefined,
    );
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDrawId(drawInput.trim());
      setParticipantId(participantInput.trim());
      setPage(1);
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [drawInput, participantInput]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setData(await getAudit({ action, draw_id: drawId, participant_id: participantId, page, page_size: PAGE_SIZE }));
    } catch (e) {
      toast.error(errorMessage(e));
    } finally {
      setLoading(false);
    }
  }, [action, drawId, participantId, page, toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const cols = 7;

  return (
    <div className="mx-auto max-w-7xl">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">{t("admin.audit.title")}</h1>
        <a
          href={exportAuditUrl({ action, draw_id: drawId, participant_id: participantId })}
          className="inline-flex h-10 items-center rounded-lg border border-slate-300 bg-white px-4 text-sm font-medium text-slate-800 hover:bg-slate-50"
        >
          {t("admin.audit.download")}
        </a>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        <Select
          label={t("admin.audit.filter_action")}
          value={action}
          onChange={(e) => {
            setAction(e.target.value);
            setPage(1);
          }}
          options={[{ value: "", label: t("admin.audit.filter_action_all") }, ...actions.map((a) => ({ value: a, label: a }))]}
        />
        <Input label={t("admin.audit.filter_draw")} value={drawInput} onChange={(e) => setDrawInput(e.target.value)} placeholder="uuid" />
        <Input
          label={t("admin.audit.filter_participant")}
          value={participantInput}
          onChange={(e) => setParticipantInput(e.target.value)}
          placeholder="uuid"
        />
      </div>

      <div className="mt-4">
        <Table>
          <thead>
            <tr>
              <Th>{t("admin.audit.col.time")}</Th>
              <Th>{t("admin.audit.col.action")}</Th>
              <Th>{t("admin.audit.col.admin")}</Th>
              <Th>{t("admin.audit.col.participant")}</Th>
              <Th>{t("admin.audit.col.draw")}</Th>
              <Th>{t("admin.audit.col.ip")}</Th>
              <Th>{t("admin.audit.col.metadata")}</Th>
            </tr>
          </thead>
          <tbody>
            {loading && data === null && <LoadingRow colSpan={cols} />}
            {data && data.items.length === 0 && <EmptyRow colSpan={cols} />}
            {data?.items.map((a) => (
              <tr key={a.id} className={loading ? "opacity-60" : ""}>
                <Td className="whitespace-nowrap text-slate-600">{formatDateTime(a.created_at, true)}</Td>
                <Td className="font-mono text-xs font-semibold">{a.action}</Td>
                <Td>{a.admin_login ?? t("common.dash")}</Td>
                <Td>
                  <IdCell id={a.participant_id} onClick={setParticipantInput} />
                </Td>
                <Td>
                  <IdCell id={a.draw_id} onClick={setDrawInput} />
                </Td>
                <Td className="font-mono text-xs text-slate-600">{a.ip ?? t("common.dash")}</Td>
                <Td>
                  <MetadataCell metadata={a.metadata} />
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
    </div>
  );
}

function IdCell({ id, onClick }: { id: string | null; onClick: (id: string) => void }) {
  if (!id) return <span className="text-slate-400">{t("common.dash")}</span>;
  return (
    <button type="button" onClick={() => onClick(id)} title={id} className="font-mono text-xs text-sky-700 hover:underline">
      {id.slice(0, 8)}…
    </button>
  );
}

function MetadataCell({ metadata }: { metadata: Record<string, unknown> | null }) {
  if (!metadata || Object.keys(metadata).length === 0) return <span className="text-slate-400">{t("common.dash")}</span>;
  const json = JSON.stringify(metadata);
  return (
    <code title={json} className="block max-w-md truncate font-mono text-xs text-slate-700">
      {json}
    </code>
  );
}
