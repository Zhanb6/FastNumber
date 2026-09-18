"use client";

import { useEffect, useRef, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { Confetti } from "./Confetti";
import { t } from "@/i18n";

export interface DrawAnimationProps {
  drawTitle: string;
  prize: string;
  winner: { number: number; firstName: string; lastName: string };
  numberPool: number[]; // participant numbers used for the visual shuffle only
  startedAt: number; // server start time, ms
  serverOffsetMs: number; // client clock correction
  durationMs?: number; // default 8000
  onRevealComplete?: () => void;
}

type Phase = "countdown" | "drawing" | "hold" | "winner";

interface Flip {
  at: number; // ms since startedAt
  value: number;
}

const FAST_INTERVAL_MS = 40; // ≈25 flips/s
const SLOWDOWN_FLIPS = 12;
const SLOWDOWN_GROWTH = 1.25;

/** Phase boundaries as fractions of the total duration (spec §10.1 for 8000 ms). */
function phaseAt(elapsed: number, d: number): Phase {
  if (elapsed < d / 8) return "countdown";
  if (elapsed < (d * 7) / 8) return "drawing";
  if (elapsed < d) return "hold";
  return "winner";
}

/**
 * Deterministic flip schedule relative to `startedAt`:
 * fast random numbers from t1 to t2, then 12 flips with geometrically growing
 * intervals (ease-out) ending exactly on the winner at t3.
 */
function buildSchedule(pool: number[], winner: number, d: number): Flip[] {
  const t1 = d / 8;
  const t2 = (d * 5) / 8;
  const t3 = (d * 7) / 8;
  const source = pool.length > 0 ? pool : [winner];
  const pick = (prev: number): number => {
    if (source.length < 2) return source[0];
    let v = prev;
    for (let i = 0; i < 4 && v === prev; i++) v = source[Math.floor(Math.random() * source.length)];
    return v;
  };

  const flips: Flip[] = [];
  let prev = winner;
  for (let at = t1; at < t2; at += FAST_INTERVAL_MS) {
    prev = pick(prev);
    flips.push({ at, value: prev });
  }

  // Slowdown: intervals 40ms * 1.25^k, normalised to fit exactly into [t2, t3].
  const raw: number[] = [];
  let sum = 0;
  for (let k = 0; k < SLOWDOWN_FLIPS; k++) {
    const iv = FAST_INTERVAL_MS * SLOWDOWN_GROWTH ** k;
    raw.push(iv);
    sum += iv;
  }
  const scale = (t3 - t2) / sum;
  let at = t2;
  for (let k = 0; k < SLOWDOWN_FLIPS; k++) {
    at += raw[k] * scale;
    const last = k === SLOWDOWN_FLIPS - 1;
    if (last) {
      flips.push({ at: t3, value: winner });
    } else {
      prev = pick(prev);
      if (prev === winner && k >= SLOWDOWN_FLIPS - 4) prev = pick(winner);
      flips.push({ at, value: prev });
    }
  }
  return flips;
}

export function DrawAnimation({
  drawTitle,
  prize,
  winner,
  numberPool,
  startedAt,
  serverOffsetMs,
  durationMs = 8000,
  onRevealComplete,
}: DrawAnimationProps) {
  const reducedMotion = useReducedMotion() ?? false;
  const reducedRef = useRef(reducedMotion);
  reducedRef.current = reducedMotion;
  const offsetRef = useRef(serverOffsetMs);
  offsetRef.current = serverOffsetMs;
  const revealRef = useRef(onRevealComplete);
  revealRef.current = onRevealComplete;

  const initialElapsed = () => Date.now() + offsetRef.current - startedAt;
  // A screen that (re)opens after the reveal shows the winner card directly, no animation.
  const [joinedLate] = useState(() => initialElapsed() >= durationMs);
  const [phase, setPhase] = useState<Phase>(() => phaseAt(initialElapsed(), durationMs));
  const [confetti, setConfetti] = useState(false);
  const phaseRef = useRef(phase);

  const numberRef = useRef<HTMLSpanElement>(null);
  // Random schedule, generated once per mount (component is keyed by draw id + startedAt).
  const [schedule] = useState<Flip[]>(() =>
    reducedMotion ? [] : buildSchedule(numberPool, winner.number, durationMs),
  );

  useEffect(() => {
    let raf = 0;
    let idx = -1;
    let shown: number | null = null;

    // The span mounts only after COUNTDOWN, so resolve the ref on every write.
    const show = (value: number) => {
      const el = numberRef.current;
      if (el && (value !== shown || el.textContent === "")) {
        el.textContent = String(value);
        shown = value;
      }
    };

    const tick = () => {
      const elapsed = Date.now() + offsetRef.current - startedAt;
      const next = phaseAt(elapsed, durationMs);
      if (next !== phaseRef.current) {
        phaseRef.current = next;
        setPhase(next);
      }
      if (next === "drawing") {
        if (schedule.length === 0 || reducedRef.current) {
          show(winner.number);
        } else {
          while (idx + 1 < schedule.length && schedule[idx + 1].at <= elapsed) idx++;
          show(idx >= 0 ? schedule[idx].value : winner.number);
        }
      } else if (next === "hold" || next === "winner") {
        show(winner.number);
      }
      if (next !== "winner") raf = requestAnimationFrame(tick);
    };
    tick();
    return () => cancelAnimationFrame(raf);
  }, [startedAt, durationMs, schedule, winner.number]);

  useEffect(() => {
    if (phase !== "winner") return;
    if (!joinedLate) setConfetti(true);
    revealRef.current?.();
  }, [phase, joinedLate]);

  const isCountdown = phase === "countdown";
  const isWinner = phase === "winner";
  const fast = reducedMotion ? 0.2 : 0.6;
  const instant = joinedLate;

  return (
    <div className="absolute inset-0 flex flex-col items-center justify-center overflow-hidden pt-[12vh]">
      {/* Title + prize: centered during COUNTDOWN, then docked to the top. */}
      <motion.div
        className="absolute left-0 right-0 top-[6vh] flex flex-col items-center px-[4vw] text-center"
        initial={instant ? false : { opacity: 0, y: "34vh", scale: 1.5 }}
        animate={isCountdown ? { opacity: 1, y: "34vh", scale: 1.5 } : { opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: fast, ease: [0.22, 1, 0.36, 1] }}
      >
        <p className="font-semibold tracking-tight" style={{ fontSize: "clamp(1.5rem, 4.2vh, 6rem)" }}>
          {drawTitle}
        </p>
        <motion.p
          className="mt-[0.8vh] font-medium text-brand-accent"
          style={{ fontSize: "clamp(1.1rem, 2.8vh, 4rem)" }}
          animate={{ opacity: isWinner ? 0 : 1 }}
          transition={{ duration: fast }}
        >
          {prize}
        </motion.p>
      </motion.div>

      {!isCountdown && (
        <motion.div
          className="flex flex-col items-center text-center"
          initial={instant ? false : { opacity: 0, scale: 0.92 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: fast, ease: "easeOut" }}
        >
          <motion.p
            className="font-semibold tracking-[0.35em] text-brand-accent uppercase"
            style={{ fontSize: "clamp(1rem, 3.2vh, 4rem)" }}
            initial={instant ? false : { opacity: 0, y: 20 }}
            animate={isWinner ? { opacity: 1, y: 0 } : { opacity: 0, y: 20 }}
            transition={{ duration: fast, delay: instant ? 0 : 0.1 }}
          >
            {t("draw.winner")}
          </motion.p>

          <motion.div
            className="flex items-baseline justify-center gap-[1.5vw]"
            animate={
              phase === "hold" && !reducedMotion
                ? { scale: [1, 1.035, 1] }
                : isWinner
                  ? { scale: 1 }
                  : { scale: 1 }
            }
            transition={
              phase === "hold" && !reducedMotion
                ? { duration: 0.9, repeat: Infinity, ease: "easeInOut" }
                : { duration: fast }
            }
          >
            <motion.span
              className="font-semibold leading-none text-brand-muted"
              style={{ fontSize: "clamp(2rem, 12vh, 18rem)" }}
              initial={instant ? false : { opacity: 0 }}
              animate={{ opacity: isWinner ? 1 : 0 }}
              transition={{ duration: fast }}
              aria-hidden={!isWinner}
            >
              {t("draw.number_prefix")}
            </motion.span>
            <motion.span
              ref={numberRef}
              className="numeric font-bold leading-none text-brand-text"
              style={{
                fontSize: "44vh",
                textShadow: isWinner ? "0 0 6vh color-mix(in srgb, var(--brand-accent) 45%, transparent)" : "none",
              }}
              animate={isWinner && !instant ? { scale: [1, 1.06, 1] } : { scale: 1 }}
              transition={{ duration: reducedMotion ? 0.2 : 0.8, ease: "easeOut" }}
              aria-live={isWinner ? "polite" : "off"}
            />
          </motion.div>

          <motion.p
            className="font-semibold uppercase"
            style={{ fontSize: "clamp(1.5rem, 7vh, 9rem)", letterSpacing: "0.02em" }}
            initial={instant ? false : { opacity: 0, y: 24 }}
            animate={isWinner ? { opacity: 1, y: 0 } : { opacity: 0, y: 24 }}
            transition={{ duration: fast, delay: instant ? 0 : 0.25 }}
          >
            {winner.firstName} {winner.lastName}
          </motion.p>
          <motion.p
            className="mt-[1.5vh] font-medium text-brand-accent"
            style={{ fontSize: "clamp(1.1rem, 3.6vh, 5rem)" }}
            initial={instant ? false : { opacity: 0 }}
            animate={isWinner ? { opacity: 1 } : { opacity: 0 }}
            transition={{ duration: fast, delay: instant ? 0 : 0.4 }}
          >
            {prize}
          </motion.p>
        </motion.div>
      )}

      {confetti && !reducedMotion && <Confetti onDone={() => setConfetti(false)} />}
      {/* TODO: optional local tick/reveal sounds (spec §10.2); the public snapshot does not expose the flag. */}
    </div>
  );
}
