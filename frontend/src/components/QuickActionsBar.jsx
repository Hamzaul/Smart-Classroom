import React from "react";
import {
  Video,
  CalendarCheck,
  FileText,
  LineChart,
  Bell,
  Cpu,
  Settings,
} from "lucide-react";

const ACTIONS = [
  { key: "live", label: "Monitor in real-time", title: "Live Monitoring", icon: Video, color: "#38BDF8" },
  { key: "attendance", label: "View attendance", title: "Attendance", icon: CalendarCheck, color: "#34D399" },
  { key: "reports", label: "Generate reports", title: "Reports", icon: FileText, color: "#9B8CFF" },
  { key: "analytics", label: "View analytics", title: "Analytics", icon: LineChart, color: "#A78BFA" },
  { key: "alerts", label: "View all alerts", title: "Alerts", icon: Bell, color: "#F87171" },
  { key: "devices", label: "Manage devices", title: "Devices", icon: Cpu, color: "#FB923C" },
  { key: "settings", label: "System settings", title: "Settings", icon: Settings, color: "#94A3B8" },
];

export default function QuickActionsBar({ onNavigate }) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
      {ACTIONS.map(({ key, label, title, icon: Icon, color }) => (
        <button
          key={key}
          onClick={() => onNavigate(key)}
          className="glass-card p-3.5 flex items-center gap-3 text-left hover:bg-white/[0.04] transition-colors"
        >
          <div
            className="w-9 h-9 rounded-lg flex items-center justify-center shrink-0"
            style={{ backgroundColor: `${color}22` }}
          >
            <Icon size={16} style={{ color }} />
          </div>
          <div className="min-w-0">
            <p className="text-sm font-medium text-slate-200 truncate">
              {title}
            </p>
            <p className="text-[11px] text-slate-500 truncate">{label}</p>
          </div>
        </button>
      ))}
    </div>
  );
}
