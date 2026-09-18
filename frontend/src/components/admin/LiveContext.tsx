"use client";

import { createContext, useContext, type ReactNode } from "react";
import { useLiveSocket, type LiveSocketState } from "@/hooks/useLiveSocket";

const LiveContext = createContext<LiveSocketState | null>(null);

/** One live socket for the whole admin shell (admin session cookie authorises it). */
export function LiveProvider({ enabled, children }: { enabled: boolean; children: ReactNode }) {
  const live = useLiveSocket({ enabled });
  return <LiveContext.Provider value={live}>{children}</LiveContext.Provider>;
}

export function useLive(): LiveSocketState {
  const ctx = useContext(LiveContext);
  if (!ctx) throw new Error("useLive must be used within LiveProvider");
  return ctx;
}
