"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState, useRef, useCallback } from "react";
import PriyaAvatar from "@/components/PriyaAvatar";
import ChatInterface from "@/components/ChatInterface";
import ContactForm from "@/components/ContactForm";

interface Room { index: number; id: string; name: string; room_type: string; narration: { text: string; duration_seconds: number; language: string }; visuals: { primary_image_url: string; labels: string[] }; features: Array<{ name: string; category: string }>; transition: { type: string; duration_ms: number }; }
interface TourScript { schema_version: string; project_id: string; project_name: string; total_rooms: number; estimated_duration_seconds: number; rooms: Room[]; }

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export default function TourPageWrapper() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center bg-gray-900"><p className="text-white">Loading...</p></div>}>
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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [ws, setWs] = useState<WebSocket | null>(null);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [showChat, setShowChat] = useState(false);
  const [showContact, setShowContact] = useState(false);
  const [transitioning, setTransitioning] = useState(false);
  const viewedRooms = useRef<Set<number>>(new Set());
  const roomEnteredAt = useRef<number>(Date.now());
  const totalViewTime = useRef<number>(0);
  const timeThresholdFired = useRef(false);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    if (!linkId) { setError("No tour link provided."); setLoading(false); return; }
    async function initTour() {
      try {
        const res = await fetch(`${API_BASE}/api/v1/auth/session/anonymous`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ link_id: linkId }) });
        if (!res.ok) { setError("This tour link is no longer valid."); setLoading(false); return; }
        const d = await res.json();
        setSessionId(d.session_id); setSessionToken(d.session_token);
        const mockTour: TourScript = { schema_version: "1.0.0", project_id: "demo", project_name: "Sunshine Heights", total_rooms: 5, estimated_duration_seconds: 180, rooms: [
          { index: 0, id: "living_room", name: "Living Room", room_type: "living_room", narration: { text: "Welcome to the spacious living room.", duration_seconds: 20, language: "en" }, visuals: { primary_image_url: "", labels: [] }, features: [{ name: "Italian Marble", category: "flooring" }], transition: { type: "slide_left", duration_ms: 300 } },
          { index: 1, id: "bedroom", name: "Master Bedroom", room_type: "bedroom", narration: { text: "Spacious master bedroom with en-suite.", duration_seconds: 20, language: "en" }, visuals: { primary_image_url: "", labels: [] }, features: [{ name: "Walk-in Closet", category: "storage" }], transition: { type: "slide_left", duration_ms: 300 } },
          { index: 2, id: "kitchen", name: "Kitchen", room_type: "kitchen", narration: { text: "Modular kitchen with premium fittings.", duration_seconds: 20, language: "en" }, visuals: { primary_image_url: "", labels: [] }, features: [{ name: "Granite Counter", category: "countertop" }], transition: { type: "slide_left", duration_ms: 300 } },
          { index: 3, id: "balcony", name: "Balcony", room_type: "balcony", narration: { text: "City skyline views from your balcony.", duration_seconds: 20, language: "en" }, visuals: { primary_image_url: "", labels: [] }, features: [{ name: "City View", category: "view" }], transition: { type: "slide_left", duration_ms: 300 } },
          { index: 4, id: "amenities", name: "Amenities", room_type: "amenities", narration: { text: "Pool, gym, and children's play area.", duration_seconds: 20, language: "en" }, visuals: { primary_image_url: "", labels: [] }, features: [{ name: "Pool", category: "fitness" }, { name: "Gym", category: "fitness" }], transition: { type: "slide_left", duration_ms: 300 } },
        ] };
        setTourScript(mockTour); viewedRooms.current.add(0); setLoading(false);
      } catch { setError("Failed to load tour."); setLoading(false); }
    }
    initTour();
  }, [linkId]);

  useEffect(() => { if (!sessionId || !sessionToken) return; const wsUrl = `${API_BASE.replace("https://","wss://").replace("http://","ws://")}/ws/tour/${sessionId}?session_token=${sessionToken}`; const s = new WebSocket(wsUrl); s.onopen = () => setWs(s); s.onmessage = (e) => { try { const d = JSON.parse(e.data); if (d.type==="talking_start") setIsSpeaking(true); if (d.type==="talking_end") setIsSpeaking(false); } catch {} }; s.onclose = () => { setWs(null); setIsSpeaking(false); }; return () => { s.close(); }; }, [sessionId, sessionToken]);
  useEffect(() => { timerRef.current = setInterval(() => { totalViewTime.current += 1; if (totalViewTime.current >= 180 && !timeThresholdFired.current) { timeThresholdFired.current = true; postEvent("time_on_tour_3min_plus", {}); } }, 1000); return () => { if (timerRef.current) clearInterval(timerRef.current); }; }, [sessionId]);

  const postEvent = useCallback(async (type: string, data: Record<string, unknown> = {}) => { if (!sessionId) return; try { await fetch(`${API_BASE}/api/v1/tours/${sessionId}/events`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ type, data }) }); } catch {} }, [sessionId]);

  const navigateRoom = (dir: "next" | "prev") => { if (!tourScript || transitioning) return; const n = dir === "next" ? currentRoomIndex + 1 : currentRoomIndex - 1; if (n < 0 || n >= tourScript.rooms.length) return; if (viewedRooms.current.has(n)) postEvent("room_revisited", { room_id: tourScript.rooms[n].id }); viewedRooms.current.add(n); setTransitioning(true); setTimeout(() => { setCurrentRoomIndex(n); roomEnteredAt.current = Date.now(); setTransitioning(false); }, 300); };

  if (loading) return <div className="min-h-screen flex items-center justify-center bg-gray-900"><div className="text-center"><PriyaAvatar size="cta" isSpeaking /><p className="text-white mt-4 text-sm">Loading tour...</p></div></div>;
  if (error) return <div className="min-h-screen flex items-center justify-center bg-gray-900"><p className="text-red-400">{error}</p></div>;
  if (!tourScript) return null;
  const room = tourScript.rooms[currentRoomIndex];

  return (
    <div className="min-h-screen bg-gray-900 flex flex-col">
      <header className="bg-gray-900/90 border-b border-gray-800 px-4 py-3 flex items-center justify-between"><div className="flex items-center gap-3"><PriyaAvatar size="header" isSpeaking={isSpeaking} /><div><p className="text-sm font-medium text-white">{tourScript.project_name}</p><p className="text-xs text-gray-400">Room {currentRoomIndex+1}/{tourScript.total_rooms}</p></div></div><button onClick={() => setShowContact(true)} className="px-4 py-2 bg-green-600 text-white text-sm rounded-full">Book Visit</button></header>
      <div className="flex-1 relative overflow-hidden">
        <div className={`w-full h-full flex items-center justify-center transition-opacity duration-300 ${transitioning?"opacity-0":"opacity-100"}`}><div className="w-full h-full bg-gradient-to-br from-gray-700 to-gray-900 flex items-center justify-center"><div className="text-center p-8 max-w-lg"><h2 className="text-3xl font-bold text-white mb-3">{room.name}</h2><p className="text-gray-300 text-sm mb-6">{room.narration.text}</p><div className="flex flex-wrap gap-2 justify-center">{room.features.map((f,i) => <span key={i} className="px-3 py-1 bg-white/10 text-white/80 rounded-full text-xs">{f.name}</span>)}</div></div></div></div>
        <div className="absolute inset-y-0 left-0 flex items-center pl-4"><button onClick={() => navigateRoom("prev")} disabled={currentRoomIndex===0} className="w-10 h-10 rounded-full bg-black/50 text-white flex items-center justify-center disabled:opacity-30">←</button></div>
        <div className="absolute inset-y-0 right-0 flex items-center pr-4"><button onClick={() => navigateRoom("next")} disabled={currentRoomIndex===tourScript.rooms.length-1} className="w-10 h-10 rounded-full bg-black/50 text-white flex items-center justify-center disabled:opacity-30">→</button></div>
        <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex gap-2">{tourScript.rooms.map((_,i) => <button key={i} onClick={() => { viewedRooms.current.add(i); setCurrentRoomIndex(i); }} className={`w-2.5 h-2.5 rounded-full ${i===currentRoomIndex?"bg-white scale-125":"bg-white/40"}`} />)}</div>
      </div>
      <div className="bg-gray-900/90 border-t border-gray-800 px-4 py-3 flex items-center justify-between"><button onClick={() => setShowChat(!showChat)} className="flex items-center gap-2 px-4 py-2 bg-white/10 text-white rounded-full text-sm"><PriyaAvatar size="badge" isSpeaking={isSpeaking} /><span>{showChat?"Close":"Ask Priya"}</span></button><button onClick={() => setShowContact(true)} className="px-5 py-2.5 bg-primary-600 text-white rounded-full text-sm font-medium">📞 Contact</button></div>
      {showChat && <div className="fixed bottom-0 left-0 right-0 h-[60vh] z-40 bg-white rounded-t-2xl shadow-2xl"><div className="h-full flex flex-col"><div className="flex items-center justify-between p-3 border-b"><span className="text-sm font-medium">Chat with Priya</span><button onClick={() => setShowChat(false)} className="text-gray-500">✕</button></div><div className="flex-1 overflow-hidden"><ChatInterface ws={ws} isSpeaking={isSpeaking} /></div></div></div>}
      {showContact && <ContactForm onSubmit={(n,p) => { postEvent("visit_booking_clicked", { buyer_name: n, buyer_phone: p }); setShowContact(false); }} onClose={() => setShowContact(false)} />}
    </div>
  );
}
