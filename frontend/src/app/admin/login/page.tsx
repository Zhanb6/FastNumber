"use client";

import { useRouter } from "next/navigation";
import { useState, type FormEvent } from "react";
import { adminLogin } from "@/lib/api";
import { errorMessage } from "@/lib/errors";
import { branding } from "@/config/branding";
import { Button, Input } from "@/components/ui";
import { t } from "@/i18n";

export default function AdminLoginPage() {
  const router = useRouter();
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (submitting) return;
    setError(null);
    setSubmitting(true);
    try {
      await adminLogin(login.trim(), password);
      router.replace("/admin");
    } catch (err) {
      setError(errorMessage(err));
      setSubmitting(false);
    }
  };

  return (
    <main className="flex min-h-dvh items-center justify-center bg-slate-50 p-4">
      <form onSubmit={onSubmit} className="w-full max-w-sm rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <p className="text-xs font-semibold tracking-widest text-slate-500 uppercase">{branding.eventName}</p>
        <h1 className="mt-1 text-xl font-semibold text-slate-900">{t("admin.login.title")}</h1>
        <div className="mt-6 flex flex-col gap-4">
          <Input
            label={t("admin.login.login")}
            name="login"
            autoComplete="username"
            value={login}
            onChange={(e) => setLogin(e.target.value)}
            required
            autoFocus
          />
          <Input
            label={t("admin.login.password")}
            name="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          {error && (
            <p role="alert" className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </p>
          )}
          <Button type="submit" size="lg" loading={submitting} className="w-full">
            {submitting ? t("admin.login.submitting") : t("admin.login.submit")}
          </Button>
        </div>
      </form>
    </main>
  );
}
