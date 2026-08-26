import React, { useState } from "react";
import { ScrollText } from "lucide-react";
import PageHeading from "../components/PageHeading.jsx";
import { usePolling } from "../hooks/usePolling.js";
import { formatTime } from "../utils/format.js";
import api from "../api/client.js";

const LEVEL_COLOR = {
  DEBUG: "text-slate-500",
  INFO: "text-accent-blue",
  WARNING: "text-accent-amber",
  ERROR: "text-accent-red",
  CRITICAL: "text-accent-red",
};

export default function LogsPage() {
  const [level, setLevel] = useState("");
  const { data: logs, loading } = usePolling(() => api.logs(300, level || undefined), 5000, [level]);

  return (
    <>
      <PageHeading
        title="Logs"
        subtitle="Live backend application logs (in-memory, last 500 entries — secrets are automatically redacted)"
      />

      <div className="glass-panel p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-display font-semibold text-slate-100 text-[15px] flex items-center gap-2">
            <ScrollText size={16} /> Application Logs {logs ? `(${logs.length})` : ""}
          </h3>
          <select
            value={level}
            onChange={(e) => setLevel(e.target.value)}
            className="glass-card px-3 py-1.5 text-sm text-slate-300 outline-none bg-base-800"
          >
            <option value="">All Levels</option>
            <option value="INFO">Info</option>
            <option value="WARNING">Warning</option>
            <option value="ERROR">Error</option>
          </select>
        </div>

        {loading && <p className="text-sm text-slate-500">Loading...</p>}
        {!loading && (!logs || logs.length === 0) && (
          <p className="text-sm text-slate-500">No log entries yet.</p>
        )}

        <div className="font-mono text-xs max-h-[600px] overflow-y-auto space-y-1">
          {(logs || []).map((entry, idx) => (
            <div key={idx} className="flex gap-2 py-1 border-b border-white/[0.03]">
              <span className="text-slate-600 shrink-0">{formatTime(entry.timestamp * 1000)}</span>
              <span className={`shrink-0 font-semibold ${LEVEL_COLOR[entry.level] || "text-slate-400"}`}>
                {entry.level}
              </span>
              <span className="text-slate-500 shrink-0">{entry.logger}</span>
              <span className="text-slate-300 break-all">{entry.message}</span>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
