import { t } from "@/i18n";
import type { FieldsConfig, NameMode, RegisterBody } from "./types";

/** Cyrillic (incl. Kazakh letters), Latin, space, hyphen, apostrophe. Mirrors the backend rule. */
const NAME_RE = /^[\p{Script=Cyrillic}\p{Script=Latin}\s'’-]+$/u;
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

export const NAME_MAX = 60;
export const COMPANY_MAX = 120;
export const EMAIL_MAX = 254;

export function validateName(value: string): string | null {
  const v = value.trim();
  if (!v) return t("register.validation.required");
  if (v.length > NAME_MAX) return t("register.validation.max_length", { n: NAME_MAX });
  if (!NAME_RE.test(v)) return t("register.validation.name");
  return null;
}

/**
 * Normalise a phone to E.164. Accepts `8XXXXXXXXXX`, `7XXXXXXXXXX`, `+7 (XXX) XXX-XX-XX`.
 * Returns null when the result is not a plausible E.164 number.
 */
export function normalizePhone(raw: string): string | null {
  let digits = raw.replace(/[^\d+]/g, "");
  if (digits.startsWith("+")) digits = `+${digits.slice(1).replace(/\+/g, "")}`;
  else digits = digits.replace(/\+/g, "");
  if (/^8\d{10}$/.test(digits)) digits = `+7${digits.slice(1)}`;
  else if (/^7\d{10}$/.test(digits)) digits = `+${digits}`;
  else if (/^\d{10}$/.test(digits)) digits = `+7${digits}`;
  if (!/^\+\d{10,15}$/.test(digits)) return null;
  return digits;
}

export function validateEmail(value: string): string | null {
  const v = value.trim();
  if (v.length > EMAIL_MAX) return t("register.validation.max_length", { n: EMAIL_MAX });
  if (!EMAIL_RE.test(v)) return t("register.validation.email");
  return null;
}

/** Mirrors the backend: first word is the surname, the rest is the given name. */
export function validateFullName(value: string): string | null {
  const words = value.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return t("register.validation.required");
  if (words.length < 2) return t("register.validation.full_name");
  const last = words[0];
  const first = words.slice(1).join(" ");
  return validateName(first) ?? validateName(last);
}

export interface RegisterFormValues {
  full_name: string;
  first_name: string;
  last_name: string;
  phone: string;
  email: string;
  company: string;
}

export type FieldErrors = Partial<Record<keyof RegisterFormValues, string>>;

/** Client-side validation mirroring the contract; returns errors and a normalised body. */
export function validateRegisterForm(
  values: RegisterFormValues,
  fields: FieldsConfig,
  nameMode: NameMode = "full",
): { errors: FieldErrors; body: Omit<RegisterBody, "device_token"> } {
  const errors: FieldErrors = {};
  const body: Omit<RegisterBody, "device_token"> = {};

  if (nameMode === "full") {
    body.full_name = values.full_name.trim().replace(/\s+/g, " ");
    const err = validateFullName(values.full_name);
    if (err) errors.full_name = err;
  } else {
    body.first_name = values.first_name.trim();
    body.last_name = values.last_name.trim();
    const fn = validateName(values.first_name);
    if (fn) errors.first_name = fn;
    const ln = validateName(values.last_name);
    if (ln) errors.last_name = ln;
  }

  if (fields.phone.enabled) {
    const raw = values.phone.trim();
    if (raw) {
      const normalized = normalizePhone(raw);
      if (!normalized) errors.phone = t("register.validation.phone");
      else body.phone = normalized;
    } else if (fields.phone.required) {
      errors.phone = t("register.validation.required");
    }
  }

  if (fields.email.enabled) {
    const raw = values.email.trim();
    if (raw) {
      const err = validateEmail(raw);
      if (err) errors.email = err;
      else body.email = raw;
    } else if (fields.email.required) {
      errors.email = t("register.validation.required");
    }
  }

  if (fields.company.enabled) {
    const raw = values.company.trim();
    if (raw) {
      if (raw.length > COMPANY_MAX) errors.company = t("register.validation.max_length", { n: COMPANY_MAX });
      else body.company = raw;
    } else if (fields.company.required) {
      errors.company = t("register.validation.required");
    }
  }

  return { errors, body };
}
