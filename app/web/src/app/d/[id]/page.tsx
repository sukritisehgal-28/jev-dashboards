"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { ChartCard } from "@/components/ChartCard";
import { DecisionInspector } from "@/components/DecisionInspector";
import { api, type Dashboard, fmt } from "@/lib/api";

const LIVE_INTERVAL_MS = 30_000;

export default function DashboardPage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [data, setData] = useState<Dashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  // ?inspect=1 opens the Decision Inspector, so a link can point straight at Jev's decisions.
  const [showInspector, setShowInspector] = useState(
    () => typeof window !== "undefined" && new URLSearchParams(window.location.search).get("inspect") === "1",
  );
  const [refreshedAt, setRefreshedAt] = useState<Date | null>(null);

  const load = useCallback(
    (refresh = false) =>
      api
        .get(id, refresh)
        .then((d) => {
          setData(d);
          setRefreshedAt(new Date());
          setError(null);
        })
        .catch((e) => setError((e as Error).message)),
    [id],
  );

  useEffect(() => {
    load();
  }, [load]);

  const live = data?.dataset.source.kind === "sheets";
  useEffect(() => {
    if (!live) return;
    const t = setInterval(() => load(true), LIVE_INTERVAL_MS);
    return () => clearInterval(t);
  }, [live, load]);

  if (error && !data) return <p className="rounded-lg border border-warn bg-warn-bg px-3 py-2 text-sm">{error}</p>;
  if (!data) return <p className="text-muted">Loading…</p>;

  const { dataset, spec } = data;
  const pending = spec.units.filter((u) => u.status === "needs_confirmation");

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link href="/" className="text-xs text-muted hover:text-foreground">
            ← All dashboards
          </Link>
          <h1 className="text-2xl font-semibold">{dataset.name}</h1>
          <p className="text-sm text-muted">
            {dataset.rows.toLocaleString()} rows × {dataset.columns} columns
            {spec.time_column && (
              <>
                {" "}
                · time from <code>{spec.time_column}</code>
              </>
            )}
            {spec.filters.length > 0 && (
              <>
                {" "}
                · counting rows where <code>{spec.filters.join(", ")}</code> is true
              </>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2 text-sm">
          {live && (
            <span className="flex items-center gap-1.5 rounded-full border border-line px-2.5 py-1 text-xs">
              <span className="h-2 w-2 animate-pulse rounded-full bg-good" /> Live · {refreshedAt?.toLocaleTimeString()}
            </span>
          )}
          <button onClick={() => setShowInspector((s) => !s)} className="rounded-lg border border-line px-3 py-1.5 hover:border-accent">
            {showInspector ? "Hide" : "Show"} Jev decisions
          </button>
          <button
            onClick={async () => {
              if (confirm(`Delete "${dataset.name}"?`)) {
                await api.remove(dataset.id);
                router.push("/");
              }
            }}
            className="rounded-lg border border-line px-3 py-1.5 text-muted hover:border-warn hover:text-warn"
          >
            Delete
          </button>
        </div>
      </div>

      {pending.map((u) => (
        <div key={u.column} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-warn bg-warn-bg px-4 py-3 text-sm">
          <span>
            <b>Jev is unsure (p = {(u.p_table ?? u.p_column).toFixed(2)})</b>: is <code>{u.column}</code> written in cents? Showing it{" "}
            {u.divide ? "divided by 100" : "as is"} for now.
          </span>
          <span className="flex gap-2">
            <button onClick={() => api.confirm(dataset.id, u.column, true).then(setData)} className="rounded-md bg-accent px-3 py-1 text-white">
              Yes, cents
            </button>
            <button onClick={() => api.confirm(dataset.id, u.column, false).then(setData)} className="rounded-md border border-line px-3 py-1">
              No
            </button>
          </span>
        </div>
      ))}

      {showInspector && <DecisionInspector data={data} />}

      <section className="grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-4">
        {spec.kpis.map((k) => (
          <div key={k.label} className="rounded-xl border border-line bg-card px-4 py-3">
            <div className="text-xs text-muted">{k.label}</div>
            <div className="mt-0.5 text-2xl font-semibold">{fmt(k.value, k.format)}</div>
            {k.note && <div className="text-xs text-muted">{k.note}</div>}
          </div>
        ))}
      </section>

      <section className="grid gap-3 lg:grid-cols-2">
        {spec.charts.map((c) => (
          <ChartCard key={c.id} chart={c} />
        ))}
      </section>

      {error && <p className="text-xs text-warn">Last refresh failed: {error}</p>}
    </div>
  );
}
