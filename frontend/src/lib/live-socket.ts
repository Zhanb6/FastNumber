import { API_BASE, getLiveCurrent } from "./api";
import type { LiveEvent, LiveSnapshot } from "./types";

export type LiveConnectionStatus = "connected" | "reconnecting";

export interface LiveSocketOptions {
  /** DRAW_SCREEN_KEY passed through from `/draw?key=` (admin sessions don't need it). */
  key?: string | null;
  onSnapshot: (snapshot: LiveSnapshot) => void;
  onParticipantsCount?: (count: number, serverTime: number) => void;
  onStatus?: (status: LiveConnectionStatus) => void;
  /** Called when the server closes the socket with 4403 (wrong/missing draw key). */
  onForbidden?: () => void;
}

const BACKOFF_MAX_MS = 10_000;
const WATCHDOG_MS = 30_000;
const POLL_MS = 2_000;

export function liveSocketUrl(key?: string | null): string {
  let base: string;
  if (API_BASE) {
    base = API_BASE.replace(/^http/, "ws");
  } else {
    const proto = window.location.protocol === "https:" ? "wss" : "ws";
    base = `${proto}://${window.location.host}`;
  }
  const q = key ? `?key=${encodeURIComponent(key)}` : "";
  return `${base}/ws/live${q}`;
}

/**
 * WebSocket client for `/ws/live` implementing contract §11.1:
 * - after every (re)connect fetch `GET /api/live/current` (DB is the source of truth);
 * - reconnect with backoff 1 → 2 → 4 → … → 10 s;
 * - watchdog: reconnect if nothing arrived for 30 s (server pings every 15 s);
 * - while the socket is down, poll `/api/live/current` every 2 s.
 * Holds no growing state; safe to keep alive for hours.
 */
export class LiveSocketClient {
  private ws: WebSocket | null = null;
  private attempt = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private watchdogTimer: ReturnType<typeof setTimeout> | null = null;
  private pollTimer: ReturnType<typeof setInterval> | null = null;
  private destroyed = false;
  private status: LiveConnectionStatus = "reconnecting";
  private fetchSeq = 0;

  constructor(private readonly opts: LiveSocketOptions) {}

  start(): void {
    this.destroyed = false;
    this.setStatus("reconnecting");
    this.startPolling();
    void this.fetchCurrent();
    this.connect();
  }

  destroy(): void {
    this.destroyed = true;
    this.clearTimers();
    this.stopPolling();
    if (this.ws) {
      const ws = this.ws;
      this.ws = null;
      ws.onopen = ws.onmessage = ws.onerror = ws.onclose = null;
      try {
        ws.close();
      } catch {
        /* ignore */
      }
    }
  }

  private setStatus(next: LiveConnectionStatus): void {
    if (this.status === next) return;
    this.status = next;
    this.opts.onStatus?.(next);
  }

  private connect(): void {
    if (this.destroyed) return;
    let ws: WebSocket;
    try {
      ws = new WebSocket(liveSocketUrl(this.opts.key));
    } catch {
      this.scheduleReconnect();
      return;
    }
    this.ws = ws;

    ws.onopen = () => {
      if (this.ws !== ws) return;
      this.attempt = 0;
      this.setStatus("connected");
      this.stopPolling();
      this.resetWatchdog();
      void this.fetchCurrent();
    };

    ws.onmessage = (ev: MessageEvent) => {
      if (this.ws !== ws) return;
      this.resetWatchdog();
      let data: LiveEvent;
      try {
        data = JSON.parse(String(ev.data)) as LiveEvent;
      } catch {
        return;
      }
      if (!data || typeof data !== "object") return;
      if (data.type === "state") {
        this.opts.onSnapshot(data);
      } else if (data.type === "participants_count") {
        this.opts.onParticipantsCount?.(data.count, data.server_time);
      }
      // "ping" only feeds the watchdog
    };

    ws.onerror = () => {
      /* onclose follows */
    };

    ws.onclose = (ev: CloseEvent) => {
      if (this.ws !== ws) return;
      this.ws = null;
      if (ev.code === 4403) this.opts.onForbidden?.();
      this.handleDown();
    };
  }

  private handleDown(): void {
    if (this.destroyed) return;
    this.setStatus("reconnecting");
    this.startPolling();
    this.scheduleReconnect();
  }

  private scheduleReconnect(): void {
    if (this.destroyed || this.reconnectTimer) return;
    const delay = Math.min(BACKOFF_MAX_MS, 1000 * 2 ** this.attempt);
    this.attempt = Math.min(this.attempt + 1, 10);
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, delay);
  }

  private resetWatchdog(): void {
    if (this.watchdogTimer) clearTimeout(this.watchdogTimer);
    this.watchdogTimer = setTimeout(() => {
      this.watchdogTimer = null;
      // Silent socket: force-close; onclose triggers reconnect.
      if (this.ws) {
        const ws = this.ws;
        this.ws = null;
        ws.onopen = ws.onmessage = ws.onerror = ws.onclose = null;
        try {
          ws.close();
        } catch {
          /* ignore */
        }
        this.handleDown();
      }
    }, WATCHDOG_MS);
  }

  private startPolling(): void {
    if (this.pollTimer || this.destroyed) return;
    this.pollTimer = setInterval(() => void this.fetchCurrent(), POLL_MS);
  }

  private stopPolling(): void {
    if (this.pollTimer) {
      clearInterval(this.pollTimer);
      this.pollTimer = null;
    }
  }

  private clearTimers(): void {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    if (this.watchdogTimer) clearTimeout(this.watchdogTimer);
    this.reconnectTimer = null;
    this.watchdogTimer = null;
  }

  private async fetchCurrent(): Promise<void> {
    const seq = ++this.fetchSeq;
    try {
      const snap = await getLiveCurrent(this.opts.key);
      // Drop stale responses that resolved after a newer fetch or after destroy.
      if (this.destroyed || seq !== this.fetchSeq) return;
      this.opts.onSnapshot(snap);
    } catch {
      /* polling / reconnect will retry */
    }
  }
}
