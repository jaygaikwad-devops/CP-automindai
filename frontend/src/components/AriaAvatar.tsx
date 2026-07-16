"use client";

import { useEffect, useRef } from "react";

type AvatarSize = "sm" | "md" | "lg";

const SIZE_MAP: Record<AvatarSize, number> = {
  sm: 36,
  md: 48,
  lg: 64,
};

interface AriaAvatarProps {
  size?: AvatarSize;
  isSpeaking?: boolean;
}

// Professional Indian woman headshot (free stock photo)
const AVATAR_URL = "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=200&h=200&fit=crop&crop=face";

export default function AriaAvatar({ size = "md", isSpeaking = false }: AriaAvatarProps) {
  const px = SIZE_MAP[size];

  return (
    <div
      className={`relative flex-shrink-0 rounded-full ${isSpeaking ? "aria-speaking" : ""}`}
      style={{ width: px, height: px }}
    >
      {/* Glow ring when speaking */}
      {isSpeaking && (
        <>
          <div className="absolute inset-[-3px] rounded-full bg-gradient-to-r from-blue-500 via-purple-500 to-pink-500 animate-spin-slow opacity-80" />
          <div className="absolute inset-[-2px] rounded-full bg-gradient-to-r from-blue-400 to-indigo-400 animate-pulse opacity-60" />
        </>
      )}

      {/* Avatar image */}
      <img
        src={AVATAR_URL}
        alt="Aria - AI Sales Guide"
        className="relative w-full h-full rounded-full object-cover border-2 border-white shadow-lg z-10"
        style={{ width: px, height: px }}
      />

      {/* Online indicator */}
      <div className={`absolute bottom-0 right-0 w-3 h-3 rounded-full border-2 border-white z-20 ${isSpeaking ? "bg-green-400 animate-pulse" : "bg-green-500"}`} />
    </div>
  );
}
