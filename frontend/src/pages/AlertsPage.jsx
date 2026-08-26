import React, { useMemo, useState } from "react";
import { AlertTriangle, Info, AlertOctagon } from "lucide-react";
import PageHeading from "../components/PageHeading.jsx";
import { usePolling } from "../hooks/usePolling.js";
import { formatTime } from "../utils/format.js";
import api from "../api/client.js";

const SEVERITY_ICON = { info: Info, warning: AlertTriangle, critical: AlertOctagon };
const SEVERITY_COLOR = {
  info: "text-accent-blue",
  warning: "text-accent-amber",
  critical: "text-accent-red",
};

export default function AlertsPage() {
  const { data: alerts, loading } = usePolling(() => api.recentAlerts(100), 6000);
  const [severityFilter, setSeverityFilter] = useState("all");

  const filtered = useMemo(() => {
    const list = alerts || [];
    if (severityFilter === "all") return list;
    return list.filter((a) => a.severity === severityFilter);
  }, [alerts, severityFilter]);

  const counts = useMemo(() => {
    const list = alerts || [];
    return {
      critical: list.filter((a) => a.severity === "critical").length,
      warning: list.filter((a) => a.severity === "warning").length,
      info: list.filter((a) => a.severity === "info").length,
    };
  }, [alerts]);

  return (
    <>
      <PageHeading
        title="Alerts"
        subtitle="All classroom alerts — sleeping, low attention, yawning, and unrecognized faces"
      />

      <div className="grid grid-cols-3 gap-4">
        {["critical", "warning", "info"].map((sev) => {
          const Icon = SEVERITY_ICON[sev];
          return (
            <div key={sev} className="glass-panel p-4 flex items-center gap-3">
              <div className={`p-2 rounded-lg bg-white/5 ${SEVERITY_COLOR[sev]}`}>
                <Icon size={18} />
              </div>
              <div>
                <p className="font-display font-semibold text-xl text-slate-100">{counts[sev]}</p>
                <p className="text-xs text-slate-500 capitalize">{sev}</p>
              </div>
            </div>
          );
        })}
      </div>

      <div className="glass-panel p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-display font-semibold text-slate-100 text-[15px]">
            All Alerts {alerts ? `(${filtered.length})` : ""}
          </h3>
          <select
            value={severityFilter}
            onChange={(e) => setSeverityFilter(e.target.value)}
            className="glass-card px-3 py-1.5 text-sm text-slate-300 outline-none bg-base-800"
          >
            <option value="all">All Severities</option>
            <option value="critical">Critical</option>
            <option value="warning">Warning</option>
            <option value="info">Info</option>
          </select>
        </div>

        {loading && <p className="text-sm text-slate-500">Loading...</p>}
        {!loading && filtered.length === 0 && (
          <p className="text-sm text-slate-500">No alerts to show.</p>
        )}

        <ul className="divide-y divide-white/[0.04]">
          {filtered.map((a, idx) => {
            const Icon = SEVERITY_ICON[a.severity] || Info;
            return (
              <li key={idx} className="flex items-start gap-3 py-2.5">
                <Icon size={15} className={`mt-0.5 shrink-0 ${SEVERITY_COLOR[a.severity] || "text-slate-400"}`} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm text-slate-200">{a.message}</p>
                  <p className="text-[11px] text-slate-500 mt-0.5 capitalize">{a.alert_type?.replace(/_/g, " ")}</p>
                </div>
                <span className="text-[11px] text-slate-500 font-mono shrink-0">{formatTime(a.timestamp)}</span>
              </li>
            );
          })}
        </ul>
      </div>
    </>
  );
}
