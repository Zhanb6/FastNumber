"use client";

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { AdminShell } from "@/components/admin/AdminShell";
import { ToastProvider } from "@/components/ui/Toast";

export default function AdminLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const isLogin = pathname === "/admin/login";
  return <ToastProvider>{isLogin ? children : <AdminShell>{children}</AdminShell>}</ToastProvider>;
}
