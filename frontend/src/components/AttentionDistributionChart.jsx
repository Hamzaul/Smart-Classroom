import React, { useMemo } from "react";
import { Chart as ChartJS, ArcElement, Tooltip } from "chart.js";
import { Doughnut } from "react-chartjs-2";

ChartJS.register(ArcElement, Tooltip);

const LEVELS = [
  { key: "excellent", label: "Excellent (80-100%)", color: "#34D399" },
  { key: "high", label: "High (60-80%)", color: "#38BDF8" },
  { key: "medium", label: "Medium (40-60%)", color: "#FBBF24" },
  { key: "low", label: "Low (20-40%)", color: "#FB923C" },
  { key: "very_low", label: "Very Low (0-20%)", color: "#F87171" },
];

export default function AttentionDistributionChart({ counts = {} }) {
  const values = LEVELS.map((l) => counts[l.key] || 0);
  const total = values.reduce((a, b) => a + b, 0) || 1;

  const data = useMemo(
    () => ({
      labels: LEVELS.map((l) => l.label),
      datasets: [
        {
          data: values,
          backgroundColor: LEVELS.map((l) => l.color),
          borderColor: "#161A2E",
          borderWidth: 3,
          hoverOffset: 6,
        },
      ],
    }),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [JSON.stringify(counts)]
  );

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    cutout: "68%",
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: "#161A2E",
        borderColor: "rgba(255,255,255,0.08)",
        borderWidth: 1,
        padding: 10,
        titleColor: "#94A3B8",
        bodyColor: "#E2E8F0",
      },
    },
  };

  return (
    <div className="flex items-center gap-4">
      <div className="w-[110px] h-[110px] shrink-0">
        <Doughnut data={data} options={options} />
      </div>
      <ul className="space-y-1.5 flex-1">
        {LEVELS.map((l, i) => (
          <li
            key={l.key}
            className="flex items-center justify-between text-[11px]"
          >
            <span className="flex items-center gap-1.5 text-slate-400">
              <span
                className="w-2 h-2 rounded-full"
                style={{ backgroundColor: l.color }}
              />
              {l.label}
            </span>
            <span className="font-medium text-slate-200">
              {Math.round((values[i] / total) * 100)}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
