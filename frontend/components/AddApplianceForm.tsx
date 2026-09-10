"use client";

import { useState } from "react";
import { RAG_ONLY_APPLIANCE_TYPES, STRUCTURED_APPLIANCE_TYPES, type NewAppliance } from "@/lib/api";

interface Props {
  onAdd: (appliance: NewAppliance) => Promise<void>;
  busy: boolean;
}

function yearsAgo(years: number): string {
  const d = new Date();
  d.setFullYear(d.getFullYear() - years);
  return d.toISOString().slice(0, 10);
}

export default function AddApplianceForm({ onAdd, busy }: Props) {
  const [applianceType, setApplianceType] = useState(STRUCTURED_APPLIANCE_TYPES[0]);
  const [brand, setBrand] = useState("Carrier");
  const [model, setModel] = useState("Infinity");
  const [installDate, setInstallDate] = useState(yearsAgo(2));

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    await onAdd({ appliance_type: applianceType, brand, model, install_date: installDate });
  }

  return (
    <form className="simulator-form" onSubmit={handleSubmit}>
      <div className="field">
        <label>Appliance type</label>
        <select value={applianceType} onChange={(e) => setApplianceType(e.target.value)}>
          <optgroup label="In structured table">
            {STRUCTURED_APPLIANCE_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </optgroup>
          <optgroup label="RAG fallback only (not in appliances.json)">
            {RAG_ONLY_APPLIANCE_TYPES.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </optgroup>
        </select>
      </div>

      <div className="field-row">
        <div className="field">
          <label>Brand</label>
          <input value={brand} onChange={(e) => setBrand(e.target.value)} required />
        </div>
        <div className="field">
          <label>Model</label>
          <input value={model} onChange={(e) => setModel(e.target.value)} required />
        </div>
      </div>

      <div className="field">
        <label>Install date</label>
        <div className="install-date-row">
          <input
            type="date"
            value={installDate}
            onChange={(e) => setInstallDate(e.target.value)}
            required
          />
          <div className="quick-dates">
            <button type="button" onClick={() => setInstallDate(yearsAgo(0.2))}>
              recent (not due)
            </button>
            <button type="button" onClick={() => setInstallDate(yearsAgo(2))}>
              2yr ago (overdue)
            </button>
            <button type="button" onClick={() => setInstallDate(yearsAgo(12))}>
              12yr ago (near EOL)
            </button>
          </div>
        </div>
      </div>

      <button type="submit" className="primary" disabled={busy}>
        Add appliance
      </button>
    </form>
  );
}
