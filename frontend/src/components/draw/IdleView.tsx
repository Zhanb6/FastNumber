import { branding } from "@/config/branding";
import type { LiveSnapshot } from "@/lib/types";
import { formatInt } from "@/lib/format";
import { t } from "@/i18n";

interface Props {
  snapshot: LiveSnapshot | null;
  paused: boolean;
}

/** IDLE state (spec §9.2): branding, participant counter, next draw, soft ambient background. */
export function IdleView({ snapshot, paused }: Props) {
  const next = snapshot?.next_draw ?? null;
  return (
    <div className="absolute inset-0">
      <div className={`ambient ${paused ? "ambient--paused" : ""}`} aria-hidden="true" />

      <div className="absolute left-[3vw] top-[3.5vh]">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={branding.logo} alt={branding.eventName} className="h-[5vh] w-auto opacity-90" decoding="async" />
      </div>

      <div className="absolute inset-0 flex flex-col items-center justify-center px-[6vw] text-center">
        <h1 className="font-bold leading-[1.02] tracking-tight" style={{ fontSize: "clamp(2.5rem, 11vh, 14rem)" }}>
          {branding.tagline[0]}
          <br />
          <span className="font-light">{branding.tagline[1]}</span>
        </h1>

        <p
          className="mt-[5vh] font-semibold tracking-[0.45em] text-brand-accent uppercase"
          style={{ fontSize: "clamp(1rem, 3.4vh, 4rem)" }}
        >
          {t("draw.heading")}
        </p>

        <p className="mt-[2.5vh] text-brand-muted" style={{ fontSize: "clamp(1rem, 3.4vh, 4rem)" }}>
          {t("draw.participants")}:{" "}
          <span className="numeric font-semibold text-brand-text">
            {snapshot ? formatInt(snapshot.participants_count) : "…"}
          </span>
        </p>

        {next && (
          <div className="mt-[7vh]">
            <p className="tracking-[0.25em] text-brand-muted uppercase" style={{ fontSize: "clamp(0.7rem, 1.8vh, 2rem)" }}>
              {t("draw.next_draw")}
            </p>
            <p className="mt-[1vh] font-semibold" style={{ fontSize: "clamp(1.4rem, 5vh, 6rem)" }}>
              {next.title}
            </p>
            <p className="mt-[0.5vh] text-brand-accent" style={{ fontSize: "clamp(1rem, 3.2vh, 4rem)" }}>
              {next.prize}
            </p>
          </div>
        )}
      </div>

      <div
        className="absolute bottom-[3vh] left-0 right-0 flex items-center justify-center gap-[0.8vw] text-brand-muted"
        style={{ fontSize: "clamp(0.7rem, 1.7vh, 2rem)" }}
      >
        <span className="h-[0.9vh] w-[0.9vh] animate-pulse rounded-full bg-brand-accent/70" aria-hidden="true" />
        {t("draw.waiting")}
      </div>
    </div>
  );
}
