"use client";

import { useEffect, useRef, useState, useCallback } from "react";

type AvatarSize = "badge" | "header" | "cta";

const SIZE_MAP: Record<AvatarSize, number> = {
  badge: 48,
  header: 38,
  cta: 64,
};

// SVG paths for mouth states
const MOUTH_CLOSED = "M 16 28 Q 20 30 24 28";
const MOUTH_OPEN = "M 16 28 Q 20 34 24 28";

interface PriyaAvatarProps {
  size?: AvatarSize;
  isSpeaking?: boolean;
}

export default function PriyaAvatar({ size = "badge", isSpeaking = false }: PriyaAvatarProps) {
  const [mouthOpen, setMouthOpen] = useState(false);
  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);
  const prefersReducedMotion = useRef(false);

  useEffect(() => {
    if (typeof window !== "undefined") {
      prefersReducedMotion.current = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    }
  }, []);

  useEffect(() => {
    if (isSpeaking) {
      if (prefersReducedMotion.current) {
        // Static open-mouth for reduced-motion users
        setMouthOpen(true);
      } else {
        // Animate mouth every 280ms
        intervalRef.current = setInterval(() => {
          setMouthOpen((prev) => !prev);
        }, 280);
      }

      // 30-second safety timeout
      timeoutRef.current = setTimeout(() => {
        if (intervalRef.current) clearInterval(intervalRef.current);
        setMouthOpen(false);
      }, 30000);
    } else {
      // Stop animation
      if (intervalRef.current) clearInterval(intervalRef.current);
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      setMouthOpen(false);
    }

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, [isSpeaking]);

  const px = SIZE_MAP[size];
  const mouthPath = mouthOpen ? MOUTH_OPEN : MOUTH_CLOSED;

  return (
    <svg
      width={px}
      height={px}
      viewBox="0 0 40 40"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      role="img"
      aria-label="Priya AI Avatar"
      className="rounded-full"
    >
      {/* Face background */}
      <circle cx="20" cy="20" r="18" fill="#FFD8B1" />
      {/* Hair */}
      <path d="M 6 18 C 6 8 34 8 34 18 C 34 12 6 12 6 18" fill="#2D1B0E" />
      <ellipse cx="6" cy="22" rx="3" ry="6" fill="#2D1B0E" />
      <ellipse cx="34" cy="22" rx="3" ry="6" fill="#2D1B0E" />
      {/* Eyes */}
      <ellipse cx="14" cy="20" rx="2" ry="2.5" fill="#2D1B0E" />
      <ellipse cx="26" cy="20" rx="2" ry="2.5" fill="#2D1B0E" />
      {/* Eye highlights */}
      <circle cx="14.5" cy="19" r="0.8" fill="white" />
      <circle cx="26.5" cy="19" r="0.8" fill="white" />
      {/* Eyebrows */}
      <path d="M 11 16 Q 14 14 17 16" stroke="#2D1B0E" strokeWidth="0.8" fill="none" />
      <path d="M 23 16 Q 26 14 29 16" stroke="#2D1B0E" strokeWidth="0.8" fill="none" />
      {/* Nose */}
      <path d="M 19 22 Q 20 24 21 22" stroke="#C8956C" strokeWidth="0.6" fill="none" />
      {/* Mouth - animated */}
      <path d={mouthPath} stroke="#C0392B" strokeWidth="1.2" fill={mouthOpen ? "#E74C3C" : "none"} />
      {/* Bindi */}
      <circle cx="20" cy="14" r="1" fill="#E74C3C" />
    </svg>
  );
}
