"use client";

import { useId, useState, type FormEvent } from "react";
import { isApiError, register } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import type { FieldsConfig, ParticipantPublic } from "@/lib/types";
import { validateRegisterForm, type FieldErrors, type RegisterFormValues } from "@/lib/validation";
import { t } from "@/i18n";

interface Props {
  fields: FieldsConfig;
  deviceToken: string | null;
  onRegistered: (p: ParticipantPublic) => void;
  onClosed: () => void;
}

const EMPTY: RegisterFormValues = { first_name: "", last_name: "", phone: "", email: "", company: "" };

export function RegisterForm({ fields, deviceToken, onRegistered, onClosed }: Props) {
  const [values, setValues] = useState<RegisterFormValues>(EMPTY);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const set = (name: keyof RegisterFormValues) => (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setValues((v) => ({ ...v, [name]: value }));
    if (errors[name]) setErrors((er) => ({ ...er, [name]: undefined }));
  };

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (submitting) return;
    setFormError(null);
    const { errors: clientErrors, body } = validateRegisterForm(values, fields);
    if (Object.keys(clientErrors).length > 0) {
      setErrors(clientErrors);
      return;
    }
    setSubmitting(true);
    try {
      const participant = await register(deviceToken ? { ...body, device_token: deviceToken } : body);
      onRegistered(participant);
    } catch (err) {
      if (isApiError(err)) {
        if (err.status === 422) {
          const fe = err.fieldErrors;
          if (Object.keys(fe).length > 0) {
            setErrors(fe as FieldErrors);
          } else {
            setFormError(errorMessage(err));
          }
        } else if (err.code === "REGISTRATION_CLOSED") {
          onClosed();
        } else {
          setFormError(errorMessage(err));
        }
      } else {
        setFormError(errorMessage(err));
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
      <div className="mb-2 text-center">
        <h1 className="text-2xl font-semibold">{t("register.form_title")}</h1>
        <p className="mt-2 text-sm text-brand-muted">{t("register.form_subtitle")}</p>
      </div>

      <Field
        label={t("register.first_name")}
        name="first_name"
        value={values.first_name}
        onChange={set("first_name")}
        error={errors.first_name}
        autoComplete="given-name"
        required
      />
      <Field
        label={t("register.last_name")}
        name="last_name"
        value={values.last_name}
        onChange={set("last_name")}
        error={errors.last_name}
        autoComplete="family-name"
        required
      />
      {fields.phone.enabled && (
        <Field
          label={t("register.phone")}
          name="phone"
          type="tel"
          inputMode="tel"
          placeholder={t("register.phone_placeholder")}
          value={values.phone}
          onChange={set("phone")}
          error={errors.phone}
          autoComplete="tel"
          required={fields.phone.required}
        />
      )}
      {fields.email.enabled && (
        <Field
          label={t("register.email")}
          name="email"
          type="email"
          inputMode="email"
          value={values.email}
          onChange={set("email")}
          error={errors.email}
          autoComplete="email"
          required={fields.email.required}
        />
      )}
      {fields.company.enabled && (
        <Field
          label={t("register.company")}
          name="company"
          value={values.company}
          onChange={set("company")}
          error={errors.company}
          autoComplete="organization"
          required={fields.company.required}
        />
      )}

      {formError && (
        <p role="alert" className="rounded-lg bg-red-500/15 px-3 py-2 text-sm text-red-200">
          {formError}
        </p>
      )}

      <button
        type="submit"
        disabled={submitting}
        aria-busy={submitting}
        className="mt-2 inline-flex h-14 w-full items-center justify-center rounded-xl bg-brand-accent text-lg font-semibold text-slate-950 transition active:scale-[0.99] disabled:opacity-70"
      >
        {submitting ? t("register.submitting") : t("register.submit")}
      </button>
    </form>
  );
}

interface FieldProps {
  label: string;
  name: string;
  value: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  error?: string;
  type?: string;
  inputMode?: React.HTMLAttributes<HTMLInputElement>["inputMode"];
  placeholder?: string;
  autoComplete?: string;
  required?: boolean;
}

function Field({ label, name, value, onChange, error, type = "text", inputMode, placeholder, autoComplete, required }: FieldProps) {
  const id = useId();
  const errorId = `${id}-error`;
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-sm font-medium text-brand-text">
        {label}
        {!required && <span className="ml-1 font-normal text-brand-muted">({t("common.optional")})</span>}
      </label>
      <input
        id={id}
        name={name}
        type={type}
        inputMode={inputMode}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        autoComplete={autoComplete}
        required={required}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : undefined}
        maxLength={name === "company" ? 120 : name === "email" ? 254 : 60}
        className={`h-14 w-full rounded-xl border bg-white px-4 text-lg text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-accent ${
          error ? "border-red-400" : "border-transparent"
        }`}
      />
      {error && (
        <p id={errorId} className="mt-1.5 text-sm text-red-300">
          {error}
        </p>
      )}
    </div>
  );
}
