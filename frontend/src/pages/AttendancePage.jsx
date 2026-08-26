import React, { useState } from "react";
import { AlertCircle } from "lucide-react";
import PageHeading from "../components/PageHeading.jsx";
import { usePolling } from "../hooks/usePolling.js";
import api from "../api/client.js";

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}
function daysAgoIso(n) {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString().slice(0, 10);
}

export default function AttendancePage() {
  const { data: todayData } = usePolling(api.attendanceToday, 8000);
  const [start, setStart] = useState(daysAgoIso(7));
  const [end, setEnd] = useState(todayIso());
  const [rangeData, setRangeData] = useState(null);
  const [rangeLoading, setRangeLoading] = useState(false);
  const [rangeError, setRangeError] = useState(null);

  const loadRange = async () => {
    setRangeLoading(true);
    setRangeError(null);
    try {
      const result = await api.attendanceRange(start, end);
      setRangeData(result);
    } catch (err) {
      setRangeError(err.message);
    } finally {
      setRangeLoading(false);
    }
  };

  const records = todayData?.records || [];
  const present = records.filter((r) => r.status === "present");
  const absent = records.filter((r) => r.status === "absent");

  return (
    <>
      <PageHeading
        title="Attendance"
        subtitle="Automatic attendance from face recognition, plus historical range queries"
      />

      <div className="glass-panel p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-display font-semibold text-slate-100 text-[15px]">
            Today ({todayData?.summary?.date || todayIso()})
          </h3>
          <div className="flex gap-4 text-xs">
            <span className="text-accent-green">{todayData?.summary?.present ?? 0} present</span>
            <span className="text-accent-red">{absent.length} absent</span>
          </div>
        </div>
        {records.length === 0 ? (
          <p className="text-sm text-slate-500">
            No attendance recorded yet today — start the camera in Live Monitoring to begin recognition.
          </p>
        ) : (
          <div className="overflow-x-auto -mx-1">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[11px] text-slate-500 uppercase tracking-wide">
                  <th className="px-3 py-2 font-medium">Name</th>
                  <th className="px-3 py-2 font-medium">Roll No.</th>
                  <th className="px-3 py-2 font-medium">Status</th>
                  <th className="px-3 py-2 font-medium">First Seen</th>
                  <th className="px-3 py-2 font-medium">Last Seen</th>
                </tr>
              </thead>
              <tbody>
                {records.map((r) => (
                  <tr key={r.student_id} className="border-t border-white/[0.04]">
                    <td className="px-3 py-2.5 text-slate-200 font-medium">{r.name}</td>
                    <td className="px-3 py-2.5 text-slate-400 font-mono text-xs">{r.roll_number}</td>
                    <td className="px-3 py-2.5">
                      <span className={r.status === "present" ? "text-accent-green" : "text-accent-red"}>
                        {r.status}
                      </span>
                    </td>
                    <td className="px-3 py-2.5 text-slate-500 text-xs font-mono">{r.first_seen?.slice(11, 16) || "-"}</td>
                    <td className="px-3 py-2.5 text-slate-500 text-xs font-mono">{r.last_seen?.slice(11, 16) || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="glass-panel p-4">
        <h3 className="font-display font-semibold text-slate-100 text-[15px] mb-3">
          Attendance History
        </h3>
        <div className="flex flex-wrap items-end gap-3 mb-4">
          <div>
            <label className="text-xs text-slate-400 block mb-1">Start Date</label>
            <input
              type="date"
              value={start}
              onChange={(e) => setStart(e.target.value)}
              className="glass-card px-3 py-1.5 text-sm text-slate-200 outline-none bg-base-800"
            />
          </div>
          <div>
            <label className="text-xs text-slate-400 block mb-1">End Date</label>
            <input
              type="date"
              value={end}
              onChange={(e) => setEnd(e.target.value)}
              className="glass-card px-3 py-1.5 text-sm text-slate-200 outline-none bg-base-800"
            />
          </div>
          <button
            onClick={loadRange}
            disabled={rangeLoading}
            className="text-sm font-medium px-4 py-2 rounded-lg bg-violet-500/90 hover:bg-violet-500 disabled:opacity-50 text-white transition-colors"
          >
            {rangeLoading ? "Loading..." : "Query Range"}
          </button>
        </div>

        {rangeError && <p className="text-sm text-accent-red">{rangeError}</p>}

        {rangeData && rangeData.storage_available === false && (
          <p className="text-sm text-accent-amber flex items-start gap-2">
            <AlertCircle size={14} className="mt-0.5 shrink-0" /> {rangeData.note}
          </p>
        )}

        {rangeData && rangeData.records && rangeData.records.length > 0 && (
          <div className="overflow-x-auto -mx-1 mt-2">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[11px] text-slate-500 uppercase tracking-wide">
                  <th className="px-3 py-2 font-medium">Date</th>
                  <th className="px-3 py-2 font-medium">Name</th>
                  <th className="px-3 py-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {rangeData.records.map((r, idx) => (
                  <tr key={idx} className="border-t border-white/[0.04]">
                    <td className="px-3 py-2.5 text-slate-400 font-mono text-xs">{r.date}</td>
                    <td className="px-3 py-2.5 text-slate-200">{r.name}</td>
                    <td className="px-3 py-2.5">
                      <span className={r.status === "present" ? "text-accent-green" : "text-accent-red"}>
                        {r.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {rangeData && rangeData.records && rangeData.records.length === 0 && rangeData.storage_available !== false && (
          <p className="text-sm text-slate-500">No records found in this range.</p>
        )}
      </div>
    </>
  );
}
