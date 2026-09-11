"use client";

import { useCallback, useState } from "react";
import {
  listConfirmations,
  respondToConfirmation,
  type PendingConfirmation,
  type RespondResult,
} from "@/lib/api";

export function usePendingConfirmations() {
  const [confirmations, setConfirmations] = useState<PendingConfirmation[]>([]);
  const [busyIds, setBusyIds] = useState<Set<string>>(new Set());
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const data = await listConfirmations();
      setConfirmations(data);
    } catch (err) {
      setError((err as Error).message);
    }
  }, []);

  const respond = useCallback(
    async (id: string, approvedApplianceIds: string[]): Promise<RespondResult | undefined> => {
      setBusyIds((prev) => new Set(prev).add(id));
      setError(null);
      try {
        return await respondToConfirmation(id, approvedApplianceIds);
      } catch (err) {
        setError((err as Error).message);
        return undefined;
      } finally {
        setBusyIds((prev) => {
          const next = new Set(prev);
          next.delete(id);
          return next;
        });
        // Re-derive from the server rather than trusting the response shape —
        // a resumed run can immediately hit a second approval gate, and the
        // list endpoint is the one source of truth for what's still pending.
        await refresh();
      }
    },
    [refresh]
  );

  return { confirmations, busyIds, error, refresh, respond };
}
