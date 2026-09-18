/** TypeScript mirrors of docs/API_CONTRACT.md shapes. */

export type ParticipantStatus = "ACTIVE" | "DISQUALIFIED" | "DELETED";
export type DrawStatus = "DRAFT" | "PENDING_CONFIRMATION" | "COMPLETED" | "CANCELLED";
export type ResultStatus = "SELECTED" | "CONFIRMED" | "REJECTED";
export type LiveState = "IDLE" | "COUNTDOWN" | "DRAWING" | "WINNER" | "COMPLETED";
export type OnMaxReached = "continue" | "close";

export interface ApiErrorBody {
  error: { code: string; message: string; details?: Record<string, unknown> };
}

export interface ParticipantPublic {
  id: string;
  number: number;
  first_name: string;
  last_name: string;
  token: string;
  created_at: string;
}

export interface ParticipantShort {
  id: string;
  number: number;
  first_name: string;
  last_name: string;
}

export interface ParticipantAdmin {
  id: string;
  number: number;
  first_name: string;
  last_name: string;
  phone: string | null;
  email: string | null;
  company: string | null;
  status: ParticipantStatus;
  status_reason: string | null;
  created_at: string;
  has_won: boolean;
  pending_result: boolean;
}

export interface DrawResultView {
  id: string;
  status: ResultStatus;
  participant: ParticipantShort;
  eligible_count: number;
  eligible_hash: string;
  reason: string | null;
  created_at: string;
}

export interface DrawView {
  id: string;
  position: number;
  title: string;
  prize: string;
  description: string | null;
  status: DrawStatus;
  exclude_previous_winners: boolean | null;
  scheduled_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  winner: ParticipantShort | null;
  current_result: DrawResultView | null;
}

export interface DrawDetail extends DrawView {
  eligible_count: number;
  effective_exclude_previous_winners: boolean;
  results: DrawResultView[];
}

export interface LiveDraw {
  id: string;
  title: string;
  prize: string;
  started_at: number | null;
}

export interface LiveNextDraw {
  id: string;
  title: string;
  prize: string;
}

export interface LiveWinner {
  number: number;
  first_name: string;
  last_name: string;
}

export interface LiveSnapshot {
  type: "state";
  state: LiveState;
  server_time: number;
  participants_count: number;
  event_name: string;
  animation_duration_ms: number;
  draw: LiveDraw | null;
  next_draw: LiveNextDraw | null;
  winner: LiveWinner | null;
  number_pool: number[] | null;
}

export interface ParticipantsCountEvent {
  type: "participants_count";
  count: number;
  server_time: number;
}

export interface PingEvent {
  type: "ping";
  server_time: number;
}

export type LiveEvent = LiveSnapshot | ParticipantsCountEvent | PingEvent;

export interface FieldConfig {
  enabled: boolean;
  required: boolean;
}

export interface FieldsConfig {
  phone: FieldConfig;
  email: FieldConfig;
  company: FieldConfig;
}

export type NameMode = "split" | "full";

export interface Settings {
  event_name: string;
  event_slug: string;
  registration_open: boolean;
  allow_previous_winners: boolean;
  start_number: number;
  start_number_locked: boolean;
  max_number: number;
  on_max_reached: OnMaxReached;
  name_mode: NameMode;
  timezone: string;
  fields: FieldsConfig;
  animation: { duration_ms: number; sound: boolean };
}

export interface SettingsUpdate {
  event_name?: string;
  registration_open?: boolean;
  allow_previous_winners?: boolean;
  start_number?: number;
  max_number?: number;
  on_max_reached?: OnMaxReached;
  name_mode?: NameMode;
  fields?: Partial<Record<keyof FieldsConfig, Partial<FieldConfig>>>;
  animation?: { duration_ms?: number; sound?: boolean };
}

export interface PublicConfig {
  event_name: string;
  registration_open: boolean;
  name_mode: NameMode;
  fields: FieldsConfig;
}

export interface RegisterBody {
  /** One "Фамилия Имя Отчество" input (name_mode = "full"). */
  full_name?: string;
  first_name?: string;
  last_name?: string;
  phone?: string;
  email?: string;
  company?: string;
  device_token?: string;
}

export interface AuditView {
  id: number;
  action: string;
  entity_type: string;
  entity_id: string | null;
  participant_id: string | null;
  draw_id: string | null;
  admin_login: string | null;
  ip: string | null;
  metadata: Record<string, unknown> | null;
  created_at: string;
}

export interface Paginated<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface AdminStats {
  total_participants: number;
  today_participants: number;
  draws_completed: number;
  winners_count: number;
  registration_open: boolean;
  event_name: string;
  timezone: string;
  public_base_url: string;
  live_state: LiveState;
}

export interface WinnerRow {
  draw_id: string;
  draw_position: number;
  draw_title: string;
  prize: string;
  participant_id: string;
  number: number;
  first_name: string;
  last_name: string;
  confirmed_at: string;
}

export type ParticipantSort = "number" | "-number" | "created_at" | "-created_at";
export type ParticipantStatusFilter = ParticipantStatus | "all" | "";

export interface ParticipantsQuery {
  q?: string;
  status?: ParticipantStatusFilter;
  won?: "" | "true" | "false";
  page?: number;
  page_size?: number;
  sort?: ParticipantSort;
}

export interface AuditQuery {
  action?: string;
  draw_id?: string;
  participant_id?: string;
  page?: number;
  page_size?: number;
}

export interface DrawCreateBody {
  title: string;
  prize: string;
  description?: string | null;
  position?: number;
  scheduled_at?: string | null;
  exclude_previous_winners?: boolean | null;
}

export type DrawUpdateBody = Partial<DrawCreateBody>;
