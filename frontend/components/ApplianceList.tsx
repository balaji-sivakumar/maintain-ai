"use client";

import type { Appliance } from "@/lib/api";

interface Props {
  appliances: Appliance[];
  onDelete: (id: string) => void;
  onLogService: (id: string) => void;
  busy: boolean;
}

export default function ApplianceList({ appliances, onDelete, onLogService, busy }: Props) {
  if (appliances.length === 0) {
    return <p className="empty-state">No tracked appliances. Seed demo data or add one below.</p>;
  }

  return (
    <ul className="appliance-list">
      {appliances.map((a) => (
        <li key={a.id} className="appliance-row">
          <div className="appliance-row-info">
            <code>{a.appliance_type}</code>
            <span className="appliance-row-title">
              {a.brand} {a.model}
            </span>
            <span className="appliance-row-dates">
              installed {a.install_date} · serviced{" "}
              {a.last_serviced_date ?? <span className="muted">never</span>}
            </span>
          </div>
          <div className="row-actions">
            <button
              disabled={busy}
              onClick={() => onLogService(a.id)}
              title="Mark serviced today"
              aria-label="Mark serviced today"
            >
              ✓
            </button>
            <button
              disabled={busy}
              className="danger"
              onClick={() => onDelete(a.id)}
              title="Delete"
              aria-label="Delete"
            >
              ✕
            </button>
          </div>
        </li>
      ))}
    </ul>
  );
}
