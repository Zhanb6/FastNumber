"use client";

import { useEffect, useState, type FormEvent } from "react";
import { getSettings, isApiError, updateSettings } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import type { FieldsConfig, NameMode, OnMaxReached, Settings, SettingsUpdate } from "@/lib/types";
import { Button, Checkbox, Input, Select, useToast } from "@/components/ui";
import { t } from "@/i18n";

interface FormState {
  event_name: string;
  registration_open: boolean;
  exclude_previous_winners: boolean;
  fields: FieldsConfig;
  name_mode: NameMode;
  on_max_reached: OnMaxReached;
  max_number: string;
  start_number: string;
  duration_ms: string;
}

function toForm(s: Settings): FormState {
  return {
    event_name: s.event_name,
    registration_open: s.registration_open,
    // UI shows the inverse of `allow_previous_winners`
    exclude_previous_winners: !s.allow_previous_winners,
    fields: {
      phone: { ...s.fields.phone },
      email: { ...s.fields.email },
      company: { ...s.fields.company },
    },
    name_mode: s.name_mode,
    on_max_reached: s.on_max_reached,
    max_number: String(s.max_number),
    start_number: String(s.start_number),
    duration_ms: String(s.animation.duration_ms),
  };
}

export default function SettingsPage() {
  const toast = useToast();
  const [settings, setSettings] = useState<Settings | null>(null);
  const [form, setForm] = useState<FormState | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    getSettings().then(
      (s) => {
        setSettings(s);
        setForm(toForm(s));
      },
      (e) => toast.error(errorMessage(e)),
    );
  }, [toast]);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!form || !settings || saving) return;
    setErrors({});

    const body: SettingsUpdate = {
      event_name: form.event_name.trim(),
      registration_open: form.registration_open,
      allow_previous_winners: !form.exclude_previous_winners,
      fields: form.fields,
      name_mode: form.name_mode,
      on_max_reached: form.on_max_reached,
      max_number: Number(form.max_number),
      animation: { duration_ms: Number(form.duration_ms) },
    };
    if (!settings.start_number_locked) body.start_number = Number(form.start_number);

    setSaving(true);
    try {
      const saved = await updateSettings(body);
      setSettings(saved);
      setForm(toForm(saved));
      toast.success(t("admin.settings.saved"));
    } catch (err) {
      if (isApiError(err) && err.status === 422) {
        const fe = err.fieldErrors;
        if (Object.keys(fe).length > 0) setErrors(fe);
        else toast.error(errorMessage(err));
      } else if (isApiError(err) && err.code === "START_NUMBER_LOCKED") {
        setErrors({ start_number: t("error.START_NUMBER_LOCKED") });
        setSettings({ ...settings, start_number_locked: true });
      } else {
        toast.error(errorMessage(err));
      }
    } finally {
      setSaving(false);
    }
  };

  if (!form || !settings) {
    return <p className="text-slate-500">{t("common.loading")}</p>;
  }

  const setField = (name: keyof FieldsConfig, key: "enabled" | "required", value: boolean) =>
    setForm((f) => {
      if (!f) return f;
      const next = { ...f.fields[name], [key]: value };
      if (key === "enabled" && !value) next.required = false;
      if (key === "required" && value) next.enabled = true;
      return { ...f, fields: { ...f.fields, [name]: next } };
    });

  const fieldLabels: Record<keyof FieldsConfig, string> = {
    phone: t("register.phone"),
    email: t("register.email"),
    company: t("register.company"),
  };

  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="text-2xl font-semibold">{t("admin.settings.title")}</h1>

      <form onSubmit={onSubmit} className="mt-6 flex flex-col gap-6">
        <section className="rounded-xl border border-slate-200 bg-white p-5">
          <Input
            label={t("admin.settings.event_name")}
            value={form.event_name}
            onChange={(e) => setForm({ ...form, event_name: e.target.value })}
            error={errors.event_name}
            maxLength={120}
            required
          />
          <Checkbox
            className="mt-4"
            label={t("admin.settings.registration_open")}
            checked={form.registration_open}
            onChange={(e) => setForm({ ...form, registration_open: e.target.checked })}
          />
          <Checkbox
            className="mt-3"
            label={t("admin.settings.exclude_previous_winners")}
            hint={t("admin.settings.exclude_hint")}
            checked={form.exclude_previous_winners}
            onChange={(e) => setForm({ ...form, exclude_previous_winners: e.target.checked })}
          />
        </section>

        <section className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="text-sm font-semibold text-slate-500 uppercase">{t("admin.settings.fields")}</h2>
          <Select
            className="mt-3"
            label={t("admin.settings.name_mode")}
            hint={t("admin.settings.name_mode_hint")}
            value={form.name_mode}
            onChange={(e) => setForm({ ...form, name_mode: e.target.value as NameMode })}
            options={[
              { value: "full", label: t("admin.settings.name_mode.full") },
              { value: "split", label: t("admin.settings.name_mode.split") },
            ]}
            error={errors.name_mode}
          />
          <div className="mt-3 grid gap-3">
            {(Object.keys(fieldLabels) as (keyof FieldsConfig)[]).map((name) => (
              <div key={name} className="flex flex-wrap items-center gap-x-6 gap-y-2 rounded-lg bg-slate-50 px-3 py-2">
                <span className="w-24 text-sm font-medium text-slate-800">{fieldLabels[name]}</span>
                <Checkbox
                  label={t("admin.settings.field_enabled")}
                  checked={form.fields[name].enabled}
                  onChange={(e) => setField(name, "enabled", e.target.checked)}
                />
                <Checkbox
                  label={t("admin.settings.field_required")}
                  checked={form.fields[name].required}
                  onChange={(e) => setField(name, "required", e.target.checked)}
                />
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="text-sm font-semibold text-slate-500 uppercase">{t("admin.settings.numbering")}</h2>
          <div className="mt-3 grid gap-4 sm:grid-cols-2">
            <Input
              label={t("admin.settings.start_number")}
              type="number"
              min={0}
              step={1}
              value={form.start_number}
              onChange={(e) => setForm({ ...form, start_number: e.target.value })}
              disabled={settings.start_number_locked}
              hint={settings.start_number_locked ? t("admin.settings.start_number_locked") : undefined}
              error={errors.start_number}
            />
            <Input
              label={t("admin.settings.max_number")}
              type="number"
              min={0}
              step={1}
              value={form.max_number}
              onChange={(e) => setForm({ ...form, max_number: e.target.value })}
              error={errors.max_number}
            />
            <Select
              className="sm:col-span-2"
              label={t("admin.settings.on_max_reached")}
              value={form.on_max_reached}
              onChange={(e) => setForm({ ...form, on_max_reached: e.target.value as OnMaxReached })}
              options={[
                { value: "continue", label: t("admin.settings.on_max_reached.continue") },
                { value: "close", label: t("admin.settings.on_max_reached.close") },
              ]}
              error={errors.on_max_reached}
            />
          </div>
        </section>

        <section className="rounded-xl border border-slate-200 bg-white p-5">
          <h2 className="text-sm font-semibold text-slate-500 uppercase">{t("admin.settings.animation")}</h2>
          <div className="mt-3 grid gap-4 sm:grid-cols-2">
            <Input
              label={t("admin.settings.animation_duration")}
              type="number"
              min={1000}
              step={100}
              value={form.duration_ms}
              onChange={(e) => setForm({ ...form, duration_ms: e.target.value })}
              error={errors["animation.duration_ms"] ?? errors.animation}
            />
            <Input label={t("admin.settings.timezone")} value={settings.timezone} disabled readOnly />
          </div>
        </section>

        <div className="flex justify-end">
          <Button type="submit" size="lg" loading={saving}>
            {t("common.save")}
          </Button>
        </div>
      </form>
    </div>
  );
}
