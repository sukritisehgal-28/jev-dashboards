// Types mirror app/backend/jevdash/api.py and spec.py.

export type Format = "money" | "number" | "percent";

export interface Kpi {
  label: string;
  value: number | null;
  format: Format;
  note: string;
  column: string | null;
}

export interface Chart {
  id: string;
  kind: "line" | "bar";
  title: string;
  format: Format;
  points: { x: string; y: number | null }[];
}

export interface UnitDecision {
  column: string;
  divide: boolean;
  status: "decided" | "needs_confirmation" | "confirmed";
  p_column: number;
  p_table: number | null;
}

export interface Decision {
  column: string;
  sample: string[];
  source: string;
  type: string;
  type_p: Record<string, number>;
  role: string;
  role_p: Record<string, number>;
  cents: number;
  cents_table?: number;
  filter: number;
  latency_ms: number;
  input_tokens: number;
  cost_usd: number;
}

export interface DatasetSummary {
  id: string;
  name: string;
  source: { kind: "upload" | "sheets" | "sample"; url?: string; filename?: string };
  updated_at: string;
}

export interface Dashboard {
  dataset: DatasetSummary & { rows: number; columns: number };
  spec: {
    time_column: string | null;
    filters: string[];
    primary: string | null;
    units: UnitDecision[];
    kpis: Kpi[];
    charts: Chart[];
  };
  decisions: Decision[];
  jev: { calls: number; cost_usd: number; source: string | null; last_run: { at: string; columns: number; wall_ms: number } | null };
  budget: { spent_usd: number; cap_usd: number };
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(path, { cache: "no-store", ...init });
  if (!r.ok) {
    let detail = r.statusText;
    try {
      detail = (await r.json()).detail ?? detail;
    } catch {}
    throw new Error(detail);
  }
  return r.json();
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  list: () => call<DatasetSummary[]>("/api/datasets"),
  budget: () => call<{ spent_usd: number; cap_usd: number }>("/api/budget"),
  health: () => call<{ ok: boolean; mock: boolean }>("/api/health"),
  get: (id: string, refresh = false) => call<Dashboard>(`/api/datasets/${id}${refresh ? "?refresh=true" : ""}`),
  sample: () => call<Dashboard>("/api/datasets/sample", { method: "POST" }),
  sheets: (url: string, name?: string) => call<Dashboard>("/api/datasets/sheets", json({ url, name })),
  upload: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return call<Dashboard>("/api/datasets/upload", { method: "POST", body: form });
  },
  confirm: (id: string, column: string, cents: boolean) => call<Dashboard>(`/api/datasets/${id}/confirm`, json({ column, cents })),
  remove: (id: string) => call<{ deleted: string }>(`/api/datasets/${id}`, { method: "DELETE" }),
};

export function fmt(v: number | null, format: Format): string {
  if (v === null || Number.isNaN(v)) return "-";
  if (format === "money") return v.toLocaleString(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 });
  if (format === "percent") return `${v.toFixed(1)}%`;
  return v.toLocaleString(undefined, { maximumFractionDigits: Math.abs(v) < 10 ? 2 : 0 });
}

export const usd = (v: number) => `$${v < 0.01 ? v.toFixed(5) : v.toFixed(4)}`;
