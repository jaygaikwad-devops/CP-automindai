"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export function useVoiceNarration() {
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [voicesReady, setVoicesReady] = useState(false);
  const selectedVoice = useRef<SpeechSynthesisVoice | null>(null);

  // Load voices — they load asynchronously in most browsers
  useEffect(() => {
    if (typeof window === "undefined" || !window.speechSynthesis) return;

    const loadVoices = () => {
      const voices = window.speechSynthesis.getVoices();
      if (voices.length === 0) return;

      // Priority: Indian English female > any English female > any English
      const voice =
        voices.find((v) => v.lang === "en-IN" && v.name.toLowerCase().includes("female")) ||
        voices.find((v) => v.lang === "en-IN") ||
        voices.find((v) => v.lang.startsWith("en") && v.name.toLowerCase().includes("female")) ||
        voices.find((v) => v.lang.startsWith("en-") && v.name.includes("Google")) ||
        voices.find((v) => v.lang.startsWith("en")) ||
        voices[0];

      selectedVoice.current = voice;
      setVoicesReady(true);
    };

    // Chrome fires this event when voices are ready
    window.speechSynthesis.onvoiceschanged = loadVoices;
    // Try immediately (works in Firefox/Safari)
    loadVoices();

    return () => {
      window.speechSynthesis.onvoiceschanged = null;
    };
  }, []);

  const speak = useCallback((text: string) => {
    if (typeof window === "undefined" || !window.speechSynthesis) return;

    // Cancel any ongoing speech
    window.speechSynthesis.cancel();

    // Chrome bug: after cancel, need a small delay
    setTimeout(() => {
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 0.92;
      utterance.pitch = 1.05;
      utterance.volume = 1;

      if (selectedVoice.current) {
        utterance.voice = selectedVoice.current;
      }

      utterance.onstart = () => setIsSpeaking(true);
      utterance.onend = () => setIsSpeaking(false);
      utterance.onerror = (e) => {
        console.warn("Speech error:", e.error);
        setIsSpeaking(false);
      };

      window.speechSynthesis.speak(utterance);
    }, 100);
  }, []);

  const stop = useCallback(() => {
    if (typeof window === "undefined") return;
    window.speechSynthesis.cancel();
    setIsSpeaking(false);
  }, []);

  return { speak, stop, isSpeaking, voicesReady };
}
