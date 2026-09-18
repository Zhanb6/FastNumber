"use client";

import { useEffect, useRef, useState } from "react";
import { LiveSocketClient, type LiveConnectionStatus } from "@/lib/live-socket";
import type { LiveSnapshot } from "@/lib/types";

export interface UseLiveSocketOptions {
  key?: string | null;
  /** Set to false to keep the socket closed (e.g. before auth resolves). */
  enabled?: boolean;
}

export interface LiveSocketState {
  snapshot: LiveSnapshot | null;
  status: LiveConnectionStatus;
  /** `server_time - Date.now()` from the latest snapshot; add to Date.now() to get server time. */
  serverOffsetMs: number;
  forbidden: boolean;
}

/**
 * React binding for `LiveSocketClient`. `participants_count` events are merged into the
 * snapshot so consumers can read a single object.
 */
export function useLiveSocket({ key = null, enabled = true }: UseLiveSocketOptions = {}): LiveSocketState {
  const [snapshot, setSnapshot] = useState<LiveSnapshot | null>(null);
  const [status, setStatus] = useState<LiveConnectionStatus>("reconnecting");
  const [serverOffsetMs, setServerOffsetMs] = useState(0);
  const [forbidden, setForbidden] = useState(false);
  const offsetRef = useRef(0);

  useEffect(() => {
    if (!enabled) return;
    const client = new LiveSocketClient({
      key,
      onSnapshot: (snap) => {
        const offset = snap.server_time - Date.now();
        // Only re-render for the offset when it drifts noticeably.
        if (Math.abs(offset - offsetRef.current) > 250) {
          offsetRef.current = offset;
          setServerOffsetMs(offset);
        }
        setForbidden(false);
        setSnapshot(snap);
      },
      onParticipantsCount: (count) => {
        setSnapshot((prev) => (prev && prev.participants_count !== count ? { ...prev, participants_count: count } : prev));
      },
      onStatus: setStatus,
      onForbidden: () => setForbidden(true),
    });
    client.start();
    return () => client.destroy();
  }, [key, enabled]);

  return { snapshot, status, serverOffsetMs, forbidden };
}
