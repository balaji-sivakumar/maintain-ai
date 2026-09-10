"use client";

import { useCallback, useEffect, useState } from "react";
import {
  API_BASE,
  addAppliance,
  checkHealth,
  deleteAppliance,
  listAppliances,
  logService,
  resetDemoData,
  seedDemoData,
  type Appliance,
  type NewAppliance,
} from "@/lib/api";
import { useLiveTrace } from "@/lib/useLiveTrace";
import ApplianceList from "@/components/ApplianceList";
import AddApplianceForm from "@/components/AddApplianceForm";
import LiveTrace from "@/components/LiveTrace";

type BackendStatus = "checking" | "ok" | "unreachable";

export default function Home() {
  const [appliances, setAppliances] = useState<Appliance[]>([]);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [backendStatus, setBackendStatus] = useState<BackendStatus>("checking");

  const trace = useLiveTrace();

  const refresh = useCallback(async () => {
    try {
      const data = await listAppliances();
      setAppliances(data);
    } catch (err) {
      setActionError((err as Error).message);
    }
  }, []);

  useEffect(() => {
    checkHealth()
      .then(() => setBackendStatus("ok"))
      .catch(() => setBackendStatus("unreachable"));
    refresh();
  }, [refresh]);

  async function withBusy(fn: () => Promise<void>) {
    setBusy(true);
    setActionError(null);
    try {
      await fn();
      await refresh();
    } catch (err) {
      setActionError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const handleAdd = (appliance: NewAppliance) => withBusy(() => addAppliance(appliance).then(() => {}));
  const handleDelete = (id: string) => withBusy(() => deleteAppliance(id).then(() => {}));
  const handleLogService = (id: string) => withBusy(() => logService(id).then(() => {}));
  const handleSeed = () => withBusy(() => seedDemoData().then(() => {}));
  const handleReset = () => withBusy(() => resetDemoData().then(() => {}));

  return (
    <div className="page">
      <header className="page-header">
        <div>
          <h1>Maintain-AI</h1>
          <p className="subtitle">Live view of the orchestrator, demo data, and a scenario simulator</p>
        </div>
        <div className="backend-status">
          <span className={`status-dot status-dot-${backendStatus}`} />
          <span className="mono">{API_BASE}</span>
        </div>
      </header>

      <main className="layout">
        <section className="panel">
          <div className="panel-header">
            <h2>Tracked appliances</h2>
            <div className="panel-actions">
              <button disabled={busy} onClick={handleSeed}>
                Seed demo data
              </button>
              <button disabled={busy} className="danger" onClick={handleReset}>
                Reset
              </button>
            </div>
          </div>

          {actionError && <p className="trace-error">{actionError}</p>}

          <ApplianceList
            appliances={appliances}
            onDelete={handleDelete}
            onLogService={handleLogService}
            busy={busy}
          />

          <h3 className="simulator-heading">Add an appliance</h3>
          <AddApplianceForm onAdd={handleAdd} busy={busy} />
        </section>

        <section className="panel">
          <LiveTrace status={trace.status} entries={trace.entries} error={trace.error} onRun={trace.run} />
        </section>
      </main>
    </div>
  );
}
