"use client";

import { createContext, useCallback, useContext, useMemo, useRef, useState, type ReactNode } from "react";

type Kind = "error" | "success" | "info";

interface ToastItem {
  id: number;
  kind: Kind;
  text: string;
}

interface ToastApi {
  error: (text: string) => void;
  success: (text: string) => void;
  info: (text: string) => void;
}

const ToastContext = createContext<ToastApi | null>(null);

const TTL_MS = 5000;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const seq = useRef(0);

  const push = useCallback((kind: Kind, text: string) => {
    const id = ++seq.current;
    setItems((list) => [...list.slice(-4), { id, kind, text }]);
    setTimeout(() => setItems((list) => list.filter((i) => i.id !== id)), TTL_MS);
  }, []);

  const api = useMemo<ToastApi>(
    () => ({
      error: (text) => push("error", text),
      success: (text) => push("success", text),
      info: (text) => push("info", text),
    }),
    [push],
  );

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="pointer-events-none fixed right-4 bottom-4 z-[60] flex w-80 max-w-[calc(100vw-2rem)] flex-col gap-2" aria-live="polite">
        {items.map((i) => (
          <div
            key={i.id}
            role={i.kind === "error" ? "alert" : "status"}
            className={`pointer-events-auto rounded-lg px-4 py-3 text-sm shadow-lg ${
              i.kind === "error" ? "bg-red-600 text-white" : i.kind === "success" ? "bg-emerald-600 text-white" : "bg-slate-800 text-white"
            }`}
          >
            {i.text}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within ToastProvider");
  return ctx;
}
