"use client";

import { useState, useRef, useEffect } from "react";
import AriaAvatar from "./AriaAvatar";

interface ChatMessage {
  id: string;
  role: "user" | "aria";
  text: string;
  streaming?: boolean;
}

interface ChatInterfaceProps {
  ws: WebSocket | null;
  isSpeaking: boolean;
}

export default function ChatInterface({ ws, isSpeaking }: ChatInterfaceProps) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "aria",
      text: "Hi! I'm Aria, your AI property guide. Ask me anything — pricing, EMI options, floor plans, amenities, or RERA details. I'm here to help!",
    },
  ]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const streamingRef = useRef<string>("");

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (!ws) return;

    const handleMessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === "chat_token") {
          streamingRef.current += data.token;
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last?.streaming) {
              return [...prev.slice(0, -1), { ...last, text: streamingRef.current }];
            }
            return prev;
          });
        } else if (data.type === "chat_end") {
          streamingRef.current = "";
          setSending(false);
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last?.streaming) {
              return [...prev.slice(0, -1), { ...last, text: data.full_response, streaming: false }];
            }
            return prev;
          });
        } else if (data.type === "talking_start") {
          streamingRef.current = "";
          setMessages((prev) => [
            ...prev,
            { id: `aria-${Date.now()}`, role: "aria", text: "", streaming: true },
          ]);
        } else if (data.type === "error" && data.code === "KB_TIMEOUT") {
          setSending(false);
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last?.streaming) {
              return [...prev.slice(0, -1), { ...last, text: "I'm having trouble finding that information. Let me try a different approach — could you rephrase your question?", streaming: false }];
            }
            return prev;
          });
        } else if (data.type === "error" && data.code === "INVALID_MESSAGE") {
          setSending(false);
        }
      } catch { /* ignore */ }
    };

    ws.addEventListener("message", handleMessage);
    return () => ws.removeEventListener("message", handleMessage);
  }, [ws]);

  const sendMessage = () => {
    if (!ws || !input.trim() || input.length > 500 || sending) return;
    const text = input.trim();
    setMessages((prev) => [...prev, { id: `user-${Date.now()}`, role: "user", text }]);
    setInput("");
    setSending(true);
    ws.send(JSON.stringify({ action: "chat", message: text }));
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  };

  return (
    <div className="flex flex-col h-full bg-white">
      {/* Header */}
      <div className="flex items-center gap-3 p-4 border-b border-gray-100 bg-gray-50/50">
        <AriaAvatar size="sm" isSpeaking={isSpeaking} />
        <div className="flex-1">
          <p className="text-sm font-semibold text-gray-900">Aria</p>
          <p className="text-xs text-gray-500">AI Property Guide • Online</p>
        </div>
        {isSpeaking && (
          <div className="flex items-center gap-1">
            <span className="w-1 h-3 bg-blue-500 rounded-full animate-pulse" />
            <span className="w-1 h-4 bg-blue-500 rounded-full animate-pulse [animation-delay:150ms]" />
            <span className="w-1 h-2 bg-blue-500 rounded-full animate-pulse [animation-delay:300ms]" />
          </div>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 max-h-[350px]">
        {messages.map((msg) => (
          <div key={msg.id} className={`flex gap-2 ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            {msg.role === "aria" && <AriaAvatar size="sm" isSpeaking={msg.streaming} />}
            <div className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
              msg.role === "user"
                ? "bg-blue-600 text-white rounded-br-md"
                : "bg-gray-100 text-gray-800 rounded-bl-md"
            }`}>
              {msg.text || (msg.streaming ? (
                <span className="inline-flex gap-1 py-1">
                  <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" />
                  <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:150ms]" />
                  <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce [animation-delay:300ms]" />
                </span>
              ) : "")}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-4 border-t border-gray-100 bg-white">
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value.slice(0, 500))}
            onKeyDown={handleKeyDown}
            placeholder="Ask about price, EMI, amenities..."
            disabled={sending || !ws}
            className="flex-1 px-4 py-3 rounded-full border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-blue-100 focus:border-blue-400 disabled:opacity-50 bg-gray-50"
            maxLength={500}
          />
          <button
            onClick={sendMessage}
            disabled={!input.trim() || sending || !ws}
            className="w-10 h-10 bg-blue-600 text-white rounded-full flex items-center justify-center hover:bg-blue-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors shadow-md"
            aria-label="Send message"
          >
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
              <path d="M10.894 2.553a1 1 0 00-1.788 0l-7 14a1 1 0 001.169 1.409l5-1.429A1 1 0 009 15.571V11a1 1 0 112 0v4.571a1 1 0 00.725.962l5 1.428a1 1 0 001.17-1.408l-7-14z" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
