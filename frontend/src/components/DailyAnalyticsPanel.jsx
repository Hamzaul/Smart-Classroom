import React, { useMemo } from "react";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  PointElement,
  LineElement,
  Tooltip,
  Legend,
} from "chart.js";
import { Chart } from "react-chartjs-2";

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  PointElement,
  LineElement,
  Tooltip,
  Legend
);

export default function DailyAnalyticsPanel({ days = [], summary = {}, available = false }) {
  const data = useMemo(
    () => ({
      labels: days.map((d) => d.label),
      datasets: [
        {
          type: "bar",
          label: "Average Attention (%)",
          data: days.map((d) => d.avgAttention),
          backgroundColor: "rgba(154,144,255,0.55)",
          borderRadius: 4,
          yAxisID: "y",
          order: 2,
        },
        {
          type: "line",
          label: "Low Attention Count",
          data: days.map((d) => d.lowAttentionCount),
          borderColor: "#F87171",
          backgroundColor: "#F87171",
          tension: 0.35,
          pointRadius: 3,
          yAxisID: "y1",
          order: 1,
        },
      ],
    }),
    [days]
  );

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: "top",
        align: "end",
        labels: {
          color: "#94A3B8",
          boxWidth: 10,
          font: { size: 11 },
        },
      },
      tooltip: {
        backgroundColor: "#161A2E",
        borderColor: "rgba(255,255,255,0.08)",
        borderWidth: 1,
      },
    },
    scales: {
      x: { grid: { display: false }, ticks: { color: "#64748B", font: { size: 10 } } },
      y: {
        position: "left",
        min: 0,
        max: 100,
        grid: { color: "rgba(255,255,255,0.05)" },
        ticks: { color: "#64748B", font: { size: 10 } },
      },
      y1: {
        position: "right",
        min: 0,
        grid: { display: false },
        ticks: { color: "#64748B", font: { size: 10 } },
      },
    },
  };

  const tiles = [
    { label: "Avg Attention", value: `${summary.avgAttention ?? 0}%`, color: "#9B8CFF" },
    { label: "Max Attention", value: `${summary.maxAttention ?? 0}%`, color: "#34D399" },
    { label: "Min Attention", value: `${summary.minAttention ?? 0}%`, color: "#F87171" },
    { label: "Total Alerts", value: summary.totalAlerts ?? 0, color: "#FBBF24" },
  ];

  return (
    <div className="glass-panel p-4 col-span-1 lg:col-span-2">
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-display font-semibold text-slate-100 text-[15px]">
          Daily Analytics
        </h2>
        <select className="glass-card px-2.5 py-1.5 text-xs text-slate-300 outline-none bg-base-800">
          <option>This Week</option>
          <option>This Month</option>
        </select>
      </div>

      <div className="grid grid-cols-4 gap-2 mb-4">
        {tiles.map((t) => (
          <div key={t.label} className="glass-card p-2.5 text-center">
            <p
              className="font-display font-semibold text-base"
              style={{ color: t.color }}
            >
              {t.value}
            </p>
            <p className="text-[10px] text-slate-500 mt-0.5">{t.label}</p>
          </div>
        ))}
      </div>

      <div className="h-[220px]">
        {!available ? (
          <div className="h-full flex flex-col items-center justify-center text-center gap-1 text-slate-500">
            <p className="text-sm">Database unavailable</p>
            <p className="text-xs text-slate-600">
              Firestore is not configured, so historical daily analytics can't be computed.
            </p>
          </div>
        ) : days.length === 0 ? (
          <div className="h-full flex items-center justify-center text-sm text-slate-500">
            No historical analytics available for this period.
          </div>
        ) : (
          <Chart type="bar" data={data} options={options} />
        )}
      </div>
    </div>
  );
}
