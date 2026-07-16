"use client";

import { useCallback, useRef, useState } from "react";

export function useVoiceNarration() {
  const [isSpeaking, setIsSpeaking] = useState(false);
  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null);

  const speak = useCallback((text: string) => {
    if (typeof window === "undefined" || !window.speechSynthesis) return;

    // Cancel any ongoing speech
    window.speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 0.95; // Slightly slower for clarity
    utterance.pitch = 1.1; // Slightly higher for female voice
    utterance.volume = 1;

    // Try to find an Indian English female voice
    const voices = window.speechSynthesis.getVoices();
    const preferredVoice = voices.find(
      (v) =>
        (v.lang.includes("en-IN") || v.lang.includes("en-GB")) &&
        v.name.toLowerCase().includes("female")
    ) || voices.find(
      (v) => v.lang.includes("en") && v.name.toLowerCase().includes("female")
    ) || voices.find(
      (v) => v.lang.includes("en-IN")
    ) || voices.find(
      (v) => v.lang.includes("en")
    );

    if (preferredVoice) {
      utterance.voice = preferredVoice;
    }

    utterance.onstart = () => setIsSpeaking(true);
    utterance.onend = () => setIsSpeaking(false);
    utterance.onerror = () => setIsSpeaking(false);

    utteranceRef.current = utterance;
    window.speechSynthesis.speak(utterance);
  }, []);

  const stop = useCallback(() => {
    if (typeof window === "undefined") return;
    window.speechSynthesis.cancel();
    setIsSpeaking(false);
  }, []);

  return { speak, stop, isSpeaking };
}
