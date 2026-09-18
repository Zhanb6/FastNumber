import { isApiError } from "./api";
import { t, tDynamic } from "@/i18n";

/** Human-readable message for any thrown error, mapping known API codes via the dictionary. */
export function errorMessage(e: unknown): string {
  if (isApiError(e)) {
    const translated = tDynamic("error", e.code);
    if (translated !== e.code) return translated;
    return e.message || t("common.error");
  }
  if (e instanceof Error && e.message) return e.message;
  return t("common.error");
}
