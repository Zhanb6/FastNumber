import { branding } from "@/config/branding";

/** Logo + two-line wordmark. Plain markup (no client JS). */
export function BrandHeader({ compact = false }: { compact?: boolean }) {
  return (
    <header className="flex flex-col items-center text-center">
      {/* Static brand asset from public/brand; next/image would only add JS here. */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={branding.logo}
        alt={branding.eventName}
        width={40}
        height={40}
        className={compact ? "h-9 w-auto" : "h-14 w-auto"}
        decoding="async"
      />
      <p
        className={
          compact
            ? "mt-3 text-[0.6rem] font-semibold tracking-[0.3em] text-brand-muted uppercase"
            : "mt-5 text-[0.7rem] font-semibold tracking-[0.35em] text-brand-muted uppercase"
        }
      >
          {branding.tagline[0]}
          <span className="mx-2 opacity-50">·</span>
          {branding.tagline[1]}
      </p>
    </header>
  );
}
