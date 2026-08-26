import React, { useMemo } from "react";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
} from "chart.js";
import { Line } from "react-chartjs-2";

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip
);

export default function AttentionOverTimeChart({ points = [] }) {
  const data = useMemo(
    () => ({
      labels: points.map((p) => p.label),
      datasets: [
        {
          data: points.map((p) => p.value),
          borderColor: "#9B8CFF",
          backgroundColor: (ctx) => {
            const { chart } = ctx;
            const { ctx: c, chartArea } = chart;
            if (!chartArea) return "rgba(155,140,255,0.15)";
            const gradient = c.createLinearGradient(
              0,
              chartArea.top,
              0,
              chartArea.bottom
            );
            gradient.addColorStop(0, "rgba(155,140,255,0.35)");
            gradient.addColorStop(1, "rgba(155,140,255,0.0)");
            return gradient;
          },
          fill: true,
          tension: 0.4,
          pointRadius: 0,
          pointHoverRadius: 4,
          pointHoverBackgroundColor: "#9B8CFF",
          borderWidth: 2,
        },
      ],
    }),
    [points]
  );

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: "#161A2E",
        borderColor: "rgba(255,255,255,0.08)",
        borderWidth: 1,
        padding: 10,
        titleColor: "#94A3B8",
        bodyColor: "#E2E8F0",
        callbacks: {
          label: (ctx) => `${ctx.parsed.y}% attention`,
        },
      },
    },
    scales: {
      x: {
        grid: { display: false },
        ticks: { color: "#64748B", font: { size: 10 }, maxTicksLimit: 6 },
      },
      y: {
        min: 0,
        max: 100,
        grid: { color: "rgba(255,255,255,0.05)" },
        ticks: {
          color: "#64748B",
          font: { size: 10 },
          callback: (v) => `${v}%`,
        },
      },
    },
  };

  return (
    <div className="h-[180px]">
      <Line data={data} options={options} />
    </div>
  );
}
