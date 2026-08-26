import React, { useState } from "react";
import { FileText, Download, Loader2 } from "lucide-react";
import PageHeading from "../components/PageHeading.jsx";
import api from "../api/client.js";

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}
function daysAgoIso(n) {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString().slice(0, 10);
}

export default function ReportsPage() {
  const [start, setStart] = useState(daysAgoIso(7));
  const [end, setEnd] = useState(todayIso());
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState(null);
  const [lastFile, setLastFile] = useState(null);

  const handleGenerate = async () => {
    setGenerating(true);
    setError(null);
    try {
      const result = await api.downloadReport(start, end);
      setLastFile(result.filename);
    } catch (err) {
      setError(err.message);
    } finally {
      setGenerating(false);
    }
  };

  return (
    <>
      <PageHeading
        title="Reports"
        subtitle="Generate a PDF attendance report for a date range"
      />

      <div className="glass-panel p-5 max-w-xl">
        <h3 className="font-display font-semibold text-slate-100 text-[15px] mb-4 flex items-center gap-2">
          <FileText size={16} /> Attendance Report
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
        </div>

        <button
          onClick={handleGenerate}
          disabled={generating}
          className="flex items-center gap-2 text-sm font-medium px-4 py-2 rounded-lg bg-violet-500/90 hover:bg-violet-500 disabled:opacity-50 text-white transition-colors"
        >
          {generating ? <Loader2 size={14} className="animate-spin" /> : <Download size={14} />}
          {generating ? "Generating..." : "Generate & Download PDF"}
        </button>

        {error && <p className="text-xs text-accent-red mt-3">{error}</p>}
        {lastFile && !error && (
          <p className="text-xs text-accent-green mt-3">Downloaded {lastFile}</p>
        )}

        <p className="text-[11px] text-slate-500 mt-4 pt-4 border-t border-white/[0.06]">
          Attendance totals come from Firestore when configured; otherwise
          only today's in-memory attendance is included, and the PDF says so
          explicitly rather than showing fabricated history.
        </p>
      </div>
    </>
  );
}
