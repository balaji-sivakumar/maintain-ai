"use client";

import { useCallback, useRef, useState } from "react";
import {
  wsCheckUrl,
  type PendingMaintenanceRequest,
  type RespondResult,
  type TraceEvent,
} from "@/lib/api";

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

export interface ConfirmEntry {
  kind: "confirm";
  requests: PendingMaintenanceRequest[];
}

export type TraceEntry = ToolEntry | TextEntry | ConfirmEntry;

export type TraceStatus = "idle" | "connecting" | "streaming" | "awaiting_approval" | "done" | "error";

/** onPaused fires when the run stops at the submit_maintenance_request
 * approval gate (Day 6) — the caller uses it to refresh the Pending
 * Approvals panel, which is where the actual approve/deny happens. */
export function useLiveTrace(onPaused?: () => void) {
  const [status, setStatus] = useState<TraceStatus>("idle");
  const [entries, setEntries] = useState<TraceEntry[]>([]);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  // Tracks which confirmation_id (if any) this specific run is currently
  // paused on, so a resolution from the separate Pending Approvals panel
  // only updates this trace when it's actually the one that raised it.
  const pausedConfirmationIdRef = useRef<string | null>(null);

  const run = useCallback(() => {
    wsRef.current?.close();
    setEntries([]);
    setError(null);
    setStatus("connecting");
    pausedConfirmationIdRef.current = null;

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
          case "confirmation_required":
            return [...prev, { kind: "confirm", requests: data.requests }];
          default:
            return prev;
        }
      });

      if (data.type === "done") {
        setStatus("done");
        ws.close();
      } else if (data.type === "confirmation_required") {
        pausedConfirmationIdRef.current = data.confirmation_id;
        setStatus("awaiting_approval");
        onPaused?.();
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
  }, [onPaused]);

  /** Called after the Pending Approvals panel resolves a confirmation batch,
   * so this trace's own "Paused" card doesn't sit there stale once the
   * decisions have actually gone through. No-ops if `confirmationId` isn't
   * the one this trace is currently paused on (e.g. it belongs to a
   * different/earlier run). */
  const applyResolution = useCallback((confirmationId: string, result: RespondResult) => {
    if (pausedConfirmationIdRef.current !== confirmationId) return;

    const approvedIds = new Set(result.approved_appliance_ids ?? []);
    const stillPending = Boolean(
      result.confirmation_required && result.confirmation_id && result.requests
    );

    const resolvedEntry: TraceEntry = stillPending
      ? { kind: "confirm", requests: result.requests! }
      : { kind: "text", text: result.response ?? "Decisions submitted." };

    setEntries((prev) => {
      const lastConfirmIndex = prev.map((e) => e.kind).lastIndexOf("confirm");
      if (lastConfirmIndex === -1) return prev;
      const updated = [...prev];
      updated[lastConfirmIndex] = resolvedEntry;

      // Each submit_maintenance_request tool_call from this pause never got
      // its own tool_result — it actually executes (or gets denied) on the
      // *resumed* run, a separate agent instance this WebSocket never sees
      // — so without this those cards spin forever even after a decision.
      for (let i = lastConfirmIndex - 1; i >= 0; i--) {
        const entry = updated[i];
        if (entry.kind !== "tool" || entry.status !== undefined) continue;
        const applianceId = entry.input?.appliance_id as string | undefined;
        if (!applianceId) continue;
        const approved = approvedIds.has(applianceId);
        updated[i] = {
          ...entry,
          status: approved ? "success" : "denied",
          output: approved ? "Request submitted." : "Request denied.",
        };
      }

      return updated;
    });

    if (stillPending) {
      pausedConfirmationIdRef.current = result.confirmation_id ?? null;
      setStatus("awaiting_approval");
    } else {
      pausedConfirmationIdRef.current = null;
      setStatus("done");
    }
  }, []);

  return { status, entries, error, run, applyResolution };
}
