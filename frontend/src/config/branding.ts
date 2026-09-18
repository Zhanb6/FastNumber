/**
 * Event branding. Replace values here and assets in `public/brand/` to reuse
 * the system for another event without touching components.
 */
export const branding = {
  eventName: "Kazakhstan Travel Forum 2026",
  /** Two-line wordmark shown on the registration page and the live screen. */
  tagline: ["KAZAKHSTAN", "TRAVEL FORUM"] as const,
  /** Logo served from `public/brand/`. Light (white) artwork on a dark background. */
  logo: "/brand/logo.svg",
  colors: {
    /** Deep background of the live screen and registration page. */
    bg: "#060A1C",
    /** Secondary background tone for gradients. */
    bg2: "#101A4A",
    /** Primary accent (buttons, highlights). */
    accent: "#5EEAD4",
    /** Secondary accent used in gradients / ambient glow. */
    accent2: "#7DD3FC",
    /** Tertiary accent (ambient glow). */
    accent3: "#A78BFA",
    text: "#F8FAFC",
    muted: "#A3B1C6",
  },
  /** Confetti palette (premium, not gold coins). */
  confetti: ["#F8FAFC", "#5EEAD4", "#7DD3FC", "#A78BFA", "#FDE68A", "#F0ABFC"],
} as const;

export type Branding = typeof branding;
