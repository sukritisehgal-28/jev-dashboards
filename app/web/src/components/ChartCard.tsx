"use client";

import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { type Chart, fmt } from "@/lib/api";

// SVG presentation attributes don't resolve CSS variables, so read the theme tokens once on the client.
function useTheme() {
  const [t, setT] = useState({ accent: "#2f6fde", muted: "#6b6b66", line: "#e4e3de" });
  useEffect(() => {
    const read = () => {
      const s = getComputedStyle(document.documentElement);
      setT({ accent: s.getPropertyValue("--accent").trim(), muted: s.getPropertyValue("--muted").trim(), line: s.getPropertyValue("--line").trim() });
    };
    read();
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    mq.addEventListener("change", read);
    return () => mq.removeEventListener("change", read);
  }, []);
  return t;
}

export function ChartCard({ chart }: { chart: Chart }) {
  const theme = useTheme();
  const axis = { stroke: theme.muted, fontSize: 11, tickLine: false, axisLine: false } as const;
  const data = chart.points.map((p) => ({ x: p.x, y: p.y }));
  const tick = (v: number) => fmt(v, chart.format === "percent" ? "number" : chart.format);
  const tooltip = (
    <Tooltip
      formatter={(v: number) => [fmt(v, chart.format), chart.title.split(" by ")[0]]}
      contentStyle={{ background: "var(--card)", border: "1px solid var(--line)", borderRadius: 8, fontSize: 12 }}
      labelStyle={{ color: "var(--muted)" }}
      cursor={{ fill: theme.line, opacity: 0.4 }}
    />
  );
  return (
    <div className="rounded-xl border border-line bg-card p-4">
      <h3 className="mb-3 text-sm font-medium text-muted">{chart.title}</h3>
      <div className="h-56">
        <ResponsiveContainer width="100%" height="100%">
          {chart.kind === "line" ? (
            <LineChart data={data} margin={{ left: 8, right: 8, top: 4 }}>
              <CartesianGrid stroke={theme.line} vertical={false} />
              <XAxis dataKey="x" {...axis} minTickGap={24} />
              <YAxis {...axis} tickFormatter={tick} width={64} />
              {tooltip}
              <Line type="monotone" dataKey="y" stroke={theme.accent} strokeWidth={2} dot={false} isAnimationActive={false} />
            </LineChart>
          ) : (
            <BarChart data={data} margin={{ left: 8, right: 8, top: 4 }}>
              <CartesianGrid stroke={theme.line} vertical={false} />
              <XAxis dataKey="x" {...axis} interval={0} />
              <YAxis {...axis} tickFormatter={tick} width={64} />
              {tooltip}
              <Bar dataKey="y" fill={theme.accent} radius={[4, 4, 0, 0]} isAnimationActive={false} />
            </BarChart>
          )}
        </ResponsiveContainer>
      </div>
    </div>
  );
}
