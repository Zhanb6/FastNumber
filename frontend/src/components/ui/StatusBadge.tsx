import type { DrawStatus, LiveState, ParticipantStatus, ResultStatus } from "@/lib/types";
import { tDynamic } from "@/i18n";

type Tone = "green" | "amber" | "red" | "gray" | "blue";

const tones: Record<Tone, string> = {
  green: "bg-emerald-100 text-emerald-800",
  amber: "bg-amber-100 text-amber-800",
  red: "bg-red-100 text-red-800",
  gray: "bg-slate-100 text-slate-700",
  blue: "bg-sky-100 text-sky-800",
};

const toneOf: Record<string, Tone> = {
  ACTIVE: "green",
  DISQUALIFIED: "amber",
  DELETED: "red",
  DRAFT: "gray",
  PENDING_CONFIRMATION: "amber",
  COMPLETED: "green",
  CANCELLED: "red",
  SELECTED: "amber",
  CONFIRMED: "green",
  REJECTED: "red",
  IDLE: "gray",
  COUNTDOWN: "blue",
  DRAWING: "blue",
  WINNER: "amber",
};

interface Props {
  value: ParticipantStatus | DrawStatus | ResultStatus | LiveState;
  kind: "participant.status" | "draw.status" | "result.status" | "live";
}

export function StatusBadge({ value, kind }: Props) {
  const tone = toneOf[value] ?? "gray";
  return (
    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium whitespace-nowrap ${tones[tone]}`}>
      {tDynamic(kind, value)}
    </span>
  );
}
