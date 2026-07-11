"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState, useRef, useCallback } from "react";
import PriyaAvatar from "@/components/PriyaAvatar";
import ChatInterface from "@/components/ChatInterface";
import ContactForm from "@/components/ContactForm";

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
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center bg-gray-900"><div className="text-center"><PriyaAvatar size="cta" isSpeaking /><p className="text-white mt-4">Loading your tour...</p></div></div>}>
      <TourPage />
    </Suspense>
  );
}

function TourPage() {
  const searchParams = useSearchParams();
  const linkId = searchParams.get("id") || "";

  const [tourScript, setTourScript] = useState<TourScript | null>(null);
  const [currentRoomIndex, setCurrentRoomIndex] = useState(0);
  const [sessionId, setSessionId] = useState("");
  const [sessionToken, setSessionToken] = useState("");
  const [projectName, setProjectName] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [ws, setWs] = useState<WebSocket | null>(null);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [showChat, setShowChat] = useState(false);
  const [showContact, setShowContact] = useState(false);
  const [transitioning, setTransitioning] = useState(false);
  const [showNarration, setShowNarration] = useState(true);

  const viewedRooms = useRef<Set<number>>(new Set());
  const roomEnteredAt = useRef<number>(Date.now());
  const totalViewTime = useRef<number>(0);
  const timeThresholdFired = useRef(false);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  // Load tour from API
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

  // WebSocket connection for Priya chat
  useEffect(() => {
    if (!sessionId || !sessionToken) return;
    const wsUrl = `${API_BASE.replace("https://", "wss://").replace("http://", "ws://")}/ws/tour/${sessionId}?session_token=${sessionToken}`;
    const socket = new WebSocket(wsUrl);
    socket.onopen = () => setWs(socket);
    socket.onmessage = (event) => {
      try {
        const d = JSON.parse(event.data);
        if (d.type === "talking_start") setIsSpeaking(true);
        if (d.type === "talking_end") setIsSpeaking(false);
      } catch { /* ignore */ }
    };
    socket.onclose = () => { setWs(null); setIsSpeaking(false); };
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

  const navigateRoom = (dir: "next" | "prev") => {
    if (!tourScript || transitioning) return;
    const n = dir === "next" ? currentRoomIndex + 1 : currentRoomIndex - 1;
    if (n < 0 || n >= tourScript.rooms.length) return;

    // Track current room view time
    const timeSpent = Math.floor((Date.now() - roomEnteredAt.current) / 1000);
    postEvent("room_viewed", { room_id: tourScript.rooms[currentRoomIndex].id, duration_seconds: timeSpent });

    // Check revisit
    if (viewedRooms.current.has(n)) {
      postEvent("room_revisited", { room_id: tourScript.rooms[n].id });
    }
    viewedRooms.current.add(n);

    setTransitioning(true);
    setShowNarration(false);
    setTimeout(() => {
      setCurrentRoomIndex(n);
      roomEnteredAt.current = Date.now();
      setTransitioning(false);
      setTimeout(() => setShowNarration(true), 500);
    }, 300);
  };

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-900">
        <div className="text-center">
          <PriyaAvatar size="cta" isSpeaking />
          <p className="text-white mt-4 text-sm animate-pulse">Preparing your virtual tour...</p>
        </div>
      </div>
    );
  }

  // Error state
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
      <header className="absolute top-0 left-0 right-0 bg-gradient-to-b from-black/70 to-transparent px-4 py-3 flex items-center justify-between z-20">
        <div className="flex items-center gap-3">
          <PriyaAvatar size="header" isSpeaking={isSpeaking} />
          <div>
            <p className="text-sm font-medium text-white">{projectName || tourScript.project_name}</p>
            <p className="text-xs text-gray-300">
              Room {currentRoomIndex + 1} of {tourScript.total_rooms} • {room.name}
            </p>
          </div>
        </div>
        <button
          onClick={() => setShowContact(true)}
          className="px-4 py-2 bg-green-500 text-white text-xs font-bold rounded-full hover:bg-green-600 shadow-lg transition-all"
        >
          📞 Book Visit
        </button>
      </header>

      {/* Room Display - Full screen background */}
      <div className="flex-1 relative overflow-hidden">
        <div
          className={`absolute inset-0 transition-opacity duration-300 ${transitioning ? "opacity-0" : "opacity-100"}`}
          style={{
            backgroundImage: `url(${room.visuals.primary_image_url})`,
            backgroundSize: "cover",
            backgroundPosition: "center",
          }}
        >
          {/* Gradient overlay for text readability */}
          <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/20 to-black/40" />
        </div>

        {/* Room content overlay */}
        <div className="absolute bottom-0 left-0 right-0 p-6 pb-20 z-10">
          {/* Priya narration bubble */}
          {showNarration && (
            <div className="max-w-lg mx-auto mb-4 animate-in fade-in slide-in-from-bottom-2 duration-500">
              <div className="bg-white/95 backdrop-blur-sm rounded-2xl p-4 shadow-xl">
                <div className="flex items-start gap-3">
                  <PriyaAvatar size="badge" isSpeaking={isSpeaking} />
                  <div>
                    <p className="text-xs font-semibold text-primary-700 mb-1">Priya</p>
                    <p className="text-sm text-gray-800 leading-relaxed">{room.narration.text}</p>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Features pills */}
          <div className="flex flex-wrap gap-2 justify-center max-w-lg mx-auto">
            {room.features.map((f, i) => (
              <span key={i} className="px-3 py-1.5 bg-white/20 backdrop-blur-sm text-white rounded-full text-xs font-medium border border-white/30">
                {f.name}
              </span>
            ))}
          </div>
        </div>

        {/* Navigation arrows */}
        <button
          onClick={() => navigateRoom("prev")}
          disabled={isFirst}
          className="absolute left-4 top-1/2 -translate-y-1/2 w-12 h-12 rounded-full bg-black/40 backdrop-blur-sm text-white flex items-center justify-center hover:bg-black/60 disabled:opacity-20 disabled:cursor-not-allowed transition-all z-10 border border-white/20"
          aria-label="Previous room"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" /></svg>
        </button>
        <button
          onClick={() => navigateRoom("next")}
          disabled={isLast}
          className="absolute right-4 top-1/2 -translate-y-1/2 w-12 h-12 rounded-full bg-black/40 backdrop-blur-sm text-white flex items-center justify-center hover:bg-black/60 disabled:opacity-20 disabled:cursor-not-allowed transition-all z-10 border border-white/20"
          aria-label="Next room"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" /></svg>
        </button>

        {/* Room dots indicator */}
        <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex gap-2 z-10">
          {tourScript.rooms.map((r, i) => (
            <button
              key={r.id}
              onClick={() => {
                if (i !== currentRoomIndex) {
                  if (viewedRooms.current.has(i)) postEvent("room_revisited", { room_id: r.id });
                  viewedRooms.current.add(i);
                  setTransitioning(true);
                  setShowNarration(false);
                  setTimeout(() => { setCurrentRoomIndex(i); roomEnteredAt.current = Date.now(); setTransitioning(false); setTimeout(() => setShowNarration(true), 500); }, 300);
                }
              }}
              className={`w-2.5 h-2.5 rounded-full transition-all ${i === currentRoomIndex ? "bg-white scale-150 shadow-lg" : "bg-white/40 hover:bg-white/70"}`}
              aria-label={`Go to ${r.name}`}
            />
          ))}
        </div>
      </div>

      {/* Bottom bar */}
      <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/90 to-transparent px-4 py-4 flex items-center justify-between z-20">
        <button
          onClick={() => setShowChat(!showChat)}
          className="flex items-center gap-2 px-4 py-2.5 bg-white/15 backdrop-blur-sm text-white rounded-full text-sm border border-white/25 hover:bg-white/25 transition-all"
        >
          <PriyaAvatar size="badge" isSpeaking={isSpeaking} />
          <span className="font-medium">{showChat ? "Close Chat" : "Ask Priya"}</span>
        </button>

        <button
          onClick={() => setShowContact(true)}
          className="px-5 py-2.5 bg-primary-500 text-white rounded-full text-sm font-bold shadow-lg hover:bg-primary-600 transition-all"
        >
          📞 Contact Agent
        </button>
      </div>

      {/* Chat panel */}
      {showChat && (
        <div className="fixed bottom-0 left-0 right-0 h-[65vh] z-50 bg-white rounded-t-2xl shadow-2xl">
          <div className="h-full flex flex-col">
            <div className="flex items-center justify-between p-3 border-b bg-gray-50 rounded-t-2xl">
              <div className="flex items-center gap-2">
                <PriyaAvatar size="header" isSpeaking={isSpeaking} />
                <span className="text-sm font-semibold text-gray-800">Chat with Priya</span>
              </div>
              <button onClick={() => setShowChat(false)} className="w-8 h-8 flex items-center justify-center rounded-full hover:bg-gray-200 text-gray-500">✕</button>
            </div>
            <div className="flex-1 overflow-hidden">
              <ChatInterface ws={ws} isSpeaking={isSpeaking} />
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
            // Show success message
            alert(`Thank you ${name}! Our agent will contact you at +91 ${phone} shortly.`);
          }}
          onClose={() => setShowContact(false)}
        />
      )}
    </div>
  );
}
