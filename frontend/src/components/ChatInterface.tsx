"use client";

import { useState, useRef, useEffect } from "react";
import PriyaAvatar from "./PriyaAvatar";

interface ChatMessage {
  id: string;
  role: "user" | "priya";
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
      role: "priya",
      text: "Hi! I'm Priya, your AI tour guide. Ask me anything about this property — pricing, amenities, floor plans, or anything else!",
    },
  ]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const streamingRef = useRef<string>("");

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Listen for WebSocket messages
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
              return [
                ...prev.slice(0, -1),
                { ...last, text: streamingRef.current },
              ];
            }
            return prev;
          });
        } else if (data.type === "chat_end") {
          streamingRef.current = "";
          setSending(false);
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last?.streaming) {
              return [
                ...prev.slice(0, -1),
                { ...last, text: data.full_response, streaming: false },
              ];
            }
            return prev;
          });
        } else if (data.type === "talking_start") {
          // Create streaming message placeholder
          streamingRef.current = "";
          setMessages((prev) => [
            ...prev,
            { id: `priya-${Date.now()}`, role: "priya", text: "", streaming: true },
          ]);
        } else if (data.type === "error" && data.code === "KB_TIMEOUT") {
          setSending(false);
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last?.streaming) {
              return [
                ...prev.slice(0, -1),
                {
                  ...last,
                  text: "Sorry, I'm having trouble finding that information. Please try again.",
                  streaming: false,
                },
              ];
            }
            return prev;
          });
        } else if (data.type === "error" && data.code === "INVALID_MESSAGE") {
          setSending(false);
        }
      } catch {
        // Non-JSON or unrelated message
      }
    };

    ws.addEventListener("message", handleMessage);
    return () => ws.removeEventListener("message", handleMessage);
  }, [ws]);

  const sendMessage = () => {
    if (!ws || !input.trim() || input.length > 500 || sending) return;

    const text = input.trim();
    setMessages((prev) => [
      ...prev,
      { id: `user-${Date.now()}`, role: "user", text },
    ]);
    setInput("");
    setSending(true);

    ws.send(JSON.stringify({ action: "chat", message: text }));
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="flex flex-col h-full bg-white rounded-xl shadow-sm border border-gray-100">
      {/* Header */}
      <div className="flex items-center gap-3 p-4 border-b border-gray-100">
        <PriyaAvatar size="header" isSpeaking={isSpeaking} />
        <div>
          <p className="text-sm font-medium text-gray-900">Priya</p>
          <p className="text-xs text-gray-500">AI Tour Guide</p>
        </div>
        {isSpeaking && (
          <span className="ml-auto text-xs text-green-600 animate-pulse">Speaking...</span>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4 max-h-[400px]">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex gap-2 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            {msg.role === "priya" && <PriyaAvatar size="badge" isSpeaking={msg.streaming} />}
            <div
              className={`max-w-[80%] rounded-xl px-4 py-2 text-sm ${
                msg.role === "user"
                  ? "bg-primary-600 text-white"
                  : "bg-gray-100 text-gray-800"
              }`}
            >
              {msg.text || (msg.streaming ? (
                <span className="inline-flex gap-1">
                  <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" />
                  <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce [animation-delay:150ms]" />
                  <span className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce [animation-delay:300ms]" />
                </span>
              ) : "")}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-4 border-t border-gray-100">
        <div className="flex items-center gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value.slice(0, 500))}
            onKeyDown={handleKeyDown}
            placeholder="Ask Priya about this property..."
            disabled={sending || !ws}
            className="flex-1 px-4 py-2.5 rounded-full border border-gray-200 text-sm focus:outline-none focus:ring-2 focus:ring-primary-200 disabled:opacity-50"
            maxLength={500}
          />
          <button
            onClick={sendMessage}
            disabled={!input.trim() || sending || !ws}
            className="p-2.5 bg-primary-600 text-white rounded-full hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            aria-label="Send message"
          >
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
              <path d="M10.894 2.553a1 1 0 00-1.788 0l-7 14a1 1 0 001.169 1.409l5-1.429A1 1 0 009 15.571V11a1 1 0 112 0v4.571a1 1 0 00.725.962l5 1.428a1 1 0 001.17-1.408l-7-14z" />
            </svg>
          </button>
        </div>
        <p className="text-xs text-gray-400 mt-1 text-right">{input.length}/500</p>
      </div>
    </div>
  );
}
