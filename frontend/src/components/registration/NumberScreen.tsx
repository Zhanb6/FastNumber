import type { ParticipantPublic } from "@/lib/types";
import { fullName } from "@/lib/format";
import { t } from "@/i18n";

interface Props {
  participant: ParticipantPublic;
  onNotMe: () => void;
}

/** Spec §4.2: the number is the hero, nothing else competes with it. */
export function NumberScreen({ participant, onNotMe }: Props) {
  return (
    <section className="flex flex-col items-center text-center">
      <p className="text-base text-brand-muted">{t("register.registered")}</p>
      <p className="mt-8 text-xs font-semibold tracking-[0.3em] text-brand-accent uppercase">{t("register.your_number")}</p>
      <p
        className="numeric mt-2 font-bold leading-none text-brand-text"
        style={{ fontSize: "clamp(5.5rem, 30vw, 9rem)" }}
        aria-label={`${t("register.your_number")} ${participant.number}`}
      >
        {participant.number}
      </p>
      <p className="mt-6 text-2xl font-medium">{fullName(participant)}</p>
      <p className="mt-10 text-base leading-relaxed text-brand-muted">
        {t("register.keep_number")}
        <br />
        {t("register.wait_draw")}
      </p>
      <p className="mt-3 text-sm text-brand-muted/80">{t("register.screenshot_hint")}</p>
      <button type="button" onClick={onNotMe} className="mt-14 text-sm text-brand-muted underline underline-offset-4">
        {t("register.not_me")}
      </button>
    </section>
  );
}
