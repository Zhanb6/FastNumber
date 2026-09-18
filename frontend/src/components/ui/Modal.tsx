"use client";

import { useEffect, useId, type ReactNode } from "react";
import { Button } from "./Button";
import { t } from "@/i18n";

interface Props {
  open: boolean;
  title: string;
  onClose: () => void;
  children?: ReactNode;
  footer?: ReactNode;
  size?: "md" | "lg";
}

/** Minimal accessible dialog: Esc / backdrop close, aria-modal, labelled by title. */
export function Modal({ open, title, onClose, children, footer, size = "md" }: Props) {
  const titleId = useId();

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-slate-900/50 p-4 sm:items-center" onMouseDown={onClose}>
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        onMouseDown={(e) => e.stopPropagation()}
        className={`w-full rounded-2xl bg-white p-6 shadow-xl ${size === "lg" ? "max-w-2xl" : "max-w-md"}`}
      >
        <div className="flex items-start justify-between gap-4">
          <h2 id={titleId} className="text-lg font-semibold text-slate-900">
            {title}
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label={t("common.close")}
            className="-mr-2 -mt-2 rounded-lg p-2 text-slate-500 hover:bg-slate-100 hover:text-slate-900"
          >
            <span aria-hidden="true">×</span>
          </button>
        </div>
        {children && <div className="mt-4 text-sm text-slate-700">{children}</div>}
        {footer && <div className="mt-6 flex flex-wrap justify-end gap-2">{footer}</div>}
      </div>
    </div>
  );
}

interface ConfirmProps {
  open: boolean;
  title: string;
  text?: ReactNode;
  confirmLabel?: string;
  danger?: boolean;
  loading?: boolean;
  onConfirm: () => void;
  onClose: () => void;
  children?: ReactNode;
}

export function ConfirmModal({ open, title, text, confirmLabel, danger, loading, onConfirm, onClose, children }: ConfirmProps) {
  return (
    <Modal
      open={open}
      title={title}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={loading}>
            {t("common.cancel")}
          </Button>
          <Button variant={danger ? "danger" : "primary"} onClick={onConfirm} loading={loading}>
            {confirmLabel ?? t("common.confirm")}
          </Button>
        </>
      }
    >
      {text && <p>{text}</p>}
      {children}
    </Modal>
  );
}
