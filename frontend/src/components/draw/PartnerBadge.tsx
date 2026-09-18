"use client";

import { useEffect, useState } from "react";
import QRCode from "qrcode";
import { branding } from "@/config/branding";
import { t } from "@/i18n";

/**
 * Sponsor badge in the corner of the live screen: Instagram handle and a QR of
 * the partner site. The QR is generated locally (no network) as an SVG so it
 * stays crisp on a 4K stage screen.
 */
export function PartnerBadge() {
  const { partner } = branding;
  const [qr, setQr] = useState<string>("");

  useEffect(() => {
    let alive = true;
    QRCode.toString(partner.site, {
      type: "svg",
      margin: 0,
      errorCorrectionLevel: "M",
      color: { dark: "#0B1020", light: "#FFFFFF" },
    })
      .then((svg) => alive && setQr(svg))
      .catch(() => undefined);
    return () => {
      alive = false;
    };
  }, [partner.site]);

  return (
    <div className="pointer-events-none absolute bottom-[3vh] left-[3vw] flex items-center gap-[1.2vw] text-brand-muted">
      {qr && (
        <div
          aria-hidden="true"
          className="h-[14vh] w-[14vh] rounded-[1vh] bg-white p-[0.8vh] [&>svg]:h-full [&>svg]:w-full"
          dangerouslySetInnerHTML={{ __html: qr }}
        />
      )}
      <div className="leading-tight">
        <p className="text-[1.3vh] font-semibold tracking-[0.25em] uppercase">{t("partner.label")}</p>
        <p className="mt-[0.5vh] text-[3vh] font-bold tracking-tight text-brand-text">{partner.name}</p>
        <p className="mt-[0.4vh] text-[1.9vh]">
          {partner.instagramLabel}
          <span className="mx-[0.6vw] opacity-40">·</span>
          {partner.siteLabel}
        </p>
      </div>
    </div>
  );
}
