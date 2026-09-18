import type { Metadata, Viewport } from "next";
import type { CSSProperties, ReactNode } from "react";
import "@fontsource-variable/inter/wght.css";
import "./globals.css";
import { branding } from "@/config/branding";

export const metadata: Metadata = {
  title: branding.eventName,
  description: `${branding.eventName} — розыгрыш`,
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: branding.colors.bg,
};

const brandVars = {
  "--brand-bg": branding.colors.bg,
  "--brand-bg2": branding.colors.bg2,
  "--brand-accent": branding.colors.accent,
  "--brand-accent2": branding.colors.accent2,
  "--brand-accent3": branding.colors.accent3,
  "--brand-text": branding.colors.text,
  "--brand-muted": branding.colors.muted,
} as CSSProperties;

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="ru" style={brandVars}>
      <body className="antialiased">{children}</body>
    </html>
  );
}
