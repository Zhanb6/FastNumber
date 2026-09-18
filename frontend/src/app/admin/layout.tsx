"use client";

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { AdminShell } from "@/components/admin/AdminShell";
import { ToastProvider } from "@/components/ui/Toast";

export default function AdminLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  // The login page and the blank screen are shown without the admin chrome or
  // the session guard; everything else under /admin requires a session.
  const bare = pathname === "/admin/login" || pathname === "/admin/LetsGocheck";
  return <ToastProvider>{bare ? children : <AdminShell>{children}</AdminShell>}</ToastProvider>;
}
