import { Button } from "./Button";
import { t } from "@/i18n";

interface Props {
  page: number;
  pageSize: number;
  total: number;
  onChange: (page: number) => void;
}

export function Pagination({ page, pageSize, total, onChange }: Props) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  return (
    <nav className="flex flex-wrap items-center justify-between gap-3 text-sm text-slate-600" aria-label="pagination">
      <span>{t("common.total", { n: total })}</span>
      <div className="flex items-center gap-2">
        <Button variant="secondary" size="sm" onClick={() => onChange(page - 1)} disabled={page <= 1}>
          {t("common.prev")}
        </Button>
        <span>{t("common.page_of", { page, pages })}</span>
        <Button variant="secondary" size="sm" onClick={() => onChange(page + 1)} disabled={page >= pages}>
          {t("common.next")}
        </Button>
      </div>
    </nav>
  );
}
