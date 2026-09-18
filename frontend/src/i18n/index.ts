import { ru, type Dictionary, type TranslationKey } from "./ru";

export type Locale = "ru";

const dictionaries: Record<Locale, Dictionary> = { ru };

/** Single active locale for now; kk/en can be registered above later. */
const locale: Locale = "ru";

export type { TranslationKey };

/**
 * Translate a key with optional `{param}` interpolation.
 * Typed by key so a missing string is a compile-time error.
 */
export function t(key: TranslationKey, params?: Record<string, string | number>): string {
  const raw: string = dictionaries[locale][key];
  if (!params) return raw;
  return raw.replace(/\{(\w+)\}/g, (m, name: string) => (name in params ? String(params[name]) : m));
}

/** True if a translation key exists (used for dynamic enum / error-code keys). */
export function hasKey(key: string): key is TranslationKey {
  return Object.prototype.hasOwnProperty.call(dictionaries[locale], key);
}

/** Translate a dynamic key (e.g. `status.${x}`), falling back to the raw value. */
export function tDynamic(prefix: string, value: string, params?: Record<string, string | number>): string {
  const key = `${prefix}.${value}`;
  return hasKey(key) ? t(key, params) : value;
}
