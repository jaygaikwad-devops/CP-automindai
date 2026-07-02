"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import { getToken } from "@/lib/auth";

interface WebSocketMessage {
  type: string;
  lead?: Record<string, unknown>;
}

export function useWebSocket(onHotLead?: (lead: Record<string, unknown>) => void) {
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const reconnectTimeout = useRef<NodeJS.Timeout>();
  const pingInterval = useRef<NodeJS.Timeout>();

  const connect = useCallback(() => {
    const token = getToken();
    if (!token) return;

    const wsUrl = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/api/v1/dashboard/ws";
    const ws = new WebSocket(`${wsUrl}?token=${token}`);

    ws.onopen = () => {
      setConnected(true);
      // Send ping every 30 seconds
      pingInterval.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send("ping");
        }
      }, 30000);
    };

    ws.onmessage = (event) => {
      if (event.data === "pong") return;
      try {
        const message: WebSocketMessage = JSON.parse(event.data);
        if (message.type === "hot_lead_update" && message.lead && onHotLead) {
          onHotLead(message.lead);
        }
      } catch {
        // Non-JSON message, ignore
      }
    };

    ws.onclose = () => {
      setConnected(false);
      if (pingInterval.current) clearInterval(pingInterval.current);
      // Reconnect after 3 seconds
      reconnectTimeout.current = setTimeout(connect, 3000);
    };

    ws.onerror = () => {
      ws.close();
    };

    wsRef.current = ws;
  }, [onHotLead]);

  useEffect(() => {
    connect();
    return () => {
      if (wsRef.current) wsRef.current.close();
      if (reconnectTimeout.current) clearTimeout(reconnectTimeout.current);
      if (pingInterval.current) clearInterval(pingInterval.current);
    };
  }, [connect]);

  return { connected };
}
