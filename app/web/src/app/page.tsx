"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { api, type DatasetSummary, usd } from "@/lib/api";

const SOURCE_LABEL = { upload: "Upload", sheets: "Google Sheets · live", sample: "Sample" } as const;

export default function ConnectPage() {
  const router = useRouter();
  const [datasets, setDatasets] = useState<DatasetSummary[]>([]);
  const [budget, setBudget] = useState<{ spent_usd: number; cap_usd: number } | null>(null);
  const [mock, setMock] = useState(false);
  const [sheetUrl, setSheetUrl] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.list().then(setDatasets).catch(() => setError("Backend not reachable. Start it with: uvicorn jevdash.api:app --port 8000"));
    api.budget().then(setBudget).catch(() => {});
    api.health().then((h) => setMock(h.mock)).catch(() => {});
  }, []);

  async function run(label: string, fn: () => Promise<{ dataset: { id: string } }>) {
    setBusy(label);
    setError(null);
    try {
      const d = await fn();
      router.push(`/d/${d.dataset.id}`);
    } catch (e) {
      setError((e as Error).message);
      setBusy(null);
    }
  }

  return (
    <div className="space-y-8">
      <section>
        <h1 className="text-2xl font-semibold">Connect your data</h1>
        <p className="mt-1 text-muted">
          Jev reads each column and decides what it means: money, dates, IDs, cents or dollars. Code does the maths and draws the
          dashboard.
        </p>
        {mock && (
          <p className="mt-2 inline-block rounded-md border border-warn bg-warn-bg px-2 py-1 text-xs">
            Mock mode: decisions come from the free rules tier, not Jev.
          </p>
        )}
      </section>

      <section className="grid gap-4 md:grid-cols-3">
        <div className="rounded-xl border border-line bg-card p-5">
          <h2 className="font-medium">Upload a file</h2>
          <p className="mt-1 text-sm text-muted">CSV or JSON, up to 20 MB and 60 columns.</p>
          <label className="mt-4 block cursor-pointer rounded-lg border border-dashed border-line px-3 py-6 text-center text-sm hover:border-accent">
            {busy === "upload" ? "Jev is reading your columns…" : "Choose a file"}
            <input
              type="file"
              accept=".csv,.json,text/csv,application/json"
              className="hidden"
              disabled={!!busy}
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) run("upload", () => api.upload(f));
              }}
            />
          </label>
        </div>

        <form
          className="rounded-xl border border-line bg-card p-5"
          onSubmit={(e) => {
            e.preventDefault();
            if (sheetUrl) run("sheets", () => api.sheets(sheetUrl));
          }}
        >
          <h2 className="font-medium">Google Sheets (live)</h2>
          <p className="mt-1 text-sm text-muted">Share as “Anyone with the link can view”. Refreshes every 30 s at no Jev cost.</p>
          <input
            value={sheetUrl}
            onChange={(e) => setSheetUrl(e.target.value)}
            placeholder="https://docs.google.com/spreadsheets/d/…"
            className="mt-4 w-full rounded-lg border border-line bg-transparent px-3 py-2 text-sm outline-none focus:border-accent"
          />
          <button
            disabled={!!busy || !sheetUrl}
            className="mt-3 w-full rounded-lg bg-accent px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
          >
            {busy === "sheets" ? "Reading sheet…" : "Connect sheet"}
          </button>
        </form>

        <div className="rounded-xl border border-line bg-card p-5">
          <h2 className="font-medium">Try the sample</h2>
          <p className="mt-1 text-sm text-muted">
            6,432 Stripe-style payments with amounts in cents, Unix timestamps and ✓ flags.
          </p>
          <button
            disabled={!!busy}
            onClick={() => run("sample", api.sample)}
            className="mt-4 w-full rounded-lg border border-accent px-3 py-2 text-sm font-medium text-accent disabled:opacity-50"
          >
            {busy === "sample" ? "Jev is reading 15 columns…" : "Load sample data"}
          </button>
        </div>
      </section>

      {error && <p className="rounded-lg border border-warn bg-warn-bg px-3 py-2 text-sm">{error}</p>}

      <section>
        <div className="flex items-baseline justify-between">
          <h2 className="font-medium">Your dashboards</h2>
          {budget && (
            <span className="text-xs text-muted">
              Jev spend {usd(budget.spent_usd)} of {usd(budget.cap_usd)} cap
            </span>
          )}
        </div>
        {datasets.length === 0 ? (
          <p className="mt-2 text-sm text-muted">None yet.</p>
        ) : (
          <ul className="mt-3 divide-y divide-line rounded-xl border border-line bg-card">
            {datasets.map((d) => (
              <li key={d.id}>
                <Link href={`/d/${d.id}`} className="flex items-center justify-between px-4 py-3 hover:bg-background">
                  <span>{d.name}</span>
                  <span className="text-xs text-muted">
                    {SOURCE_LABEL[d.source.kind]} · {new Date(d.updated_at).toLocaleString()}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
