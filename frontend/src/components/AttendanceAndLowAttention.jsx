import React, { useMemo } from "react";
import { Chart as ChartJS, ArcElement, Tooltip } from "chart.js";
import { Doughnut } from "react-chartjs-2";

ChartJS.register(ArcElement, Tooltip);

export function AttendanceSummaryCard({ present = 0, total = 0 }) {
  const absent = Math.max(total - present, 0);
  const pct = total > 0 ? Math.round((present / total) * 100) : 0;

  const data = useMemo(
    () => ({
      labels: ["Present", "Absent"],
      datasets: [
        {
          data: [present, absent],
          backgroundColor: ["#34D399", "#F87171"],
          borderColor: "#161A2E",
          borderWidth: 4,
        },
      ],
    }),
    [present, absent]
  );

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    cutout: "72%",
    plugins: { legend: { display: false }, tooltip: { enabled: true } },
  };

  return (
    <div className="glass-panel p-4">
      <h2 className="font-display font-semibold text-slate-100 text-[15px] mb-3">
        Attendance Summary (Today)
      </h2>
      <div className="flex items-center gap-5">
        <div className="relative w-[120px] h-[120px] shrink-0">
          <Doughnut data={data} options={options} />
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="font-display font-bold text-xl text-slate-100">
              {pct}%
            </span>
            <span className="text-[10px] text-slate-500">Present</span>
          </div>
        </div>
        <ul className="space-y-2 text-sm">
          <li className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-accent-green" />
            <span className="text-slate-400">Present</span>
            <span className="ml-auto font-semibold text-slate-100">
              {present}
            </span>
          </li>
          <li className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-accent-red" />
            <span className="text-slate-400">Absent</span>
            <span className="ml-auto font-semibold text-slate-100">
              {absent}
            </span>
          </li>
          <li className="flex items-center gap-2 pt-1 border-t border-white/[0.06] mt-1">
            <span className="text-slate-500">Total</span>
            <span className="ml-auto font-semibold text-slate-200">
              {total}
            </span>
          </li>
        </ul>
      </div>
    </div>
  );
}

export function LowAttentionStudentsCard({ students = [] }) {
  return (
    <div className="glass-panel p-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-display font-semibold text-slate-100 text-[15px]">
          Low Attention Students
        </h2>
        <button className="text-xs text-violet-400 hover:text-violet-300">
          View All
        </button>
      </div>
      {students.length === 0 ? (
        <p className="text-sm text-slate-500 py-4 text-center">
          No students currently below the attention threshold.
        </p>
      ) : (
        <ul className="space-y-2.5">
          {students.map((s) => (
            <li key={s.student_id} className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-gradient-to-br from-accent-orange/60 to-accent-red/60 flex items-center justify-center text-xs font-semibold text-white shrink-0">
                {s.name?.[0] ?? "?"}
              </div>
              <span className="text-sm text-slate-200 flex-1">{s.name}</span>
              <span className="font-semibold text-accent-red text-sm">
                {Math.round(s.attention_score)}%
              </span>
              <span className="text-[11px] text-slate-500 capitalize w-14 text-right">
                {s.attention_level?.replace("_", " ")}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
