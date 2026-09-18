import type { ReactNode } from "react";
import { t } from "@/i18n";

export function Table({ children }: { children: ReactNode }) {
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
      <table className="w-full min-w-max text-left text-sm">{children}</table>
    </div>
  );
}

export function Th({ children, className = "" }: { children?: ReactNode; className?: string }) {
  return (
    <th scope="col" className={`border-b border-slate-200 bg-slate-50 px-3 py-2.5 text-xs font-semibold tracking-wide text-slate-600 uppercase ${className}`}>
      {children}
    </th>
  );
}

export function Td({ children, className = "" }: { children?: ReactNode; className?: string }) {
  return <td className={`border-b border-slate-100 px-3 py-2.5 align-middle text-slate-800 ${className}`}>{children}</td>;
}

export function EmptyRow({ colSpan, text }: { colSpan: number; text?: string }) {
  return (
    <tr>
      <td colSpan={colSpan} className="px-3 py-10 text-center text-slate-500">
        {text ?? t("common.empty")}
      </td>
    </tr>
  );
}

export function LoadingRow({ colSpan }: { colSpan: number }) {
  return (
    <tr>
      <td colSpan={colSpan} className="px-3 py-10 text-center text-slate-500">
        {t("common.loading")}
      </td>
    </tr>
  );
}
