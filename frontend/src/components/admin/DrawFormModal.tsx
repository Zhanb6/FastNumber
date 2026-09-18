"use client";

import { useEffect, useState, type FormEvent } from "react";
import { createDraw, isApiError, updateDraw } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import type { DrawCreateBody, DrawView } from "@/lib/types";
import { isoToLocalInput, localInputToIso } from "@/lib/format";
import { Button, Input, Modal, Select, Textarea, useToast } from "@/components/ui";
import { t } from "@/i18n";

interface Props {
  open: boolean;
  /** Existing draw to edit (DRAFT only); undefined = create. */
  draw?: DrawView;
  onClose: () => void;
  onSaved: (draw: DrawView) => void;
}

type ExcludeOption = "null" | "true" | "false";

interface FormState {
  title: string;
  prize: string;
  description: string;
  position: string;
  scheduled_at: string;
  exclude: ExcludeOption;
}

const EMPTY: FormState = { title: "", prize: "", description: "", position: "", scheduled_at: "", exclude: "null" };

function fromDraw(d: DrawView): FormState {
  return {
    title: d.title,
    prize: d.prize,
    description: d.description ?? "",
    position: String(d.position),
    scheduled_at: isoToLocalInput(d.scheduled_at),
    exclude: d.exclude_previous_winners === null ? "null" : d.exclude_previous_winners ? "true" : "false",
  };
}

export function DrawFormModal({ open, draw, onClose, onSaved }: Props) {
  const toast = useToast();
  const [form, setForm] = useState<FormState>(EMPTY);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (open) {
      setForm(draw ? fromDraw(draw) : EMPTY);
      setErrors({});
    }
  }, [open, draw]);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (saving) return;
    const localErrors: Record<string, string> = {};
    if (!form.title.trim()) localErrors.title = t("register.validation.required");
    if (!form.prize.trim()) localErrors.prize = t("register.validation.required");
    if (Object.keys(localErrors).length > 0) {
      setErrors(localErrors);
      return;
    }
    const body: DrawCreateBody = {
      title: form.title.trim(),
      prize: form.prize.trim(),
      description: form.description.trim() || null,
      scheduled_at: localInputToIso(form.scheduled_at),
      exclude_previous_winners: form.exclude === "null" ? null : form.exclude === "true",
    };
    if (form.position.trim() !== "") body.position = Number(form.position);

    setSaving(true);
    try {
      const saved = draw ? await updateDraw(draw.id, body) : await createDraw(body);
      onSaved(saved);
      onClose();
    } catch (err) {
      if (isApiError(err) && err.status === 422 && Object.keys(err.fieldErrors).length > 0) {
        setErrors(err.fieldErrors);
      } else {
        toast.error(errorMessage(err));
      }
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal open={open} title={draw ? t("admin.draws.edit_title") : t("admin.draws.create_title")} onClose={onClose} size="lg">
      <form onSubmit={onSubmit} className="grid gap-4 sm:grid-cols-2">
        <Input
          className="sm:col-span-2"
          label={t("admin.draws.field.title")}
          value={form.title}
          onChange={(e) => setForm({ ...form, title: e.target.value })}
          error={errors.title}
          maxLength={120}
          required
        />
        <Input
          className="sm:col-span-2"
          label={t("admin.draws.field.prize")}
          value={form.prize}
          onChange={(e) => setForm({ ...form, prize: e.target.value })}
          error={errors.prize}
          maxLength={200}
          required
        />
        <Textarea
          className="sm:col-span-2"
          label={t("admin.draws.field.description")}
          value={form.description}
          onChange={(e) => setForm({ ...form, description: e.target.value })}
          error={errors.description}
        />
        <Input
          label={t("admin.draws.field.position")}
          type="number"
          min={1}
          step={1}
          value={form.position}
          onChange={(e) => setForm({ ...form, position: e.target.value })}
          error={errors.position}
        />
        <Input
          label={t("admin.draws.field.scheduled_at")}
          type="datetime-local"
          value={form.scheduled_at}
          onChange={(e) => setForm({ ...form, scheduled_at: e.target.value })}
          error={errors.scheduled_at}
        />
        <Select
          className="sm:col-span-2"
          label={t("admin.draws.field.exclude_previous_winners")}
          value={form.exclude}
          onChange={(e) => setForm({ ...form, exclude: e.target.value as ExcludeOption })}
          options={[
            { value: "null", label: t("common.by_setting") },
            { value: "true", label: t("common.yes") },
            { value: "false", label: t("common.no") },
          ]}
          error={errors.exclude_previous_winners}
        />
        <div className="flex justify-end gap-2 sm:col-span-2">
          <Button variant="secondary" onClick={onClose} disabled={saving}>
            {t("common.cancel")}
          </Button>
          <Button type="submit" loading={saving}>
            {draw ? t("common.save") : t("common.create")}
          </Button>
        </div>
      </form>
    </Modal>
  );
}
