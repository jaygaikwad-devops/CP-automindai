"use client";

import { useCallback, useRef, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export function useVoiceNarration() {
  const [isSpeaking, setIsSpeaking] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const speak = useCallback(async (text: string) => {
    if (!text) return;

    // Stop any current playback
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }

    setIsSpeaking(true);

    try {
      // Fetch audio from Polly endpoint
      const url = `${API_BASE}/api/v1/tours/narrate?text=${encodeURIComponent(text)}`;
      const audio = new Audio(url);
      audioRef.current = audio;

      audio.onended = () => setIsSpeaking(false);
      audio.onerror = () => {
        setIsSpeaking(false);
        // Fallback to browser TTS with female voice
        if (window.speechSynthesis) {
          const utterance = new SpeechSynthesisUtterance(text);
          utterance.rate = 0.92;
          utterance.pitch = 1.2; // Higher pitch = more female
          // Try to find a female voice
          const voices = window.speechSynthesis.getVoices();
          const femaleVoice = voices.find(v => v.name.includes("Female") || v.name.includes("Zira") || v.name.includes("Samantha") || v.name.includes("Google UK English Female") || v.name.includes("Karen")) 
            || voices.find(v => v.lang.startsWith("en") && v.name.toLowerCase().includes("female"))
            || voices.find(v => v.lang === "en-IN");
          if (femaleVoice) utterance.voice = femaleVoice;
          utterance.onstart = () => setIsSpeaking(true);
          utterance.onend = () => setIsSpeaking(false);
          window.speechSynthesis.speak(utterance);
        }
      };

      await audio.play();
    } catch {
      setIsSpeaking(false);
      // Fallback to browser TTS with female voice
      if (typeof window !== "undefined" && window.speechSynthesis) {
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.rate = 0.92;
        utterance.pitch = 1.2;
        const voices = window.speechSynthesis.getVoices();
        const femaleVoice = voices.find(v => v.name.includes("Female") || v.name.includes("Zira") || v.name.includes("Samantha") || v.name.includes("Google UK English Female") || v.name.includes("Karen"))
          || voices.find(v => v.lang.startsWith("en") && v.name.toLowerCase().includes("female"))
          || voices.find(v => v.lang === "en-IN");
        if (femaleVoice) utterance.voice = femaleVoice;
        utterance.onstart = () => setIsSpeaking(true);
        utterance.onend = () => setIsSpeaking(false);
        window.speechSynthesis.speak(utterance);
      }
    }
  }, []);

  const stop = useCallback(() => {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    if (typeof window !== "undefined" && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
    setIsSpeaking(false);
  }, []);

  return { speak, stop, isSpeaking };
}
