"use client";

import { useState } from "react";
import type { Appliance, PendingConfirmation } from "@/lib/api";

interface Props {
  confirmations: PendingConfirmation[];
  appliances: Appliance[];
  busyIds: Set<string>;
  error: string | null;
  onRespond: (id: string, approvedApplianceIds: string[]) => void;
}

function applianceLabel(appliances: Appliance[], applianceId: string): string {
  const appliance = appliances.find((a) => a.id === applianceId);
  return appliance ? `${appliance.brand} ${appliance.model}` : applianceId;
}

function ConfirmationCard({
  confirmation,
  appliances,
  busy,
  onRespond,
}: {
  confirmation: PendingConfirmation;
  appliances: Appliance[];
  busy: boolean;
  onRespond: (approvedApplianceIds: string[]) => void;
}) {
  // Default to everything checked — approving every recommendation is the
  // common case, and unchecking to deny specific ones is the exception.
  const [approved, setApproved] = useState<Set<string>>(
    () => new Set(confirmation.requests.map((r) => r.appliance_id))
  );

  const toggle = (applianceId: string) =>
    setApproved((prev) => {
      const next = new Set(prev);
      if (next.has(applianceId)) next.delete(applianceId);
      else next.add(applianceId);
      return next;
    });

  return (
    <div className="confirmation-card">
      {confirmation.requests.map((req) => (
        <label key={req.appliance_id} className="confirmation-row">
          <input
            type="checkbox"
            checked={approved.has(req.appliance_id)}
            disabled={busy}
            onChange={() => toggle(req.appliance_id)}
          />
          <div className="confirmation-row-body">
            <div className="confirmation-row-title">
              {applianceLabel(appliances, req.appliance_id)} —{" "}
              <span className={`action-tag action-${req.action}`}>{req.action}</span>
            </div>
            <div className="confirmation-row-notes">{req.notes}</div>
          </div>
        </label>
      ))}
      <div className="confirmation-actions">
        <button
          className="primary"
          disabled={busy}
          onClick={() => onRespond(Array.from(approved))}
        >
          Submit decisions
        </button>
      </div>
    </div>
  );
}

export default function PendingConfirmations({
  confirmations,
  appliances,
  busyIds,
  error,
  onRespond,
}: Props) {
  if (confirmations.length === 0) return null;

  return (
    <section className="panel pending-confirmations">
      <div className="panel-header">
        <h2>Pending approvals</h2>
        <span className="status-badge status-connecting">{confirmations.length} waiting</span>
      </div>
      <p className="live-trace-subtitle">
        This is the enforced part — submitting a repair or replacement request is gated behind
        human approval, so nothing is recorded as requested until you decide here. Uncheck any
        appliance you don&rsquo;t want to proceed with, then submit.
      </p>

      {error && <p className="trace-error">{error}</p>}

      {confirmations.map((c) => (
        <ConfirmationCard
          key={c.id}
          confirmation={c}
          appliances={appliances}
          busy={busyIds.has(c.id)}
          onRespond={(approvedApplianceIds) => onRespond(c.id, approvedApplianceIds)}
        />
      ))}
    </section>
  );
}
