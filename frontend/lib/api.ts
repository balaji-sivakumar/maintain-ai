export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE?.replace(/\/$/, "") ?? "http://localhost:8000";

export function wsCheckUrl(): string {
  const wsBase = API_BASE.replace(/^http/, "ws");
  return `${wsBase}/ws/check`;
}

export interface Appliance {
  id: string;
  appliance_type: string;
  brand: string;
  model: string;
  install_date: string;
  last_serviced_date?: string;
}

export interface NewAppliance {
  appliance_type: string;
  brand: string;
  model: string;
  install_date: string;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`${init?.method ?? "GET"} ${path} failed: ${res.status} ${body}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export function listAppliances(): Promise<Appliance[]> {
  return request<Appliance[]>("/appliances");
}

export function addAppliance(appliance: NewAppliance): Promise<{ appliance_id: string }> {
  return request("/appliances", { method: "POST", body: JSON.stringify(appliance) });
}

export function deleteAppliance(id: string): Promise<{ appliance_id: string; deleted: boolean }> {
  return request(`/appliances/${id}`, { method: "DELETE" });
}

export function logService(id: string): Promise<{ appliance_id: string; last_serviced_date: string }> {
  return request(`/appliances/${id}/service`, { method: "POST", body: JSON.stringify({}) });
}

export function seedDemoData(): Promise<{ seeded: Appliance[] }> {
  return request("/demo/seed", { method: "POST" });
}

export function resetDemoData(): Promise<{ deleted: number }> {
  return request("/demo/reset", { method: "POST" });
}

export function checkHealth(): Promise<{ status: string }> {
  return request("/health");
}

// --- Live tool trace -------------------------------------------------------

export type TraceEvent =
  | { type: "tool_call"; tool_use_id: string; name: string; input: Record<string, unknown> }
  | { type: "tool_result"; tool_use_id: string; name: string; status: string; output: string }
  | { type: "text_delta"; content: string }
  | { type: "done"; final_text: string }
  | { type: "error"; message: string };

/** A handful of appliance types not in the seeded reference table, so
 * picking one from the UI visibly exercises the Day 4 RAG fallback. */
export const RAG_ONLY_APPLIANCE_TYPES = ["ev_charger", "wine_cooler", "pool_pump"];

export const STRUCTURED_APPLIANCE_TYPES = [
  "hvac_system",
  "hvac_filter",
  "water_heater_tank",
  "water_heater_tankless",
  "smoke_detector",
  "co_detector",
  "refrigerator",
  "dishwasher",
  "garbage_disposal",
  "washing_machine",
  "dryer",
  "water_softener",
  "sump_pump",
  "garage_door_opener",
  "water_filtration_system",
  "gutters",
  "roof",
  "water_pressure_regulator",
  "furnace_humidifier",
  "range_oven",
];
