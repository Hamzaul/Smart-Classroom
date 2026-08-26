import React, { useMemo, useState } from "react";
import { Search } from "lucide-react";
import { levelBadgeClass, formatLevel, formatTime } from "../utils/format.js";

export default function StudentAttentionList({ students = [] }) {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("all");

  const filtered = useMemo(() => {
    return students.filter((s) => {
      const matchesQuery = s.name?.toLowerCase().includes(query.toLowerCase());
      const matchesFilter =
        filter === "all" ||
        (s.attention_level || "").toLowerCase() === filter;
      return matchesQuery && matchesFilter;
    });
  }, [students, query, filter]);

  return (
    <div className="glass-panel p-4 col-span-1 lg:col-span-2">
      <div className="flex items-center justify-between mb-3">
        <h2 className="font-display font-semibold text-slate-100 text-[15px]">
          Student Attention List
        </h2>
      </div>

      <div className="flex items-center gap-2 mb-3">
        <div className="flex items-center gap-2 glass-card px-3 py-2 flex-1 text-slate-400">
          <Search size={14} />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search student..."
            className="bg-transparent outline-none text-sm placeholder:text-slate-500 flex-1 text-slate-200"
          />
        </div>
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="glass-card px-3 py-2 text-sm text-slate-300 outline-none bg-base-800"
        >
          <option value="all">All</option>
          <option value="excellent">Excellent</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
          <option value="very_low">Very Low</option>
        </select>
      </div>

      <div className="overflow-x-auto -mx-1">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[11px] text-slate-500 uppercase tracking-wide">
              <th className="px-3 py-2 font-medium">#</th>
              <th className="px-3 py-2 font-medium">Student Name</th>
              <th className="px-3 py-2 font-medium">Attention</th>
              <th className="px-3 py-2 font-medium">Status</th>
              <th className="px-3 py-2 font-medium">Last Updated</th>
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 && (
              <tr>
                <td colSpan={5} className="px-3 py-6 text-center text-slate-500 text-sm">
                  No students match this view yet.
                </td>
              </tr>
            )}
            {filtered.map((s, idx) => (
              <tr
                key={s.student_id || idx}
                className="border-t border-white/[0.04] hover:bg-white/[0.02] transition-colors"
              >
                <td className="px-3 py-2.5 text-slate-500">{idx + 1}</td>
                <td className="px-3 py-2.5 text-slate-200 font-medium">
                  {s.name || "Unknown"}
                </td>
                <td className="px-3 py-2.5">
                  <span className="font-display font-semibold text-slate-100">
                    {Math.round(s.attention_score ?? 0)}%
                  </span>
                </td>
                <td className="px-3 py-2.5">
                  <span className={levelBadgeClass(s.attention_level)}>
                    {formatLevel(s.attention_level)}
                  </span>
                </td>
                <td className="px-3 py-2.5 text-slate-500 font-mono text-xs">
                  {formatTime(s.timestamp)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
