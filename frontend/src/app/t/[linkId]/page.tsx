"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useParams } from "next/navigation";
import PriyaAvatar from "@/components/PriyaAvatar";
import ChatInterface from "@/components/ChatInterface";
import ContactForm from "@/components/ContactForm";

interface Room {
  index: number;
  id: string;
  name: string;
  room_type: string;
  narration: { text: string; duration_seconds: number; language: string };
  visuals: {
    primary_image_url: string;
    thumbnail_url?: string;
    labels: string[];
    dimensions?: { width: number; height: number };
  };
  features: Array<{ name: string; category: string }>;
  transition: { type: string; duration_ms: number };
}

interface TourScript {
  schema_version: string;
  project_id: string;
  project_name: string;
  total_rooms: number;
  estimated_duration_seconds: number;
  rooms: Room[];
}

const API_BASE = "";

export default function TourViewerPage() {
  const params = useParams();
  const linkId = params.linkId as string;

  // State
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

  // Tracking refs
  const viewedRooms = useRef<Set<number>>(new Set());
  const roomEnteredAt = useRef<number>(Date.now());
  const totalViewTime = useRef<number>(0);
  const timeThresholdFired = useRef(false);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  // Create anonymous session and load tour
  useEffect(() => {
    async function initTour() {
      try {
        // Create anonymous session
        const sessionRes = await fetch(`${API_BASE}/api/v1/auth/session/anonymous`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ link_id: linkId }),
        });

        if (!sessionRes.ok) {
          setError("This tour link is no longer valid.");
          setLoading(false);
          return;
        }

        const sessionData = await sessionRes.json();
        setSessionId(sessionData.session_id);
        setSessionToken(sessionData.session_token);

        // Load tour script (in real app this comes from CDN/API)
        // For now use a placeholder tour script
        const mockTour: TourScript = {
          schema_version: "1.0.0",
          project_id: "demo",
          project_name: "Sunshine Heights",
          total_rooms: 5,
          estimated_duration_seconds: 180,
          rooms: [
            {
              index: 0, id: "living_room", name: "Living Room", room_type: "living_room",
              narration: { text: "Welcome to the spacious living room with natural light and Italian marble flooring.", duration_seconds: 20, language: "en" },
              visuals: { primary_image_url: "/images/living_room.jpg", labels: ["sofa", "window", "natural_light"] },
              features: [{ name: "Italian Marble Flooring", category: "flooring" }, { name: "Floor-to-ceiling Windows", category: "windows" }],
              transition: { type: "slide_left", duration_ms: 300 },
            },
            {
              index: 1, id: "master_bedroom", name: "Master Bedroom", room_type: "bedroom",
              narration: { text: "The master bedroom features a walk-in closet and en-suite bathroom with premium fittings.", duration_seconds: 20, language: "en" },
              visuals: { primary_image_url: "/images/bedroom.jpg", labels: ["bed", "closet", "window"] },
              features: [{ name: "Walk-in Closet", category: "storage" }, { name: "En-suite Bathroom", category: "bathroom" }],
              transition: { type: "slide_left", duration_ms: 300 },
            },
            {
              index: 2, id: "kitchen", name: "Modular Kitchen", room_type: "kitchen",
              narration: { text: "The modular kitchen comes fully equipped with granite countertops and stainless steel appliances.", duration_seconds: 20, language: "en" },
              visuals: { primary_image_url: "/images/kitchen.jpg", labels: ["counter", "appliances", "cabinets"] },
              features: [{ name: "Granite Countertops", category: "countertop" }, { name: "Chimney & Hob", category: "appliance" }],
              transition: { type: "slide_left", duration_ms: 300 },
            },
            {
              index: 3, id: "balcony", name: "Balcony", room_type: "balcony",
              narration: { text: "Step out onto the balcony for a panoramic view of the city skyline and green surroundings.", duration_seconds: 20, language: "en" },
              visuals: { primary_image_url: "/images/balcony.jpg", labels: ["view", "railing", "plants"] },
              features: [{ name: "Panoramic City View", category: "view" }, { name: "Anti-skid Flooring", category: "flooring" }],
              transition: { type: "slide_left", duration_ms: 300 },
            },
            {
              index: 4, id: "amenities", name: "Amenities", room_type: "amenities",
              narration: { text: "The project offers world-class amenities including a swimming pool, gym, and children's play area.", duration_seconds: 20, language: "en" },
              visuals: { primary_image_url: "/images/amenities.jpg", labels: ["pool", "gym", "garden"] },
              features: [{ name: "Swimming Pool", category: "fitness" }, { name: "Gymnasium", category: "fitness" }, { name: "Children's Play Area", category: "recreation" }],
              transition: { type: "slide_left", duration_ms: 300 },
            },
          ],
        };
        setTourScript(mockTour);
        viewedRooms.current.add(0);
        setLoading(false);
      } catch {
        setError("Failed to load tour. Please try again.");
        setLoading(false);
      }
    }

    if (linkId) initTour();
  }, [linkId]);

  // Connect WebSocket
  useEffect(() => {
    if (!sessionId || !sessionToken) return;

    const wsUrl = `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}/ws/tour/${sessionId}?session_token=${sessionToken}`;
    const socket = new WebSocket(wsUrl);

    socket.onopen = () => setWs(socket);
    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "talking_start") setIsSpeaking(true);
        if (data.type === "talking_end") setIsSpeaking(false);
      } catch { /* ignore */ }
    };
    socket.onclose = () => {
      setWs(null);
      setIsSpeaking(false);
    };

    return () => { socket.close(); };
  }, [sessionId, sessionToken]);

  // Time tracking
  useEffect(() => {
    timerRef.current = setInterval(() => {
      totalViewTime.current += 1;
      // Check 3-minute threshold
      if (totalViewTime.current >= 180 && !timeThresholdFired.current) {
        timeThresholdFired.current = true;
        postEvent("time_on_tour_3min_plus", { duration_seconds: totalViewTime.current });
      }
    }, 1000);

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
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

  const navigateRoom = (direction: "next" | "prev") => {
    if (!tourScript || transitioning) return;
    const newIndex = direction === "next" ? currentRoomIndex + 1 : currentRoomIndex - 1;
    if (newIndex < 0 || newIndex >= tourScript.rooms.length) return;

    // Track time on current room
    const timeSpent = Math.floor((Date.now() - roomEnteredAt.current) / 1000);
    postEvent("room_viewed", { room_id: tourScript.rooms[currentRoomIndex].id, duration_seconds: timeSpent });

    // Check for revisit
    if (viewedRooms.current.has(newIndex)) {
      postEvent("room_revisited", { room_id: tourScript.rooms[newIndex].id });
    }
    viewedRooms.current.add(newIndex);

    // Transition
    setTransitioning(true);
    setTimeout(() => {
      setCurrentRoomIndex(newIndex);
      roomEnteredAt.current = Date.now();
      setTransitioning(false);
    }, 300);
  };

  const handleBookVisit = () => setShowContact(true);

  const handleContactSubmit = (name: string, phone: string) => {
    postEvent("visit_booking_clicked", { buyer_name: name, buyer_phone: phone });
    setShowContact(false);
    alert("Thank you! A representative will contact you shortly.");
  };

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-900">
        <div className="text-center">
          <PriyaAvatar size="cta" isSpeaking={true} />
          <p className="text-white mt-4 text-sm">Loading your tour...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-900 p-4">
        <div className="text-center">
          <p className="text-red-400 text-lg mb-2">Tour Unavailable</p>
          <p className="text-gray-400 text-sm">{error}</p>
        </div>
      </div>
    );
  }

  if (!tourScript) return null;

  const currentRoom = tourScript.rooms[currentRoomIndex];
  const isFirst = currentRoomIndex === 0;
  const isLast = currentRoomIndex === tourScript.rooms.length - 1;

  return (
    <div className="min-h-screen bg-gray-900 flex flex-col">
      {/* Header */}
      <header className="bg-gray-900/90 backdrop-blur-sm border-b border-gray-800 px-4 py-3 flex items-center justify-between z-10">
        <div className="flex items-center gap-3">
          <PriyaAvatar size="header" isSpeaking={isSpeaking} />
          <div>
            <p className="text-sm font-medium text-white">{tourScript.project_name}</p>
            <p className="text-xs text-gray-400">
              Room {currentRoomIndex + 1} of {tourScript.total_rooms}
            </p>
          </div>
        </div>
        <button
          onClick={handleBookVisit}
          className="px-4 py-2 bg-green-600 text-white text-sm rounded-full font-medium hover:bg-green-700 transition-colors"
        >
          Book Visit
        </button>
      </header>

      {/* Room display */}
      <div className="flex-1 relative overflow-hidden">
        <div
          className={`w-full h-full flex items-center justify-center transition-opacity duration-300 ${
            transitioning ? "opacity-0" : "opacity-100"
          }`}
        >
          {/* Room image placeholder (in real app: actual image from CDN) */}
          <div className="w-full h-full bg-gradient-to-br from-gray-700 to-gray-900 flex items-center justify-center">
            <div className="text-center p-8 max-w-lg">
              <h2 className="text-3xl font-bold text-white mb-3">{currentRoom.name}</h2>
              <p className="text-gray-300 text-sm mb-6">{currentRoom.narration.text}</p>
              <div className="flex flex-wrap gap-2 justify-center">
                {currentRoom.features.map((f, i) => (
                  <span key={i} className="px-3 py-1 bg-white/10 text-white/80 rounded-full text-xs">
                    {f.name}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Navigation arrows */}
        <div className="absolute inset-y-0 left-0 flex items-center pl-4">
          <button
            onClick={() => navigateRoom("prev")}
            disabled={isFirst}
            className="w-10 h-10 rounded-full bg-black/50 text-white flex items-center justify-center hover:bg-black/70 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
            aria-label="Previous room"
          >
            ←
          </button>
        </div>
        <div className="absolute inset-y-0 right-0 flex items-center pr-4">
          <button
            onClick={() => navigateRoom("next")}
            disabled={isLast}
            className="w-10 h-10 rounded-full bg-black/50 text-white flex items-center justify-center hover:bg-black/70 disabled:opacity-30 disabled:cursor-not-allowed transition-all"
            aria-label="Next room"
          >
            →
          </button>
        </div>

        {/* Room thumbnails */}
        <div className="absolute bottom-4 left-1/2 -translate-x-1/2 flex gap-2">
          {tourScript.rooms.map((room, i) => (
            <button
              key={room.id}
              onClick={() => {
                if (i !== currentRoomIndex) {
                  if (viewedRooms.current.has(i)) {
                    postEvent("room_revisited", { room_id: room.id });
                  }
                  viewedRooms.current.add(i);
                  setCurrentRoomIndex(i);
                  roomEnteredAt.current = Date.now();
                }
              }}
              className={`w-2.5 h-2.5 rounded-full transition-all ${
                i === currentRoomIndex ? "bg-white scale-125" : "bg-white/40 hover:bg-white/70"
              }`}
              aria-label={`Go to ${room.name}`}
            />
          ))}
        </div>
      </div>

      {/* Bottom bar: Chat toggle + CTA */}
      <div className="bg-gray-900/90 backdrop-blur-sm border-t border-gray-800 px-4 py-3 flex items-center justify-between">
        <button
          onClick={() => setShowChat(!showChat)}
          className="flex items-center gap-2 px-4 py-2 bg-white/10 text-white rounded-full text-sm hover:bg-white/20 transition-colors"
        >
          <PriyaAvatar size="badge" isSpeaking={isSpeaking} />
          <span>{showChat ? "Close Chat" : "Ask Priya"}</span>
        </button>

        <button
          onClick={handleBookVisit}
          className="px-5 py-2.5 bg-primary-600 text-white rounded-full text-sm font-medium hover:bg-primary-700 transition-colors"
        >
          📞 Contact Us
        </button>
      </div>

      {/* Chat panel (slide up) */}
      {showChat && (
        <div className="fixed bottom-0 left-0 right-0 h-[60vh] z-40 bg-white rounded-t-2xl shadow-2xl animate-in slide-in-from-bottom">
          <div className="h-full flex flex-col">
            <div className="flex items-center justify-between p-3 border-b">
              <span className="text-sm font-medium">Chat with Priya</span>
              <button onClick={() => setShowChat(false)} className="text-gray-500 hover:text-gray-700">
                ✕
              </button>
            </div>
            <div className="flex-1 overflow-hidden">
              <ChatInterface ws={ws} isSpeaking={isSpeaking} />
            </div>
          </div>
        </div>
      )}

      {/* Contact form modal */}
      {showContact && (
        <ContactForm
          onSubmit={handleContactSubmit}
          onClose={() => setShowContact(false)}
        />
      )}
    </div>
  );
}
