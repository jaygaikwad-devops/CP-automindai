"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState, useRef, useCallback } from "react";
import AriaAvatar from "@/components/AriaAvatar";
import ChatInterface from "@/components/ChatInterface";
import ContactForm from "@/components/ContactForm";
import { useVoiceNarration } from "@/hooks/useVoiceNarration";

interface Room {
  index: number;
  id: string;
  name: string;
  room_type: string;
  narration: { text: string; duration_seconds: number; language: string };
  visuals: { primary_image_url: string; labels: string[] };
  features: Array<{ name: string; category: string }>;
  transition: { type: string; duration_ms: number };
}

interface TourScript {
  schema_version: string;
  project_name: string;
  total_rooms: number;
  estimated_duration_seconds: number;
  rooms: Room[];
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export default function TourPageWrapper() {
  return (
    <Suspense fallback={
      <div className="min-h-screen flex items-center justify-center bg-gray-900">
        <div className="text-center">
          <AriaAvatar size="lg" isSpeaking />
          <p className="text-white mt-4 text-sm animate-pulse">Aria is preparing your tour...</p>
        </div>
      </div>
    }>
      <TourPage />
    </Suspense>
  );
}

function TourPage() {
  const searchParams = useSearchParams();
  const linkId = searchParams.get("id") || "";
  const { speak, stop, isSpeaking: voiceSpeaking } = useVoiceNarration();

  const [tourScript, setTourScript] = useState<TourScript | null>(null);
  const [currentRoomIndex, setCurrentRoomIndex] = useState(0);
  const [sessionId, setSessionId] = useState("");
  const [sessionToken, setSessionToken] = useState("");
  const [projectName, setProjectName] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [ws, setWs] = useState<WebSocket | null>(null);
  const [wsSpeaking, setWsSpeaking] = useState(false);
  const [showChat, setShowChat] = useState(false);
  const [showContact, setShowContact] = useState(false);
  const [transitioning, setTransitioning] = useState(false);
  const [showNarration, setShowNarration] = useState(true);
  const [narrationPlayed, setNarrationPlayed] = useState<Set<number>>(new Set());

  const isSpeaking = voiceSpeaking || wsSpeaking;

  const viewedRooms = useRef<Set<number>>(new Set());
  const roomEnteredAt = useRef<number>(Date.now());
  const totalViewTime = useRef<number>(0);
  const timeThresholdFired = useRef(false);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  // Load tour
  useEffect(() => {
    if (!linkId) { setError("No tour link provided."); setLoading(false); return; }
    async function loadTour() {
      try {
        const res = await fetch(`${API_BASE}/api/v1/tours/link/${linkId}`);
        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          setError(data.detail || "This tour is no longer available.");
          setLoading(false);
          return;
        }
        const data = await res.json();
        setTourScript(data.tour_script);
        setSessionId(data.session_id);
        setSessionToken(data.session_token);
        setProjectName(data.project_name);
        viewedRooms.current.add(0);
        setLoading(false);
      } catch {
        setError("Failed to load tour. Please check your connection.");
        setLoading(false);
      }
    }
    loadTour();
  }, [linkId]);

  // Don't auto-narrate — browsers block audio without user gesture
  // User must tap "Listen" or navigate to trigger voice

  // WebSocket
  useEffect(() => {
    if (!sessionId || !sessionToken) return;
    const wsUrl = `${API_BASE.replace("https://", "wss://").replace("http://", "ws://")}/ws/tour/${sessionId}?session_token=${sessionToken}`;
    const socket = new WebSocket(wsUrl);
    socket.onopen = () => setWs(socket);
    socket.onmessage = (event) => {
      try {
        const d = JSON.parse(event.data);
        if (d.type === "talking_start") setWsSpeaking(true);
        if (d.type === "talking_end") setWsSpeaking(false);
      } catch { /* ignore */ }
    };
    socket.onclose = () => { setWs(null); setWsSpeaking(false); };
    return () => { socket.close(); };
  }, [sessionId, sessionToken]);

