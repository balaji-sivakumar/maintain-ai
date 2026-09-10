"use client";

import { useCallback, useRef, useState } from "react";
import { wsCheckUrl, type TraceEvent } from "@/lib/api";

export interface ToolEntry {
  kind: "tool";
  id: string;
  name: string;
  input: Record<string, unknown>;
  status?: string;
  output?: string;
}

export interface TextEntry {
  kind: "text";
  text: string;
}

export type TraceEntry = ToolEntry | TextEntry;

export type TraceStatus = "idle" | "connecting" | "streaming" | "done" | "error";

export function useLiveTrace() {
  const [status, setStatus] = useState<TraceStatus>("idle");
  const [entries, setEntries] = useState<TraceEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const run = useCallback(() => {
    wsRef.current?.close();
    setEntries([]);
    setError(null);
    setStatus("connecting");

    const ws = new WebSocket(wsCheckUrl());
    wsRef.current = ws;

    ws.onopen = () => setStatus("streaming");

    ws.onmessage = (event) => {
      const data: TraceEvent = JSON.parse(event.data);

      setEntries((prev) => {
        switch (data.type) {
          case "tool_call":
            return [
              ...prev,
              { kind: "tool", id: data.tool_use_id, name: data.name, input: data.input },
            ];
          case "tool_result":
            return prev.map((entry) =>
              entry.kind === "tool" && entry.id === data.tool_use_id
                ? { ...entry, status: data.status, output: data.output }
                : entry
            );
          case "text_delta": {
            const last = prev[prev.length - 1];
            if (last?.kind === "text") {
              return [...prev.slice(0, -1), { kind: "text", text: last.text + data.content }];
            }
            return [...prev, { kind: "text", text: data.content }];
          }
          default:
            return prev;
        }
      });

      if (data.type === "done") {
        setStatus("done");
        ws.close();
      } else if (data.type === "error") {
        setError(data.message);
        setStatus("error");
        ws.close();
      }
    };

    ws.onerror = () => {
      setError("WebSocket connection failed — is the backend URL reachable?");
      setStatus("error");
    };

    ws.onclose = () => {
      setStatus((current) => (current === "streaming" ? "error" : current));
    };
  }, []);

  return { status, entries, error, run };
}
