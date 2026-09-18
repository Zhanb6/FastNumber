"use client";

import { useEffect, useId, useRef, useState } from "react";

export interface NumberReelsProps {
  /** Number the reels must land on. */
  target: number;
  /** Server start time of the draw, ms. */
  startedAt: number;
  /** Ref holding the live client→server clock correction. */
  offsetRef: { current: number };
  durationMs: number;
  /**
   * Render the digits statically, in the same box metrics as the spinning reels:
   * reduced motion, a screen opened after the reveal, or the reels already stopped
   * (static markup drops `overflow: hidden`, so the winner glow is not clipped).
   */
  frozen: boolean;
  className?: string;
  style?: React.CSSProperties;
}

const SPIN_SPEED = 0.012; // digits per ms at full speed (~12 digits/s)
const DECEL_SHARE = 0.28; // share of a reel's spin spent decelerating
const FIRST_STOP_SHARE = 0.55; // the leftmost reel stops after 55 % of the spin window
const MAX_BLUR = 9; // vertical feGaussianBlur stdDeviation at full speed
/** Digits 0–9 plus a trailing 0, which makes the 9→0 wrap seamless. */
const STRIP = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 0];

interface Reel {
  /** Digit this reel lands on. */
  digit: number;
  /** Strip position at spin start, so reels are out of phase with each other. */
  start: number;
  /** Time (since startedAt) at which this reel comes to a stop. */
  stopAt: number;
  constMs: number;
  decelMs: number;
  constDigits: number;
  totalDigits: number;
}

/**
 * One reel per digit: all start together at t = d/8, then stop left to right,
 * the last one exactly at t = 7d/8 where the HOLD phase begins.
 * Each reel's travel is rounded so the constant-speed run plus an ease-out
 * deceleration land precisely on its digit.
 */
function buildReels(target: number, durationMs: number): Reel[] {
  const digits = String(target).split("").map(Number);
  const t1 = durationMs / 8;
  const t3 = (durationMs * 7) / 8;
  const firstStop = t1 + (t3 - t1) * FIRST_STOP_SHARE;
  const n = digits.length;

  return digits.map((digit, i) => {
    const stopAt = n === 1 ? t3 : firstStop + ((t3 - firstStop) * i) / (n - 1);
    const spinMs = stopAt - t1;
    const constMs = spinMs * (1 - DECEL_SHARE);
    const decelMs = spinMs - constMs;
    const constDigits = SPIN_SPEED * constMs;
    // An ease-out with a matching initial velocity covers half of what a constant run would.
    const ideal = constDigits + (SPIN_SPEED * decelMs) / 2;
    const start = (i * 7) % 10;
    const rest = (((digit - start) % 10) + 10) % 10;
    let totalDigits = Math.round((ideal - rest) / 10) * 10 + rest;
    if (totalDigits < constDigits + 2) totalDigits += 10;
    return { digit, start, stopAt, constMs, decelMs, constDigits, totalDigits };
  });
}

/** Strip position and speed (digits/ms) of one reel at `elapsed` ms since startedAt. */
function reelAt(r: Reel, elapsed: number, t1: number): { pos: number; speed: number } {
  if (elapsed <= t1) return { pos: r.start, speed: 0 };
  if (elapsed >= r.stopAt) return { pos: r.start + r.totalDigits, speed: 0 };
  const dt = elapsed - t1;
  if (dt < r.constMs) return { pos: r.start + SPIN_SPEED * dt, speed: SPIN_SPEED };
  const p = (dt - r.constMs) / r.decelMs;
  const decelDigits = r.totalDigits - r.constDigits;
  return {
    pos: r.start + r.constDigits + decelDigits * (1 - (1 - p) ** 2),
    speed: ((2 * decelDigits) / r.decelMs) * (1 - p),
  };
}

export function NumberReels({
  target,
  startedAt,
  offsetRef,
  durationMs,
  frozen,
  className = "",
  style,
}: NumberReelsProps) {
  const [reels] = useState(() => buildReels(target, durationMs));
  const stripRefs = useRef<(HTMLSpanElement | null)[]>([]);
  const blurRefs = useRef<(SVGFEGaussianBlurElement | null)[]>([]);
  const windowRef = useRef<HTMLSpanElement>(null);
  const uid = useId().replace(/[^a-zA-Z0-9]/g, "");

  useEffect(() => {
    if (frozen) return;
    const t1 = durationMs / 8;
    const lastStop = reels[reels.length - 1].stopAt;
    let raf = 0;
    // A cell is exactly as tall as the reel window; measured once per frame, not per reel.
    let cell = 0;

    const tick = () => {
      const elapsed = Date.now() + offsetRef.current - startedAt;
      if (windowRef.current) cell = windowRef.current.clientHeight;
      for (let i = 0; i < reels.length; i++) {
        const strip = stripRefs.current[i];
        if (!strip) continue;
        const { pos, speed } = reelAt(reels[i], elapsed, t1);
        const shift = (((pos % 10) + 10) % 10) * cell;
        strip.style.transform = `translate3d(0, ${-shift}px, 0)`;
        // Vertical-only blur: motion smear along the travel axis, glyphs stay sharp sideways.
        const blur = (speed / SPIN_SPEED) * MAX_BLUR;
        blurRefs.current[i]?.setAttribute("stdDeviation", `0 ${blur.toFixed(2)}`);
        strip.style.filter = blur > 0.5 ? `url(#reel-blur-${uid}-${i})` : "none";
      }
      if (elapsed < lastStop + 60) raf = requestAnimationFrame(tick);
    };
    tick();
    return () => cancelAnimationFrame(raf);
  }, [reels, startedAt, durationMs, offsetRef, frozen, uid]);

  return (
    <span className={`reel-row numeric ${className}`} style={style} aria-hidden="true">
      {!frozen && (
        <svg className="reel-defs" aria-hidden="true">
          <defs>
            {reels.map((_, i) => (
              <filter
                key={i}
                id={`reel-blur-${uid}-${i}`}
                x="-20%"
                y="-50%"
                width="140%"
                height="200%"
                colorInterpolationFilters="sRGB"
              >
                <feGaussianBlur
                  stdDeviation="0 0"
                  ref={(el) => {
                    blurRefs.current[i] = el;
                  }}
                />
              </filter>
            ))}
          </defs>
        </svg>
      )}
      {reels.map((r, i) => (
        <span
          // The key switches with `frozen` so React remounts the strip: a fresh node
          // drops the inline transform left behind by the last animated frame.
          key={`${frozen ? "s" : "r"}${i}`}
          className={`reel-window ${frozen ? "reel-window--open" : ""}`}
          ref={i === 0 ? windowRef : undefined}
        >
          <span
            className="reel-strip"
            ref={(el) => {
              stripRefs.current[i] = el;
            }}
          >
            {frozen ? (
              <span className="reel-cell">{r.digit}</span>
            ) : (
              STRIP.map((digit, k) => (
                <span key={k} className="reel-cell">
                  {digit}
                </span>
              ))
            )}
          </span>
        </span>
      ))}
    </span>
  );
}
