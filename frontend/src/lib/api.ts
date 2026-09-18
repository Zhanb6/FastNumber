import type {
  AdminStats,
  ApiErrorBody,
  AuditQuery,
  AuditView,
  DrawCreateBody,
  DrawDetail,
  DrawUpdateBody,
  DrawView,
  LiveSnapshot,
  Paginated,
  ParticipantAdmin,
  ParticipantPublic,
  ParticipantsQuery,
  PublicConfig,
  RegisterBody,
  Settings,
  SettingsUpdate,
  WinnerRow,
} from "./types";

/** "" in production (same origin through nginx), http://localhost:8000 in dev. */
export const API_BASE: string = process.env.NEXT_PUBLIC_API_BASE ?? "";

/** Fired on `window` when an admin call returns 401 so the admin shell can redirect. */
export const UNAUTHORIZED_EVENT = "ktf:unauthorized";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>;

  constructor(status: number, code: string, message: string, details?: Record<string, unknown>) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details ?? {};
  }

  /** `details.fields` of a 422 VALIDATION_ERROR, if any. */
  get fieldErrors(): Record<string, string> {
    const fields = this.details["fields"];
    if (fields && typeof fields === "object") {
      const out: Record<string, string> = {};
      for (const [k, v] of Object.entries(fields as Record<string, unknown>)) {
        out[k] = typeof v === "string" ? v : JSON.stringify(v);
      }
      return out;
    }
    return {};
  }
}

export function isApiError(e: unknown): e is ApiError {
  return e instanceof ApiError;
}

function buildQuery(params: Record<string, string | number | boolean | undefined | null>): string {
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    sp.set(k, String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}

export function apiUrl(path: string): string {
  return `${API_BASE}${path}`;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body !== undefined) headers.set("Content-Type", "application/json");

  let res: Response;
  try {
    res = await fetch(apiUrl(path), { ...init, headers, credentials: "include" });
  } catch {
    throw new ApiError(0, "NETWORK_ERROR", "Network error");
  }

  if (res.status === 204) return undefined as T;

  const text = await res.text();
  let json: unknown = null;
  if (text) {
    try {
      json = JSON.parse(text);
    } catch {
      json = null;
    }
  }

  if (!res.ok) {
    const body = json as Partial<ApiErrorBody> | null;
    const err = body?.error;
    const apiError = new ApiError(
      res.status,
      err?.code ?? `HTTP_${res.status}`,
      err?.message ?? res.statusText ?? "Request failed",
      err?.details,
    );
    if (
      res.status === 401 &&
      path.startsWith("/api/admin/") &&
      !path.startsWith("/api/admin/auth/") &&
      typeof window !== "undefined"
    ) {
      window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
    }
    throw apiError;
  }
  return json as T;
}

const get = <T>(path: string) => request<T>(path);
const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });
const put = <T>(path: string, body: unknown) =>
  request<T>(path, { method: "PUT", body: JSON.stringify(body) });
const patch = <T>(path: string, body: unknown) =>
  request<T>(path, { method: "PATCH", body: JSON.stringify(body) });
const del = <T>(path: string) => request<T>(path, { method: "DELETE" });

/* ---------- public ---------- */

export const getPublicConfig = () => get<PublicConfig>("/api/config/public");
export const register = (body: RegisterBody) => post<ParticipantPublic>("/api/register", body);
export const getMe = (token: string) => get<ParticipantPublic>(`/api/me/${encodeURIComponent(token)}`);
export const getLiveCurrent = (key?: string | null) =>
  get<LiveSnapshot>(`/api/live/current${buildQuery({ key })}`);

/* ---------- admin: auth ---------- */

export const adminLogin = (login: string, password: string) =>
  post<{ login: string }>("/api/admin/auth/login", { login, password });
export const adminLogout = () => post<void>("/api/admin/auth/logout");
export const adminMe = () => get<{ login: string }>("/api/admin/auth/me");

/* ---------- admin: stats / live ---------- */

export const getStats = () => get<AdminStats>("/api/admin/stats");
export const liveIdle = () => post<LiveSnapshot>("/api/admin/live/idle");

/* ---------- admin: participants ---------- */

export const listParticipants = (q: ParticipantsQuery) =>
  get<Paginated<ParticipantAdmin>>(`/api/admin/participants${buildQuery({ ...q })}`);
export const disqualifyParticipant = (id: string, reason?: string) =>
  post<ParticipantAdmin>(`/api/admin/participants/${id}/disqualify`, reason ? { reason } : {});
export const restoreParticipant = (id: string) =>
  post<ParticipantAdmin>(`/api/admin/participants/${id}/restore`);
export const deleteParticipant = (id: string) => del<void>(`/api/admin/participants/${id}`);
export const exportParticipantsUrl = (q: Pick<ParticipantsQuery, "q" | "status" | "won">) =>
  apiUrl(`/api/admin/export/participants${buildQuery({ ...q })}`);

/* ---------- admin: draws ---------- */

export const listDraws = () => get<{ items: DrawView[] }>("/api/admin/draws");
export const createDraw = (body: DrawCreateBody) => post<DrawView>("/api/admin/draws", body);
export const getDraw = (id: string) => get<DrawDetail>(`/api/admin/draws/${id}`);
export const updateDraw = (id: string, body: DrawUpdateBody) =>
  patch<DrawView>(`/api/admin/draws/${id}`, body);
export const deleteDraw = (id: string) => del<void>(`/api/admin/draws/${id}`);
export const cancelDraw = (id: string) => post<DrawView>(`/api/admin/draws/${id}/cancel`);
export const startDraw = (id: string) => post<DrawDetail>(`/api/admin/draws/${id}/start`);
export const redrawDraw = (id: string, reason?: string) =>
  post<DrawDetail>(`/api/admin/draws/${id}/redraw`, reason ? { reason } : {});
export const confirmDraw = (id: string) => post<DrawDetail>(`/api/admin/draws/${id}/confirm`);

/* ---------- admin: winners / audit / settings ---------- */

export const getWinners = () => get<{ items: WinnerRow[] }>("/api/admin/winners");
export const exportWinnersUrl = () => apiUrl("/api/admin/export/winners");

export const getAudit = (q: AuditQuery) => get<Paginated<AuditView>>(`/api/admin/audit${buildQuery({ ...q })}`);
export const getAuditActions = () => get<{ items: string[] }>("/api/admin/audit/actions");
export const exportAuditUrl = (q: Pick<AuditQuery, "action" | "draw_id" | "participant_id">) =>
  apiUrl(`/api/admin/export/audit${buildQuery({ ...q })}`);

export const getSettings = () => get<Settings>("/api/admin/settings");
export const updateSettings = (body: SettingsUpdate) => put<Settings>("/api/admin/settings", body);
