import React from "react";
import { Moon, Wind, TrendingDown, UserX, AlertTriangle } from "lucide-react";
import { formatTime } from "../utils/format.js";

const ICONS = {
  sleeping: Moon,
  yawning: Wind,
  low_attention: TrendingDown,
  face_not_detected: UserX,
  unrecognized_person: AlertTriangle,
};

const SEVERITY_COLOR = {
  info: "#38BDF8",
  warning: "#FBBF24",
  critical: "#F87171",
};

export default function RecentAlertsPanel({ alerts = [] }) {
  return (
    <div className="glass-panel p-4">
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-display font-semibold text-slate-100 text-[15px]">
          Recent Alerts
        </h2>
        <button className="text-xs text-violet-400 hover:text-violet-300">
          View All
        </button>
      </div>

      {alerts.length === 0 ? (
        <p className="text-sm text-slate-500 py-4 text-center">
          No alerts yet — the classroom is running smoothly.
        </p>
      ) : (
        <ul className="space-y-3 max-h-[280px] overflow-y-auto pr-1">
          {alerts.map((a) => {
            const Icon = ICONS[a.alert_type] || AlertTriangle;
            const color = SEVERITY_COLOR[a.severity] || "#94A3B8";
            return (
              <li key={a.alert_id} className="flex items-start gap-3">
                <div
                  className="w-7 h-7 rounded-lg flex items-center justify-center shrink-0 mt-0.5"
                  style={{ backgroundColor: `${color}22` }}
                >
                  <Icon size={14} style={{ color }} />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-slate-180 truncate">
                    {a.message}
                  </p>
                </div>
                <span className="text-[11px] text-slate-500 font-mono shrink-0">
                  {formatTime(a.created_at)}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
