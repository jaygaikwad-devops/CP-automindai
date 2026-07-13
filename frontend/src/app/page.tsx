"use client";

import { useEffect, useState, useRef } from "react";
import Link from "next/link";
import PriyaAvatar from "@/components/PriyaAvatar";

// Construction → Building animation phases
const PHASES = [
  { label: "Foundation", progress: 15 },
  { label: "Structure", progress: 35 },
  { label: "Finishing", progress: 60 },
  { label: "Interiors", progress: 80 },
  { label: "Ready to Move", progress: 100 },
];

export default function LandingPage() {
  const [buildPhase, setBuildPhase] = useState(0);
  const [showContent, setShowContent] = useState(false);
  const [scrollY, setScrollY] = useState(0);
  const heroRef = useRef<HTMLDivElement>(null);

  // Building animation on load
  useEffect(() => {
    const timer = setInterval(() => {
      setBuildPhase((prev) => {
        if (prev >= PHASES.length - 1) {
          clearInterval(timer);
          setTimeout(() => setShowContent(true), 400);
          return prev;
        }
        return prev + 1;
      });
    }, 600);
    return () => clearInterval(timer);
  }, []);

  // Parallax scroll
  useEffect(() => {
    const handleScroll = () => setScrollY(window.scrollY);
    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <div className="min-h-screen bg-white overflow-x-hidden">
      {/* ===== HERO SECTION ===== */}
      <section ref={heroRef} className="relative min-h-screen flex items-center justify-center overflow-hidden">
        {/* Animated gradient background */}
        <div className="absolute inset-0 bg-gradient-to-br from-slate-900 via-blue-900 to-indigo-900" />
        
        {/* Floating particles */}
        <div className="absolute inset-0 overflow-hidden">
          {[...Array(20)].map((_, i) => (
            <div
              key={i}
              className="absolute w-1 h-1 bg-white/20 rounded-full animate-pulse"
              style={{
                left: `${Math.random() * 100}%`,
                top: `${Math.random() * 100}%`,
                animationDelay: `${Math.random() * 3}s`,
                animationDuration: `${2 + Math.random() * 3}s`,
              }}
            />
          ))}
        </div>

        {/* Building Animation */}
        <div className="absolute inset-0 flex items-end justify-center pb-20 opacity-20" style={{ transform: `translateY(${scrollY * 0.3}px)` }}>
          <svg viewBox="0 0 400 300" className="w-[600px] h-[450px]" fill="none">
            {/* Ground */}
            <rect x="0" y="280" width="400" height="20" fill="#1e3a5f" opacity="0.5" />
            
            {/* Building floors - animate based on phase */}
            {[...Array(Math.min(buildPhase + 1, 5))].map((_, i) => (
              <g key={i} className="animate-in fade-in slide-in-from-bottom duration-500" style={{ animationDelay: `${i * 200}ms` }}>
                <rect x={120} y={260 - i * 50} width="160" height="45" fill={`rgba(59, 130, 246, ${0.3 + i * 0.1})`} stroke="rgba(147, 197, 253, 0.3)" strokeWidth="1" rx="2" />
                {/* Windows */}
                {[...Array(4)].map((_, j) => (
                  <rect key={j} x={135 + j * 38} y={268 - i * 50} width="20" height="28" fill={buildPhase >= i ? "rgba(251, 191, 36, 0.6)" : "rgba(30, 58, 95, 0.5)"} rx="1" />
                ))}
              </g>
            ))}
            
            {/* Crane (visible during construction) */}
            {buildPhase < 4 && (
              <g className="animate-pulse" style={{ animationDuration: "2s" }}>
                <line x1="320" y1="50" x2="320" y2="280" stroke="rgba(251, 191, 36, 0.4)" strokeWidth="3" />
                <line x1="250" y1="55" x2="380" y2="55" stroke="rgba(251, 191, 36, 0.4)" strokeWidth="2" />
                <line x1="300" y1="55" x2="300" y2="100" stroke="rgba(147, 197, 253, 0.3)" strokeWidth="1" strokeDasharray="4" />
              </g>
            )}
            
            {/* Completed flag */}
            {buildPhase >= 4 && (
              <g className="animate-in fade-in zoom-in duration-700">
                <rect x="185" y="30" width="30" height="20" fill="#22c55e" rx="2" />
                <line x1="185" y1="30" x2="185" y2="60" stroke="#22c55e" strokeWidth="2" />
                <text x="192" y="44" fill="white" fontSize="8" fontWeight="bold">✓</text>
              </g>
            )}
          </svg>
        </div>

        {/* Hero Content */}
        <div className={`relative z-10 text-center px-6 max-w-4xl mx-auto transition-all duration-1000 ${showContent ? "opacity-100 translate-y-0" : "opacity-0 translate-y-8"}`}>
          {/* Phase indicator */}
          <div className="mb-8">
            <div className="inline-flex items-center gap-2 px-4 py-2 bg-white/10 backdrop-blur-sm rounded-full border border-white/20 mb-6">
              <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
              <span className="text-white/80 text-xs font-medium tracking-wider uppercase">
                {buildPhase >= 4 ? "Platform Live" : `Building... ${PHASES[buildPhase].label}`}
              </span>
            </div>
          </div>

          <h1 className="text-5xl md:text-7xl font-bold text-white mb-6 leading-tight tracking-tight">
            Turn Property Tours into
            <span className="block bg-gradient-to-r from-blue-400 via-cyan-300 to-teal-300 bg-clip-text text-transparent">
              Hot Leads
            </span>
          </h1>
          
          <p className="text-lg md:text-xl text-blue-100/80 mb-10 max-w-2xl mx-auto leading-relaxed">
            AI-powered virtual tours with Priya — your 24/7 sales avatar. 
            Share on WhatsApp, score buyer intent in real-time, 
            and get instant alerts when they&apos;re ready to buy.
          </p>

          {/* CTA Buttons */}
          <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-12">
            <Link
              href="/login"
              className="group relative px-8 py-4 bg-white text-slate-900 rounded-2xl font-bold text-lg shadow-2xl shadow-white/20 hover:shadow-white/30 transition-all duration-300 hover:-translate-y-1"
            >
              <span className="relative z-10">Start Selling Smarter →</span>
              <div className="absolute inset-0 bg-gradient-to-r from-blue-50 to-cyan-50 rounded-2xl opacity-0 group-hover:opacity-100 transition-opacity" />
            </Link>
            <a
              href="#how-it-works"
              className="px-8 py-4 text-white/90 border border-white/30 rounded-2xl font-medium hover:bg-white/10 transition-all duration-300"
            >
              See How It Works
            </a>
          </div>

          {/* Stats */}
          <div className="grid grid-cols-3 gap-8 max-w-md mx-auto">
            <div className="text-center">
              <div className="text-3xl font-bold text-white">3s</div>
              <div className="text-xs text-blue-200/60 mt-1">Lead Alert Time</div>
            </div>
            <div className="text-center">
              <div className="text-3xl font-bold text-white">10x</div>
              <div className="text-xs text-blue-200/60 mt-1">More Conversions</div>
            </div>
            <div className="text-center">
              <div className="text-3xl font-bold text-white">24/7</div>
              <div className="text-xs text-blue-200/60 mt-1">AI Sales Avatar</div>
            </div>
          </div>
        </div>

        {/* Scroll indicator */}
        <div className="absolute bottom-8 left-1/2 -translate-x-1/2 animate-bounce">
          <svg className="w-6 h-6 text-white/40" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
          </svg>
        </div>
      </section>

      {/* ===== HOW IT WORKS ===== */}
      <section id="how-it-works" className="py-24 px-6 bg-gradient-to-b from-slate-50 to-white">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-4xl md:text-5xl font-bold text-slate-900 mb-4">
              How AutoMind Works
            </h2>
            <p className="text-lg text-slate-500 max-w-2xl mx-auto">
              From property listing to hot lead — in 4 simple steps
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
            {[
              { step: "1", icon: "📲", title: "Share Tour", desc: "Generate a WhatsApp link for any project. Share with buyers in one tap." },
              { step: "2", icon: "🏠", title: "Buyer Explores", desc: "Buyer opens the link — sees an AI-narrated room-by-room virtual tour." },
              { step: "3", icon: "💬", title: "Priya Engages", desc: "Our AI avatar Priya answers questions about price, EMI, amenities in real-time." },
              { step: "4", icon: "🔥", title: "Hot Lead Alert", desc: "When engagement score hits 7+, you get an instant WhatsApp alert with buyer details." },
            ].map((item, i) => (
              <div key={i} className="relative group">
                <div className="bg-white rounded-3xl p-8 shadow-lg shadow-slate-200/50 border border-slate-100 hover:shadow-xl hover:-translate-y-2 transition-all duration-500">
                  <div className="text-4xl mb-4">{item.icon}</div>
                  <div className="absolute -top-3 -right-3 w-8 h-8 bg-blue-600 text-white rounded-full flex items-center justify-center text-sm font-bold shadow-lg">
                    {item.step}
                  </div>
                  <h3 className="text-xl font-bold text-slate-900 mb-2">{item.title}</h3>
                  <p className="text-slate-500 text-sm leading-relaxed">{item.desc}</p>
                </div>
                {i < 3 && (
                  <div className="hidden md:block absolute top-1/2 -right-4 w-8 text-slate-300">
                    →
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ===== MEET PRIYA ===== */}
      <section className="py-24 px-6 bg-gradient-to-br from-indigo-50 via-white to-cyan-50">
        <div className="max-w-5xl mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-16 items-center">
            <div>
              <div className="inline-flex items-center gap-2 px-3 py-1 bg-indigo-100 rounded-full mb-6">
                <PriyaAvatar size="badge" isSpeaking />
                <span className="text-sm font-medium text-indigo-700">Meet Priya</span>
              </div>
              <h2 className="text-4xl font-bold text-slate-900 mb-6">
                Your AI Sales Avatar That Never Sleeps
              </h2>
              <p className="text-lg text-slate-600 mb-8 leading-relaxed">
                Priya narrates every room, answers buyer questions about price, EMI, RERA, and amenities — 
                powered by AI that knows everything about your project. She works 24/7, never takes a day off, 
                and identifies hot buyers before they even call you.
              </p>
              <ul className="space-y-4">
                {[
                  "Narrates tours room-by-room with project knowledge",
                  "Answers price, EMI, RERA questions instantly",
                  "Scores buyer intent in real-time (0-10)",
                  "Triggers WhatsApp alert when buyer is hot",
                ].map((item, i) => (
                  <li key={i} className="flex items-start gap-3">
                    <span className="w-6 h-6 bg-green-100 text-green-600 rounded-full flex items-center justify-center text-xs flex-shrink-0 mt-0.5">✓</span>
                    <span className="text-slate-700">{item}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div className="relative">
              <div className="bg-gradient-to-br from-slate-800 to-slate-900 rounded-3xl p-6 shadow-2xl">
                <div className="bg-slate-700/50 rounded-2xl p-4 mb-4">
                  <div className="flex items-center gap-2 mb-3">
                    <PriyaAvatar size="header" isSpeaking />
                    <div>
                      <p className="text-white text-sm font-medium">Priya</p>
                      <p className="text-slate-400 text-xs">AI Tour Guide</p>
                    </div>
                  </div>
                  <div className="bg-slate-600/50 rounded-xl p-3">
                    <p className="text-sm text-slate-200 leading-relaxed">
                      &quot;The 2BHK starts at ₹85 lakhs with a carpet area of 650 sq ft. 
                      EMI would be approximately ₹52,000/month for a 20-year loan at 8.5%. 
                      Would you like me to tell you about the payment plan?&quot;
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <div className="flex-1 bg-slate-700 rounded-full px-4 py-2">
                    <p className="text-slate-400 text-sm">What is the EMI for 2BHK?</p>
                  </div>
                  <div className="w-8 h-8 bg-blue-500 rounded-full flex items-center justify-center">
                    <svg className="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 20 20"><path d="M10.894 2.553a1 1 0 00-1.788 0l-7 14a1 1 0 001.169 1.409l5-1.429A1 1 0 009 15.571V11a1 1 0 112 0v4.571a1 1 0 00.725.962l5 1.428a1 1 0 001.17-1.408l-7-14z" /></svg>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ===== LEAD SCORING ===== */}
      <section className="py-24 px-6 bg-white">
        <div className="max-w-5xl mx-auto text-center">
          <h2 className="text-4xl font-bold text-slate-900 mb-4">
            Know Exactly Who&apos;s Ready to Buy
          </h2>
          <p className="text-lg text-slate-500 mb-16 max-w-2xl mx-auto">
            Every buyer interaction is scored. When intent is high, you know instantly.
          </p>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 max-w-3xl mx-auto mb-12">
            {[
              { signal: "Viewed 3+ min", points: "+2", color: "bg-blue-50 text-blue-700 border-blue-200" },
              { signal: "Asked about price", points: "+2", color: "bg-purple-50 text-purple-700 border-purple-200" },
              { signal: "Asked about EMI", points: "+3", color: "bg-pink-50 text-pink-700 border-pink-200" },
              { signal: "Revisited rooms", points: "+2", color: "bg-amber-50 text-amber-700 border-amber-200" },
              { signal: "Return visit", points: "+2", color: "bg-teal-50 text-teal-700 border-teal-200" },
              { signal: "Shared tour", points: "+1", color: "bg-green-50 text-green-700 border-green-200" },
              { signal: "Booked visit", points: "+4", color: "bg-red-50 text-red-700 border-red-200" },
              { signal: "Score ≥ 7", points: "🔥 ALERT", color: "bg-orange-50 text-orange-700 border-orange-200" },
            ].map((item, i) => (
              <div key={i} className={`${item.color} border rounded-2xl p-4 text-center`}>
                <div className="text-lg font-bold">{item.points}</div>
                <div className="text-xs mt-1 opacity-80">{item.signal}</div>
              </div>
            ))}
          </div>

          <div className="inline-flex items-center gap-3 px-6 py-3 bg-orange-50 border border-orange-200 rounded-full">
            <span className="text-2xl">📱</span>
            <span className="text-sm text-orange-800 font-medium">Score hits 7 → Instant WhatsApp alert with buyer details</span>
          </div>
        </div>
      </section>

      {/* ===== USER GUIDE ===== */}
      <section className="py-24 px-6 bg-gradient-to-b from-slate-50 to-white">
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="text-4xl font-bold text-slate-900 mb-4">Quick Start Guide</h2>
            <p className="text-slate-500">Get your first hot lead in under 5 minutes</p>
          </div>

          <div className="space-y-6">
            {[
              { step: "1", title: "Login with OTP", desc: "Enter your phone number → receive OTP → you're in. No passwords to remember.", time: "30 sec" },
              { step: "2", title: "Browse Your Projects", desc: "See all builder projects assigned to you. Each shows tour status and location.", time: "10 sec" },
              { step: "3", title: "Share Tour on WhatsApp", desc: "Tap 'Share on WhatsApp' → a branded link with preview card is ready to send to any buyer.", time: "5 sec" },
              { step: "4", title: "Buyer Explores with Priya", desc: "Buyer opens the link → sees AI-narrated virtual tour → asks questions → engagement is scored automatically.", time: "2-5 min" },
              { step: "5", title: "Get Hot Lead Alert", desc: "When buyer shows high intent (score 7+), you get instant WhatsApp notification with their details.", time: "< 3 sec" },
              { step: "6", title: "Follow Up & Close", desc: "Call the buyer while they're still engaged. You know exactly what they asked about.", time: "You decide" },
            ].map((item, i) => (
              <div key={i} className="flex gap-6 items-start group">
                <div className="w-12 h-12 bg-blue-600 text-white rounded-2xl flex items-center justify-center text-lg font-bold flex-shrink-0 group-hover:scale-110 transition-transform shadow-lg shadow-blue-200">
                  {item.step}
                </div>
                <div className="flex-1 bg-white rounded-2xl p-6 border border-slate-100 shadow-sm group-hover:shadow-md transition-shadow">
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="text-lg font-bold text-slate-900">{item.title}</h3>
                    <span className="text-xs text-slate-400 bg-slate-50 px-2 py-1 rounded-full">{item.time}</span>
                  </div>
                  <p className="text-slate-500 text-sm">{item.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ===== CTA SECTION ===== */}
      <section className="py-24 px-6 bg-gradient-to-br from-blue-600 via-indigo-600 to-purple-700 relative overflow-hidden">
        <div className="absolute inset-0 opacity-10">
          <div className="absolute top-10 left-10 w-64 h-64 bg-white rounded-full blur-3xl" />
          <div className="absolute bottom-10 right-10 w-96 h-96 bg-cyan-300 rounded-full blur-3xl" />
        </div>
        
        <div className="max-w-3xl mx-auto text-center relative z-10">
          <div className="inline-block mb-6">
            <PriyaAvatar size="cta" isSpeaking />
          </div>
          <h2 className="text-4xl md:text-5xl font-bold text-white mb-6">
            Ready to Close More Deals?
          </h2>
          <p className="text-xl text-blue-100/80 mb-10 max-w-xl mx-auto">
            Join Channel Partners who are generating 10x more qualified leads with AI-powered tours.
          </p>
          <Link
            href="/login"
            className="inline-block px-10 py-5 bg-white text-blue-700 rounded-2xl font-bold text-lg shadow-2xl hover:shadow-white/20 hover:-translate-y-1 transition-all duration-300"
          >
            Login & Start Sharing Tours →
          </Link>
          <p className="text-blue-200/60 text-sm mt-6">
            Free to try • No credit card required • OTP login in 30 seconds
          </p>
        </div>
      </section>

      {/* ===== FOOTER ===== */}
      <footer className="py-12 px-6 bg-slate-900 text-center">
        <div className="max-w-4xl mx-auto">
          <div className="flex items-center justify-center gap-2 mb-4">
            <PriyaAvatar size="badge" isSpeaking={false} />
            <span className="text-xl font-bold text-white">AutoMind AI</span>
          </div>
          <p className="text-slate-400 text-sm mb-6">
            AI-Powered Virtual Tours for Real Estate Channel Partners
          </p>
          <div className="flex items-center justify-center gap-6 text-sm text-slate-500">
            <Link href="/login" className="hover:text-white transition-colors">Login</Link>
            <span>•</span>
            <a href="https://api.automindai.info/docs" target="_blank" rel="noopener noreferrer" className="hover:text-white transition-colors">API Docs</a>
            <span>•</span>
            <span>© 2026 AutoMind AI</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
