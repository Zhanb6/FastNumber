"use client";

import { useEffect, useRef } from "react";
import { branding } from "@/config/branding";

interface Particle {
  x: number;
  y: number;
  vx: number;
  vy: number;
  w: number;
  h: number;
  rot: number;
  vrot: number;
  color: string;
  shape: 0 | 1; // 0 = rect, 1 = circle
  wobble: number;
  wobbleSpeed: number;
}

interface Props {
  /** Total lifetime; the canvas clears itself and stops afterwards. */
  durationMs?: number;
  particleCount?: number;
  onDone?: () => void;
}

/**
 * Lightweight canvas confetti: ~200 particles, one rAF loop, DPR-aware,
 * stops and clears itself after `durationMs`. No allocation in the loop.
 */
export function Confetti({ durationMs = 5000, particleCount = 220, onDone }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const onDoneRef = useRef(onDone);
  onDoneRef.current = onDone;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const palette = branding.confetti;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    let width = 0;
    let height = 0;

    const resize = () => {
      width = window.innerWidth;
      height = window.innerHeight;
      canvas.width = Math.floor(width * dpr);
      canvas.height = Math.floor(height * dpr);
      canvas.style.width = `${width}px`;
      canvas.style.height = `${height}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    resize();
    window.addEventListener("resize", resize);

    // Two bursts from the lower corners plus a gentle rain from the top.
    const particles: Particle[] = [];
    const rand = (a: number, b: number) => a + Math.random() * (b - a);
    for (let i = 0; i < particleCount; i++) {
      const source = i % 3;
      let x: number;
      let y: number;
      let vx: number;
      let vy: number;
      if (source === 0) {
        x = rand(0, width * 0.15);
        y = height * rand(0.55, 0.8);
        vx = rand(4, 11);
        vy = rand(-16, -8);
      } else if (source === 1) {
        x = rand(width * 0.85, width);
        y = height * rand(0.55, 0.8);
        vx = rand(-11, -4);
        vy = rand(-16, -8);
      } else {
        x = rand(0, width);
        y = rand(-height * 0.3, -10);
        vx = rand(-1, 1);
        vy = rand(1, 3);
      }
      const size = rand(6, 13);
      particles.push({
        x,
        y,
        vx,
        vy,
        w: size,
        h: size * rand(0.4, 0.7),
        rot: rand(0, Math.PI * 2),
        vrot: rand(-0.2, 0.2),
        color: palette[i % palette.length],
        shape: Math.random() < 0.25 ? 1 : 0,
        wobble: rand(0, Math.PI * 2),
        wobbleSpeed: rand(0.05, 0.12),
      });
    }

    const gravity = 0.28;
    const drag = 0.985;
    const start = performance.now();
    let raf = 0;
    let done = false;

    const frame = (now: number) => {
      const elapsed = now - start;
      if (elapsed >= durationMs) {
        ctx.clearRect(0, 0, width, height);
        done = true;
        onDoneRef.current?.();
        return;
      }
      const fade = elapsed > durationMs - 1200 ? (durationMs - elapsed) / 1200 : 1;
      ctx.clearRect(0, 0, width, height);
      for (let i = 0; i < particles.length; i++) {
        const p = particles[i];
        p.vy += gravity;
        p.vx *= drag;
        p.vy *= drag;
        p.wobble += p.wobbleSpeed;
        p.x += p.vx + Math.sin(p.wobble) * 0.8;
        p.y += p.vy;
        p.rot += p.vrot;
        if (p.y > height + 20) continue;
        ctx.save();
        ctx.globalAlpha = fade;
        ctx.translate(p.x, p.y);
        ctx.rotate(p.rot);
        ctx.fillStyle = p.color;
        if (p.shape === 1) {
          ctx.beginPath();
          ctx.arc(0, 0, p.h * 0.6, 0, Math.PI * 2);
          ctx.fill();
        } else {
          // Fake 3D flip by scaling the height with the wobble.
          ctx.fillRect(-p.w / 2, (-p.h / 2) * Math.cos(p.wobble), p.w, p.h * Math.cos(p.wobble));
        }
        ctx.restore();
      }
      raf = requestAnimationFrame(frame);
    };
    raf = requestAnimationFrame(frame);

    return () => {
      if (!done) cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
      ctx.clearRect(0, 0, width, height);
    };
  }, [durationMs, particleCount]);

  return <canvas ref={canvasRef} aria-hidden="true" className="pointer-events-none absolute inset-0 z-20" />;
}
