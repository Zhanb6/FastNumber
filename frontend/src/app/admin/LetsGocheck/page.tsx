"use client";

import { useEffect, useState } from "react";
import { isApiError, listDraws } from "@/lib/api";
import type { DrawView } from "@/lib/types";

const REFRESH_MS = 5000;

/** Plain, unlinked screen: a listbox of every draw by its number and title. */
export default function DrawListPage() {
  const [draws, setDraws] = useState<DrawView[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string>("");

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const { items } = await listDraws();
        if (!alive) return;
        setDraws(items);
        setError(null);
      } catch (e) {
        if (!alive) return;
        setError(isApiError(e) && e.status === 401 ? "Нужен вход в админку" : "Не удалось загрузить");
      }
    };
    void load();
    const timer = setInterval(load, REFRESH_MS);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, []);

  return (
    <div className="min-h-dvh bg-white p-6 text-black">
      {error && <p className="text-sm">{error}</p>}

      {draws && (
        <select
          size={Math.min(Math.max(draws.length, 4), 20)}
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          className="w-full max-w-2xl rounded border border-black/20 p-2 text-base"
        >
          {draws.map((d) => (
            <option key={d.id} value={d.id}>
              {d.position}. {d.title}
            </option>
          ))}
          {draws.length === 0 && <option disabled>Розыгрышей нет</option>}
        </select>
      )}
    </div>
  );
}
