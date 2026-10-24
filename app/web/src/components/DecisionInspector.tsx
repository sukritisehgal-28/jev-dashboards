import { type Dashboard, usd } from "@/lib/api";

const p = (v: number | undefined | null) => (v === undefined || v === null ? "-" : v.toFixed(2));

export function DecisionInspector({ data }: { data: Dashboard }) {
  const { decisions, jev, spec } = data;
  const filter = new Set(spec.filters);
  return (
    <section className="space-y-3">
      <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm text-muted">
        <span>
          <b className="text-foreground">{jev.calls}</b> Jev calls: 4 typed questions per column + 1 table-level units check
        </span>
        {jev.last_run && (
          <span>
            <b className="text-foreground">{Math.round(jev.last_run.wall_ms)} ms</b> wall time, in parallel
          </span>
        )}
        <span>
          <b className="text-foreground">{usd(jev.cost_usd)}</b> for this dataset
        </span>
        <span>
          answered by <b className="text-foreground">{jev.source}</b>
        </span>
      </div>
      <div className="overflow-x-auto rounded-xl border border-line bg-card">
        <table className="w-full text-left text-sm">
          <thead className="text-xs text-muted">
            <tr className="border-b border-line">
              {["column", "sample", "type", "role", "cents? (column / table)", "filters totals?", "latency"].map((h) => (
                <th key={h} className="px-3 py-2 font-medium">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {decisions.map((d) => (
              <tr key={d.column} className="border-b border-line last:border-0 align-top">
                <td className="px-3 py-2 font-mono text-xs">{d.column}</td>
                <td className="max-w-56 truncate px-3 py-2 text-xs text-muted">{d.sample.slice(0, 3).join(" | ")}</td>
                <td className="px-3 py-2">
                  <b>{d.type}</b> <span className="text-xs text-muted">{p(d.type_p[d.type])}</span>
                </td>
                <td className="px-3 py-2">
                  {d.role} <span className="text-xs text-muted">{p(d.role_p[d.role])}</span>
                </td>
                <td className="px-3 py-2 text-xs">
                  {d.type === "money" ? `${p(d.cents)} / ${p(d.cents_table)}` : <span className="text-muted">-</span>}
                </td>
                <td className="px-3 py-2 text-xs">
                  {filter.has(d.column) ? <b>yes</b> : <span className="text-muted">no</span>}{" "}
                  <span className="text-muted">{p(d.filter)}</span>
                </td>
                <td className="px-3 py-2 text-xs text-muted">{Math.round(d.latency_ms)} ms</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-muted">
        Numbers are the model&apos;s probabilities for this dataset. Decisions it is unsure about are flagged for you to confirm.
      </p>
    </section>
  );
}
