import { branding } from "@/config/branding";
import { t } from "@/i18n";

/** Sponsor credit shown under every state of the registration page. */
export function PartnerFooter() {
  const { partner } = branding;
  return (
    <footer className="mt-10 w-full border-t border-white/10 pt-6 text-brand-muted">
      <p className="text-[0.62rem] font-semibold tracking-[0.2em] uppercase">{t("partner.label")}</p>

      <div className="mt-3 flex flex-wrap items-start justify-between gap-x-6 gap-y-4">
        <div className="min-w-0">
          <p className="text-xl font-bold tracking-tight text-brand-text">{partner.name}</p>
          <p className="mt-0.5 text-xs">{t("partner.services")}</p>
          <p className="mt-1 text-[0.68rem] leading-snug">{t("partner.credit")}</p>
        </div>
        <p className="text-[0.62rem] leading-relaxed font-medium tracking-[0.12em] uppercase">
          {t("partner.motto")
            .split("\n")
            .map((line) => (
              <span key={line} className="block">
                {line}
              </span>
            ))}
        </p>
      </div>

      <div className="mt-4 flex flex-wrap gap-3">
        <PartnerLink href={partner.site} label={partner.siteLabel} icon={<GlobeIcon />} />
        <PartnerLink href={partner.instagram} label={partner.instagramLabel} icon={<InstagramIcon />} />
      </div>
    </footer>
  );
}

function PartnerLink({ href, label, icon }: { href: string; label: string; icon: React.ReactNode }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex min-h-11 items-center gap-2 rounded-full border border-white/15 px-4 text-sm text-brand-text transition hover:border-white/35 hover:bg-white/5"
    >
      {icon}
      <span>{label}</span>
      <ExternalIcon />
    </a>
  );
}

const ICON = "h-4 w-4 shrink-0";

function GlobeIcon() {
  return (
    <svg className={ICON} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
      <circle cx="12" cy="12" r="9" />
      <path d="M3 12h18M12 3a15 15 0 0 1 0 18a15 15 0 0 1 0-18" />
    </svg>
  );
}

function InstagramIcon() {
  return (
    <svg className={ICON} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden="true">
      <rect x="3" y="3" width="18" height="18" rx="5" />
      <circle cx="12" cy="12" r="4" />
      <circle cx="17.2" cy="6.8" r="1.1" fill="currentColor" stroke="none" />
    </svg>
  );
}

function ExternalIcon() {
  return (
    <svg className="h-3 w-3 shrink-0 opacity-60" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
      <path d="M14 4h6v6M20 4l-9 9M19 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h5" />
    </svg>
  );
}
