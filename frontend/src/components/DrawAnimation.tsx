"use client";

import { useEffect, useRef, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { Confetti } from "./Confetti";
import { NumberReels } from "./draw/NumberReels";
import { t } from "@/i18n";

export interface DrawAnimationProps {
  drawTitle: string;
  prize: string;
  winner: { number: number; firstName: string; lastName: string };
  startedAt: number; // server start time, ms
  serverOffsetMs: number; // client clock correction
  durationMs?: number; // default 8000
  onRevealComplete?: () => void;
}

type Phase = "countdown" | "drawing" | "hold" | "winner";

/** Phase boundaries as fractions of the total duration (spec §10.1 for 8000 ms). */
function phaseAt(elapsed: number, d: number): Phase {
  if (elapsed < d / 8) return "countdown";
  if (elapsed < (d * 7) / 8) return "drawing";
  if (elapsed < d) return "hold";
  return "winner";
}

export function DrawAnimation({
  drawTitle,
  prize,
  winner,
  startedAt,
  serverOffsetMs,
  durationMs = 8000,
  onRevealComplete,
}: DrawAnimationProps) {
  const reducedMotion = useReducedMotion() ?? false;
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

  useEffect(() => {
    let raf = 0;
    const tick = () => {
      const elapsed = Date.now() + offsetRef.current - startedAt;
      const next = phaseAt(elapsed, durationMs);
      if (next !== phaseRef.current) {
        phaseRef.current = next;
        setPhase(next);
      }
      if (next !== "winner") raf = requestAnimationFrame(tick);
    };
    tick();
    return () => cancelAnimationFrame(raf);
  }, [startedAt, durationMs]);

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
            className="relative flex items-center justify-center"
            animate={
              phase === "hold" && !reducedMotion
                ? { scale: [1, 1.035, 1] }
                : isWinner && !instant
                  ? { scale: [1, 1.06, 1] }
                  : { scale: 1 }
            }
            transition={
              phase === "hold" && !reducedMotion
                ? { duration: 0.9, repeat: Infinity, ease: "easeInOut" }
                : { duration: reducedMotion ? 0.2 : 0.8, ease: "easeOut" }
            }
          >
            {/* Absolute, so the digits stay dead centre in every phase. */}
            <motion.span
              className="absolute right-full mr-[1.5vw] font-semibold leading-none text-brand-muted"
              style={{ fontSize: "clamp(2rem, 12vh, 18rem)" }}
              initial={instant ? false : { opacity: 0 }}
              animate={{ opacity: isWinner ? 1 : 0 }}
              transition={{ duration: fast }}
              aria-hidden="true"
            >
              {t("draw.number_prefix")}
            </motion.span>
            <NumberReels
              target={winner.number}
              startedAt={startedAt}
              offsetRef={offsetRef}
              durationMs={durationMs}
              frozen={instant || reducedMotion || phase === "hold" || isWinner}
              className="font-bold text-brand-text"
              style={{
                fontSize: "40vh",
                textShadow: isWinner
                  ? "0 0 6vh color-mix(in srgb, var(--brand-accent) 45%, transparent)"
                  : "none",
              }}
            />
            <span className="sr-only" aria-live="polite">
              {isWinner ? `${t("draw.number_prefix")} ${winner.number}` : ""}
            </span>
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