  // Time tracking
  useEffect(() => {
    if (!sessionId) return;
    timerRef.current = setInterval(() => {
      totalViewTime.current += 1;
      if (totalViewTime.current >= 180 && !timeThresholdFired.current) {
        timeThresholdFired.current = true;
        postEvent("time_on_tour_3min_plus", { duration_seconds: totalViewTime.current });
      }
    }, 1000);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [sessionId]);

  const postEvent = useCallback(async (type: string, data: Record<string, unknown> = {}) => {
    if (!sessionId) return;
    try {
      await fetch(`${API_BASE}/api/v1/tours/${sessionId}/events`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ type, data }),
      });
    } catch { /* non-critical */ }
  }, [sessionId]);

  const navigateRoom = (newIndex: number) => {
    if (!tourScript || transitioning || newIndex < 0 || newIndex >= tourScript.rooms.length || newIndex === currentRoomIndex) return;

    // Stop current narration
    stop();

    // Track time on current room
    const timeSpent = Math.floor((Date.now() - roomEnteredAt.current) / 1000);
    postEvent("room_viewed", { room_id: tourScript.rooms[currentRoomIndex].id, duration_seconds: timeSpent });

    // Check revisit
    if (viewedRooms.current.has(newIndex)) {
      postEvent("room_revisited", { room_id: tourScript.rooms[newIndex].id });
    }
    viewedRooms.current.add(newIndex);

    // Transition
    setTransitioning(true);
    setShowNarration(false);
    setTimeout(() => {
      setCurrentRoomIndex(newIndex);
      roomEnteredAt.current = Date.now();
      setTransitioning(false);
      setTimeout(() => {
        setShowNarration(true);
        // Auto-narrate new room
        if (!narrationPlayed.has(newIndex)) {
          speak(tourScript.rooms[newIndex].narration.text);
          setNarrationPlayed((prev) => new Set([...prev, newIndex]));
        }
      }, 400);
    }, 300);
  };

  // Loading
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-900">
        <div className="text-center">
          <AriaAvatar size="lg" isSpeaking />
          <p className="text-white mt-4 text-sm animate-pulse">Aria is preparing your tour...</p>
        </div>
      </div>
    );
  }

  // Error
  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-900 p-4">
        <div className="text-center max-w-sm">
          <div className="text-5xl mb-4">🏠</div>
          <p className="text-white text-lg font-medium mb-2">Tour Unavailable</p>
          <p className="text-gray-400 text-sm">{error}</p>
        </div>
      </div>
    );
  }

  if (!tourScript) return null;

  const room = tourScript.rooms[currentRoomIndex];
  const isFirst = currentRoomIndex === 0;
  const isLast = currentRoomIndex === tourScript.rooms.length - 1;

  return (
    <div className="min-h-screen bg-gray-900 flex flex-col">
      {/* Header */}
      <header className="absolute top-0 left-0 right-0 bg-gradient-to-b from-black/80 to-transparent px-4 py-4 flex items-center justify-between z-20">
        <div className="flex items-center gap-3">
          <AriaAvatar size="sm" isSpeaking={isSpeaking} />
          <div>
            <p className="text-sm font-semibold text-white">{projectName}</p>
            <p className="text-xs text-gray-300">{room.name} • {currentRoomIndex + 1}/{tourScript.total_rooms}</p>
          </div>
        </div>
        <button
          onClick={() => setShowContact(true)}
          className="px-4 py-2 bg-green-500 text-white text-xs font-bold rounded-full hover:bg-green-600 shadow-lg transition-all"
        >
          📞 Book Visit
        </button>
      </header>

      {/* Room Display */}
      <div className="flex-1 relative overflow-hidden">
        <div
          className={`absolute inset-0 transition-all duration-500 ${transitioning ? "opacity-0 scale-105" : "opacity-100 scale-100"}`}
          style={{ backgroundImage: `url(${room.visuals.primary_image_url})`, backgroundSize: "cover", backgroundPosition: "center" }}
        >
          <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/20 to-black/50" />
        </div>

        {/* Bottom content */}
        <div className="absolute bottom-0 left-0 right-0 p-5 pb-24 z-10">
          {/* Aria narration card */}
          {showNarration && (
            <div className="max-w-md mx-auto mb-5 animate-in fade-in slide-in-from-bottom-3 duration-600">
              <div className="bg-white/95 backdrop-blur-md rounded-2xl p-4 shadow-2xl border border-white/50">
                <div className="flex items-start gap-3">
                  <AriaAvatar size="sm" isSpeaking={isSpeaking} />
                  <div className="flex-1">
                    <div className="flex items-center justify-between mb-1">
                      <p className="text-xs font-bold text-blue-700">Aria</p>
                      {isSpeaking && (
                        <div className="flex items-center gap-0.5">
                          <span className="w-1 h-2 bg-blue-500 rounded-full animate-pulse" />
                          <span className="w-1 h-3 bg-blue-500 rounded-full animate-pulse [animation-delay:100ms]" />
                          <span className="w-1 h-2 bg-blue-500 rounded-full animate-pulse [animation-delay:200ms]" />
                          <span className="w-1 h-3 bg-blue-500 rounded-full animate-pulse [animation-delay:300ms]" />
                        </div>
                      )}
                    </div>
                    <p className="text-sm text-gray-800 leading-relaxed">{room.narration.text}</p>
                  </div>
                </div>
                {/* Voice narration button */}
                <button
                  onClick={() => {
                    speak(room.narration.text);
                    setNarrationPlayed((prev) => new Set([...prev, currentRoomIndex]));
                  }}
                  className="mt-3 ml-12 flex items-center gap-2 px-3 py-1.5 bg-blue-50 hover:bg-blue-100 text-blue-700 rounded-full text-xs font-semibold transition-colors"
                >
                  {isSpeaking ? (
                    <>
                      <span className="flex items-center gap-0.5">
                        <span className="w-1 h-2 bg-blue-500 rounded-full animate-pulse" />
                        <span className="w-1 h-3 bg-blue-500 rounded-full animate-pulse [animation-delay:100ms]" />
                        <span className="w-1 h-2 bg-blue-500 rounded-full animate-pulse [animation-delay:200ms]" />
                      </span>
                      Speaking...
                    </>
                  ) : (
                    <>🔊 {narrationPlayed.has(currentRoomIndex) ? "Listen again" : "Listen to Aria"}</>
                  )}
                </button>
              </div>
            </div>
          )}

          {/* Features */}
          <div className="flex flex-wrap gap-2 justify-center max-w-md mx-auto">
            {room.features.map((f, i) => (
              <span key={i} className="px-3 py-1.5 bg-white/15 backdrop-blur-sm text-white rounded-full text-xs font-medium border border-white/25">
                {f.name}
              </span>
            ))}
          </div>
        </div>

        {/* Navigation arrows */}
        <button
          onClick={() => navigateRoom(currentRoomIndex - 1)}
          disabled={isFirst}
          className="absolute left-3 top-1/2 -translate-y-1/2 w-11 h-11 rounded-full bg-white/20 backdrop-blur-md text-white flex items-center justify-center hover:bg-white/30 disabled:opacity-20 disabled:cursor-not-allowed transition-all z-10 border border-white/30"
          aria-label="Previous room"
        >
          ‹
        </button>
        <button
          onClick={() => navigateRoom(currentRoomIndex + 1)}
          disabled={isLast}
          className="absolute right-3 top-1/2 -translate-y-1/2 w-11 h-11 rounded-full bg-white/20 backdrop-blur-md text-white flex items-center justify-center hover:bg-white/30 disabled:opacity-20 disabled:cursor-not-allowed transition-all z-10 border border-white/30"
          aria-label="Next room"
        >
          ›
        </button>

        {/* Room dots */}
        <div className="absolute bottom-16 left-1/2 -translate-x-1/2 flex gap-2 z-10">
          {tourScript.rooms.map((r, i) => (
            <button
              key={r.id}
              onClick={() => navigateRoom(i)}
              className={`h-1.5 rounded-full transition-all ${i === currentRoomIndex ? "w-6 bg-white" : "w-1.5 bg-white/40 hover:bg-white/70"}`}
              aria-label={r.name}
            />
          ))}
        </div>
      </div>

      {/* Bottom bar */}
      <div className="absolute bottom-0 left-0 right-0 bg-black/80 backdrop-blur-md px-4 py-3 flex items-center justify-between z-20 border-t border-white/10">
        <button
          onClick={() => { setShowChat(!showChat); if (showChat) stop(); }}
          className="flex items-center gap-2 px-4 py-2.5 bg-white/10 text-white rounded-full text-sm border border-white/20 hover:bg-white/20 transition-all"
        >
          <AriaAvatar size="sm" isSpeaking={isSpeaking && showChat} />
          <span className="font-medium">{showChat ? "Close" : "Ask Aria"}</span>
        </button>

        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              // Show contact form — brochure is sent after contact info collected
              setShowContact(true);
            }}
            className="px-4 py-2.5 bg-white/10 text-white rounded-full text-xs font-medium border border-white/20 hover:bg-white/20 transition-all"
          >
            📄 Brochure
          </button>
          <button
            onClick={() => setShowContact(true)}
            className="px-5 py-2.5 bg-blue-500 text-white rounded-full text-sm font-bold shadow-lg hover:bg-blue-600 transition-all"
          >
            📞 Contact
          </button>
        </div>
      </div>

      {/* Chat panel */}
      {showChat && (
        <div className="fixed bottom-0 left-0 right-0 h-[65vh] z-50 bg-white rounded-t-3xl shadow-2xl border-t border-gray-200">
          <div className="h-full flex flex-col">
            <div className="flex items-center justify-center pt-2 pb-1">
              <div className="w-10 h-1 bg-gray-300 rounded-full" />
            </div>
            <div className="flex-1 overflow-hidden">
              <ChatInterface ws={ws} isSpeaking={wsSpeaking} />
            </div>
          </div>
        </div>
      )}

      {/* Contact form */}
      {showContact && (
        <ContactForm
          onSubmit={(name, phone) => {
            postEvent("visit_booking_clicked", { buyer_name: name, buyer_phone: phone });
            setShowContact(false);
            alert(`Thank you ${name}! Our agent will call you at +91 ${phone} shortly. You can also download the project brochure.`);
          }}
          onClose={() => setShowContact(false)}
        />
      )}
    </div>
  );
}
