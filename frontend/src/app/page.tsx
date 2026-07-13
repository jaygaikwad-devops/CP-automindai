"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

export default function LandingPage() {
  const [loaded, setLoaded] = useState(false);
  const [activeStep, setActiveStep] = useState(0);

  useEffect(() => {
    setLoaded(true);
    const interval = setInterval(() => {
      setActiveStep((prev) => (prev + 1) % 4);
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="min-h-screen bg-white">
      {/* ===== NAVIGATION ===== */}
      <nav className="fixed top-0 left-0 right-0 z-50 bg-white/80 backdrop-blur-xl border-b border-gray-100">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-gradient-to-br from-blue-600 to-indigo-600 rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-sm">A</span>
            </div>
            <span className="text-xl font-bold text-gray-900">AutoMind</span>
          </div>
          <div className="hidden md:flex items-center gap-8 text-sm text-gray-600">
            <a href="#how-it-works" className="hover:text-gray-900 transition-colors">How It Works</a>
            <a href="#features" className="hover:text-gray-900 transition-colors">Features</a>
            <a href="#guide" className="hover:text-gray-900 transition-colors">Guide</a>
          </div>
          <Link
            href="/login"
            className="px-5 py-2.5 bg-gray-900 text-white rounded-full text-sm font-medium hover:bg-gray-800 transition-colors"
          >
            Login
          </Link>
        </div>
      </nav>

      {/* ===== HERO ===== */}
      <section className="relative pt-32 pb-20 md:pt-40 md:pb-32 overflow-hidden">
        {/* Background: Real construction → building photo */}
        <div className="absolute inset-0">
          <img
            src="https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?w=1920&q=80"
            alt="Modern skyscraper"
            className="w-full h-full object-cover"
          />
          <div className="absolute inset-0 bg-gradient-to-r from-white via-white/95 to-white/70" />
        </div>

        <div className={`relative max-w-7xl mx-auto px-6 transition-all duration-1000 ${loaded ? "opacity-100 translate-y-0" : "opacity-0 translate-y-10"}`}>
          <div className="max-w-2xl">
            <div className="inline-flex items-center gap-2 px-4 py-2 bg-blue-50 rounded-full mb-8">
              <span className="w-2 h-2 bg-blue-600 rounded-full animate-pulse" />
              <span className="text-sm font-medium text-blue-700">AI-Powered Real Estate Platform</span>
            </div>

            <h1 className="text-5xl md:text-6xl lg:text-7xl font-bold text-gray-900 leading-[1.1] tracking-tight mb-8">
              From Site Visit
              <br />
              <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-600 to-indigo-600">
                to Sold.
              </span>
            </h1>

            <p className="text-xl text-gray-600 leading-relaxed mb-10 max-w-lg">
              Share AI virtual tours on WhatsApp. Get instant alerts when buyers are ready. 
              Close deals faster with real-time intent scoring.
            </p>

            <div className="flex flex-col sm:flex-row gap-4">
              <Link
                href="/login"
                className="inline-flex items-center justify-center px-8 py-4 bg-gray-900 text-white rounded-full text-base font-semibold hover:bg-gray-800 shadow-xl shadow-gray-900/20 transition-all hover:-translate-y-0.5"
              >
                Get Started Free
                <span className="ml-2">→</span>
              </Link>
              <a
                href="#how-it-works"
                className="inline-flex items-center justify-center px-8 py-4 bg-white text-gray-700 rounded-full text-base font-semibold border border-gray-200 hover:border-gray-300 hover:shadow-lg transition-all"
              >
                Watch Demo
              </a>
            </div>

            {/* Trust indicators */}
            <div className="mt-14 flex items-center gap-8">
              <div>
                <div className="text-2xl font-bold text-gray-900">500+</div>
                <div className="text-xs text-gray-500">Channel Partners</div>
              </div>
              <div className="w-px h-10 bg-gray-200" />
              <div>
                <div className="text-2xl font-bold text-gray-900">10,000+</div>
                <div className="text-xs text-gray-500">Tours Generated</div>
              </div>
              <div className="w-px h-10 bg-gray-200" />
              <div>
                <div className="text-2xl font-bold text-gray-900">3 sec</div>
                <div className="text-xs text-gray-500">Lead Alert Time</div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ===== HOW IT WORKS ===== */}
      <section id="how-it-works" className="py-24 md:py-32 px-6 bg-gray-50">
        <div className="max-w-7xl mx-auto">
          <div className="text-center mb-20">
            <p className="text-sm font-semibold text-blue-600 uppercase tracking-wider mb-3">How It Works</p>
            <h2 className="text-4xl md:text-5xl font-bold text-gray-900">
              Four steps to your next deal
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-5xl mx-auto">
            {[
              {
                num: "01",
                title: "Share Tour Link",
                desc: "Pick a project, generate a branded WhatsApp link with OG preview card. Send to any buyer in one tap.",
                img: "https://images.unsplash.com/photo-1560518883-ce09059eeffa?w=600&q=80",
              },
              {
                num: "02",
                title: "Buyer Takes Virtual Tour",
                desc: "Buyer opens the link on their phone. They see a room-by-room walkthrough with real photos and AI narration.",
                img: "https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?w=600&q=80",
              },
              {
                num: "03",
                title: "Priya Answers Questions",
                desc: "Our AI avatar answers price, EMI, RERA, floor plan questions in real-time. Every interaction is scored.",
                img: "https://images.unsplash.com/photo-1553877522-43269d4ea984?w=600&q=80",
              },
              {
                num: "04",
                title: "You Get Hot Lead Alert",
                desc: "When buyer intent crosses threshold 7/10, you get instant WhatsApp notification with their name, phone, and what they asked.",
                img: "https://images.unsplash.com/photo-1611746872915-64382b5c76da?w=600&q=80",
              },
            ].map((step, i) => (
              <div
                key={i}
                className={`group relative bg-white rounded-3xl overflow-hidden border border-gray-100 hover:shadow-2xl hover:-translate-y-1 transition-all duration-500 ${activeStep === i ? "ring-2 ring-blue-500/50 shadow-xl" : ""}`}
              >
                <div className="aspect-[16/9] overflow-hidden">
                  <img
                    src={step.img}
                    alt={step.title}
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-700"
                  />
                  <div className="absolute top-4 left-4 w-10 h-10 bg-white rounded-full flex items-center justify-center shadow-lg">
                    <span className="text-sm font-bold text-gray-900">{step.num}</span>
                  </div>
                </div>
                <div className="p-6">
                  <h3 className="text-xl font-bold text-gray-900 mb-2">{step.title}</h3>
                  <p className="text-gray-500 text-sm leading-relaxed">{step.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ===== FEATURES / LEAD SCORING ===== */}
      <section id="features" className="py-24 md:py-32 px-6">
        <div className="max-w-7xl mx-auto">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">
            <div>
              <p className="text-sm font-semibold text-blue-600 uppercase tracking-wider mb-3">Real-Time Intelligence</p>
              <h2 className="text-4xl md:text-5xl font-bold text-gray-900 mb-6">
                Know who&apos;s ready
                <br />before they call you
              </h2>
              <p className="text-lg text-gray-600 mb-10 leading-relaxed">
                Every buyer interaction is scored automatically. You see exactly what they&apos;re interested in — 
                price, EMI, specific rooms, amenities — and get alerted the moment they&apos;re hot.
              </p>

              <div className="space-y-4">
                {[
                  { signal: "Spent 3+ minutes on tour", pts: "+2" },
                  { signal: "Asked about price or EMI", pts: "+3" },
                  { signal: "Revisited rooms", pts: "+2" },
                  { signal: "Returned within 24 hours", pts: "+2" },
                  { signal: "Clicked 'Book Visit'", pts: "+4" },
                ].map((item, i) => (
                  <div key={i} className="flex items-center justify-between py-3 border-b border-gray-100 last:border-0">
                    <span className="text-gray-700">{item.signal}</span>
                    <span className="px-3 py-1 bg-blue-50 text-blue-700 rounded-full text-sm font-semibold">{item.pts}</span>
                  </div>
                ))}
              </div>

              <div className="mt-8 p-4 bg-orange-50 border border-orange-200 rounded-2xl">
                <div className="flex items-center gap-3">
                  <span className="text-2xl">🔥</span>
                  <div>
                    <p className="font-semibold text-orange-900">Score reaches 7/10</p>
                    <p className="text-sm text-orange-700">You get instant WhatsApp alert with buyer details</p>
                  </div>
                </div>
              </div>
            </div>

            <div className="relative">
              <img
                src="https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=800&q=80"
                alt="Luxury apartment balcony view"
                className="rounded-3xl shadow-2xl"
              />
              {/* Floating notification card */}
              <div className="absolute -bottom-6 -left-6 bg-white rounded-2xl p-4 shadow-xl border border-gray-100 max-w-[280px]">
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 bg-red-100 rounded-full flex items-center justify-center flex-shrink-0">
                    <span className="text-lg">🔥</span>
                  </div>
                  <div>
                    <p className="text-sm font-semibold text-gray-900">Hot Lead Alert!</p>
                    <p className="text-xs text-gray-500 mt-0.5">Priya Sharma • Score 8/10</p>
                    <p className="text-xs text-gray-400 mt-0.5">Asked about EMI for 2BHK</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ===== QUICK START GUIDE ===== */}
      <section id="guide" className="py-24 md:py-32 px-6 bg-gray-50">
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-16">
            <p className="text-sm font-semibold text-blue-600 uppercase tracking-wider mb-3">Get Started</p>
            <h2 className="text-4xl md:text-5xl font-bold text-gray-900 mb-4">
              Your first lead in 5 minutes
            </h2>
            <p className="text-gray-500 text-lg">No setup fees. No credit card. Just results.</p>
          </div>

          <div className="space-y-1">
            {[
              { step: "1", title: "Login with your phone", desc: "Enter your mobile number, receive OTP, and you're in. Takes 30 seconds.", icon: "📱" },
              { step: "2", title: "See your assigned projects", desc: "Your builder's projects appear automatically with tour status and location details.", icon: "🏗️" },
              { step: "3", title: "Share a tour on WhatsApp", desc: "One tap generates a branded link. Send to buyers directly from WhatsApp.", icon: "📲" },
              { step: "4", title: "Buyer explores with AI guide", desc: "They see rooms, ask questions, get instant answers about price, EMI, amenities.", icon: "🤖" },
              { step: "5", title: "Score reaches 7 — you get alerted", desc: "WhatsApp notification arrives: buyer name, phone, what they're interested in.", icon: "🔔" },
              { step: "6", title: "Call and close", desc: "You know exactly what they want. Follow up while they're still engaged.", icon: "🤝" },
            ].map((item, i) => (
              <div key={i} className="flex gap-5 items-start p-5 rounded-2xl hover:bg-white hover:shadow-lg transition-all duration-300 group">
                <div className="w-12 h-12 bg-white border-2 border-gray-200 group-hover:border-blue-500 group-hover:bg-blue-50 rounded-2xl flex items-center justify-center text-xl transition-all flex-shrink-0">
                  {item.icon}
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-gray-900 mb-1">{item.title}</h3>
                  <p className="text-gray-500 text-sm">{item.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ===== FINAL CTA ===== */}
      <section className="py-24 md:py-32 px-6 relative overflow-hidden">
        <div className="absolute inset-0">
          <img
            src="https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?w=1920&q=80"
            alt="Modern residential building"
            className="w-full h-full object-cover"
          />
          <div className="absolute inset-0 bg-gray-900/85" />
        </div>

        <div className="relative max-w-3xl mx-auto text-center">
          <h2 className="text-4xl md:text-5xl font-bold text-white mb-6 leading-tight">
            Stop waiting for buyers to call.
            <br />
            <span className="text-blue-400">Start knowing when they&apos;re ready.</span>
          </h2>
          <p className="text-xl text-gray-300 mb-10 max-w-xl mx-auto">
            Every tour you share is a lead machine working 24/7. 
            Priya qualifies buyers while you focus on closing.
          </p>
          <Link
            href="/login"
            className="inline-flex items-center justify-center px-10 py-5 bg-white text-gray-900 rounded-full text-lg font-bold shadow-2xl hover:-translate-y-1 transition-all duration-300"
          >
            Start Now — It&apos;s Free →
          </Link>
          <p className="text-gray-400 text-sm mt-6">OTP login • No passwords • Live in 30 seconds</p>
        </div>
      </section>

      {/* ===== FOOTER ===== */}
      <footer className="py-12 px-6 bg-white border-t border-gray-100">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 bg-gradient-to-br from-blue-600 to-indigo-600 rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-xs">A</span>
            </div>
            <span className="font-bold text-gray-900">AutoMind AI</span>
            <span className="text-gray-400 text-sm ml-2">— AI Virtual Tours for Real Estate</span>
          </div>
          <div className="flex items-center gap-6 text-sm text-gray-500">
            <Link href="/login" className="hover:text-gray-900 transition-colors">CP Login</Link>
            <a href="https://api.automindai.info/docs" target="_blank" rel="noopener noreferrer" className="hover:text-gray-900 transition-colors">API</a>
            <span>© 2026 AutoMind AI Platform</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
