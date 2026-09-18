"use client";

import { useEffect, useState } from "react";
import { exportWinnersUrl, getWinners } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import type { WinnerRow } from "@/lib/types";
import { formatDateTime } from "@/lib/format";
import { EmptyRow, LoadingRow, Table, Td, Th, useToast } from "@/components/ui";
import { t } from "@/i18n";

export default function WinnersPage() {
  const toast = useToast();
  const [rows, setRows] = useState<WinnerRow[] | null>(null);

  useEffect(() => {
    getWinners().then(
      (r) => setRows(r.items),
      (e) => {
        setRows([]);
        toast.error(errorMessage(e));
      },
    );
  }, [toast]);

  return (
    <div className="mx-auto max-w-6xl">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold">{t("admin.winners.title")}</h1>
        <a
          href={exportWinnersUrl()}
          className="inline-flex h-10 items-center rounded-lg border border-slate-300 bg-white px-4 text-sm font-medium text-slate-800 hover:bg-slate-50"
        >
          {t("admin.winners.download")}
        </a>
      </div>

      <div className="mt-6">
        <Table>
          <thead>
            <tr>
              <Th>{t("admin.winners.col.draw")}</Th>
              <Th>{t("admin.winners.col.prize")}</Th>
              <Th>{t("admin.winners.col.number")}</Th>
              <Th>{t("admin.winners.col.first_name")}</Th>
              <Th>{t("admin.winners.col.last_name")}</Th>
              <Th>{t("admin.winners.col.confirmed_at")}</Th>
            </tr>
          </thead>
          <tbody>
            {rows === null && <LoadingRow colSpan={6} />}
            {rows !== null && rows.length === 0 && <EmptyRow colSpan={6} text={t("admin.winners.empty")} />}
            {rows?.map((w) => (
              <tr key={`${w.draw_id}-${w.participant_id}`}>
                <Td>
                  <span className="text-slate-500">#{w.draw_position}</span> {w.draw_title}
                </Td>
                <Td>{w.prize}</Td>
                <Td className="numeric font-semibold">{w.number}</Td>
                <Td>{w.first_name}</Td>
                <Td>{w.last_name}</Td>
                <Td className="text-slate-600">{formatDateTime(w.confirmed_at)}</Td>
              </tr>
            ))}
          </tbody>
        </Table>
      </div>
    </div>
  );
}
