import React from "react";
import {
  Users,
  UserCheck,
  UserX,
  Target,
  TrendingDown,
  Moon,
  Wind,
} from "lucide-react";

const CARDS = [
  { key: "total", label: "Total Students", icon: Users, color: "#9B8CFF" },
  { key: "present", label: "Present", icon: UserCheck, color: "#34D399" },
  { key: "absent", label: "Absent", icon: UserX, color: "#F87171" },
  { key: "avgAttention", label: "Avg. Attention", icon: Target, color: "#38BDF8", suffix: "%" },
  { key: "lowAttention", label: "Low Attention", icon: TrendingDown, color: "#FB923C" },
  { key: "sleeping", label: "Sleeping", icon: Moon, color: "#A78BFA" },
  { key: "yawning", label: "Yawning", icon: Wind, color: "#FBBF24" },
];

export default function StatCardsRow({ stats = {} }) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
      {CARDS.map(({ key, label, icon: Icon, color, suffix }) => (
        <div key={key} className="glass-card p-3.5 flex flex-col gap-2">
          <div
            className="w-8 h-8 rounded-lg flex items-center justify-center"
            style={{ backgroundColor: `${color}22` }}
          >
            <Icon size={15} style={{ color }} />
          </div>
          <div>
            <p className="font-display font-semibold text-lg text-slate-100 leading-tight">
              {stats[key] ?? "--"}
              {suffix && stats[key] != null ? suffix : ""}
            </p>
            <p className="text-[11px] text-slate-500 leading-tight mt-0.5">
              {label}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
}
