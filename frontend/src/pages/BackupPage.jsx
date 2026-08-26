import React, { useState } from "react";
import { DatabaseBackup, Save, RotateCcw, Loader2, AlertTriangle } from "lucide-react";
import PageHeading from "../components/PageHeading.jsx";
import { usePolling } from "../hooks/usePolling.js";
import { formatTime } from "../utils/format.js";
import api from "../api/client.js";

export default function BackupPage() {
  const { data: backups, loading, refetch } = usePolling(api.listBackups, 10000);
  const [creating, setCreating] = useState(false);
  const [restoringFile, setRestoringFile] = useState(null);
  const [message, setMessage] = useState(null);
  const [error, setError] = useState(null);

  const handleCreate = async () => {
    setCreating(true);
    setError(null);
    setMessage(null);
    try {
      const result = await api.createBackup();
      setMessage(`Backup created: ${result.filename}`);
      refetch();
    } catch (err) {
      setError(err.message);
    } finally {
      setCreating(false);
    }
  };

  const handleRestore = async (filename) => {
    if (!window.confirm(`Restore attendance data from "${filename}"? This adds/updates attendance records but won't delete anything.`)) {
      return;
    }
    setRestoringFile(filename);
    setError(null);
    setMessage(null);
    try {
      const result = await api.restoreBackup(filename);
      setMessage(`Restored ${result.restored_attendance_records} attendance record(s) from ${filename}.`);
    } catch (err) {
      setError(err.message);
    } finally {
      setRestoringFile(null);
    }
  };

  return (
    <>
      <PageHeading
        title="Backup"
        subtitle="Snapshot and restore students, attendance, and alerts"
        action={
          <button
            onClick={handleCreate}
            disabled={creating}
            className="flex items-center gap-2 text-sm font-medium px-4 py-2 rounded-lg bg-violet-500/90 hover:bg-violet-500 disabled:opacity-50 text-white transition-colors"
          >
            {creating ? <Loader2 size={14} className="animate-spin" /> : <Save size={14} />}
            {creating ? "Creating..." : "Create Backup"}
          </button>
        }
      />

      {message && <p className="text-sm text-accent-green">{message}</p>}
      {error && <p className="text-sm text-accent-red">{error}</p>}

      <div className="glass-panel p-3.5 flex items-start gap-2.5">
        <AlertTriangle size={15} className="text-accent-amber mt-0.5 shrink-0" />
        <p className="text-xs text-slate-400">
          Restoring only adds or updates attendance records found in the
          backup file — it never deletes existing data outside the backup's
          scope.
        </p>
      </div>

      <div className="glass-panel p-4">
        <h3 className="font-display font-semibold text-slate-100 text-[15px] mb-3 flex items-center gap-2">
          <DatabaseBackup size={16} /> Available Backups {backups ? `(${backups.length})` : ""}
        </h3>

        {loading && <p className="text-sm text-slate-500">Loading...</p>}
        {!loading && (!backups || backups.length === 0) && (
          <p className="text-sm text-slate-500">No backups yet — click "Create Backup" to make one.</p>
        )}

        {!loading && backups && backups.length > 0 && (
          <div className="overflow-x-auto -mx-1">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[11px] text-slate-500 uppercase tracking-wide">
                  <th className="px-3 py-2 font-medium">Filename</th>
                  <th className="px-3 py-2 font-medium">Created</th>
                  <th className="px-3 py-2 font-medium">Source</th>
                  <th className="px-3 py-2 font-medium">Students</th>
                  <th className="px-3 py-2 font-medium">Attendance</th>
                  <th className="px-3 py-2 font-medium"></th>
                </tr>
              </thead>
              <tbody>
                {backups.map((b) => (
                  <tr key={b.filename} className="border-t border-white/[0.04]">
                    <td className="px-3 py-2.5 text-slate-200 font-mono text-xs">{b.filename}</td>
                    <td className="px-3 py-2.5 text-slate-500 text-xs">{formatTime(b.created_at)}</td>
                    <td className="px-3 py-2.5 text-slate-400 text-xs">{b.data_source}</td>
                    <td className="px-3 py-2.5 text-slate-300">{b.student_count}</td>
                    <td className="px-3 py-2.5 text-slate-300">{b.attendance_count}</td>
                    <td className="px-3 py-2.5 text-right">
                      <button
                        onClick={() => handleRestore(b.filename)}
                        disabled={restoringFile === b.filename}
                        className="flex items-center gap-1.5 text-xs text-slate-400 hover:text-accent-blue transition-colors disabled:opacity-50 ml-auto"
                      >
                        {restoringFile === b.filename ? (
                          <Loader2 size={13} className="animate-spin" />
                        ) : (
                          <RotateCcw size={13} />
                        )}
                        Restore
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}
