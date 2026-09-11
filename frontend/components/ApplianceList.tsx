"use client";

import { useState } from "react";
import type { Appliance, ApplianceStatus, UpdateApplianceFields } from "@/lib/api";

interface Props {
  appliances: Appliance[];
  onDelete: (id: string) => void;
  onLogService: (id: string) => void;
  onUpdate: (id: string, fields: UpdateApplianceFields) => void;
  busy: boolean;
}

const STATUS_LABEL: Record<ApplianceStatus, string> = {
  OK: "OK",
  SERVICE_DUE: "Service due",
  REPAIR_REQUESTED: "Repair requested",
  REPLACE_REQUESTED: "Replace requested",
  UNKNOWN: "Unknown",
};

// A freshly added/seeded appliance has no status until the first check runs
// (see maintenance_status.py) — this is a display-only fallback, never a
// value the backend actually sends.
const NOT_CHECKED = "NOT_CHECKED";

function EditApplianceRow({
  appliance,
  busy,
  onSave,
  onCancel,
}: {
  appliance: Appliance;
  busy: boolean;
  onSave: (fields: UpdateApplianceFields) => void;
  onCancel: () => void;
}) {
  const [installDate, setInstallDate] = useState(appliance.install_date);
  const [servicedDate, setServicedDate] = useState(appliance.last_serviced_date ?? "");

  return (
    <li className="appliance-row appliance-row-editing">
      <div className="edit-appliance-form">
        <div className="field-row">
          <div className="field">
            <label>Install date</label>
            <input
              type="date"
              value={installDate}
              onChange={(e) => setInstallDate(e.target.value)}
            />
          </div>
          <div className="field">
            <label>Last serviced</label>
            <input
              type="date"
              value={servicedDate}
              onChange={(e) => setServicedDate(e.target.value)}
            />
          </div>
        </div>
        <div className="edit-appliance-actions">
          <button
            className="primary"
            disabled={busy}
            onClick={() =>
              onSave({
                install_date: installDate,
                last_serviced_date: servicedDate === "" ? null : servicedDate,
              })
            }
          >
            Save
          </button>
          <button disabled={busy} onClick={onCancel}>
            Cancel
          </button>
        </div>
      </div>
    </li>
  );
}

export default function ApplianceList({ appliances, onDelete, onLogService, onUpdate, busy }: Props) {
  const [editingId, setEditingId] = useState<string | null>(null);

  if (appliances.length === 0) {
    return <p className="empty-state">No tracked appliances. Seed demo data or add one below.</p>;
  }

  return (
    <ul className="appliance-list">
      {appliances.map((a) =>
        editingId === a.id ? (
          <EditApplianceRow
            key={a.id}
            appliance={a}
            busy={busy}
            onSave={(fields) => {
              onUpdate(a.id, fields);
              setEditingId(null);
            }}
            onCancel={() => setEditingId(null)}
          />
        ) : (
          <li key={a.id} className="appliance-row">
            <div className="appliance-row-info">
              <div className="appliance-row-tags">
                <code>{a.appliance_type}</code>
                <span className={`status-pill status-pill-${a.status ?? NOT_CHECKED}`}>
                  {a.status ? STATUS_LABEL[a.status] : "Not checked yet"}
                </span>
              </div>
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
                onClick={() => setEditingId(a.id)}
                title="Edit dates"
                aria-label="Edit dates"
              >
                ✎
              </button>
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
        )
      )}
    </ul>
  );
}
