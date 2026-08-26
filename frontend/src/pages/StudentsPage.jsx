import React, { useState } from "react";
import { UserPlus, Trash2, Loader2, AlertCircle } from "lucide-react";
import PageHeading from "../components/PageHeading.jsx";
import { usePolling } from "../hooks/usePolling.js";
import api from "../api/client.js";

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

export default function StudentsPage() {
  const { data: students, loading, error, refetch } = usePolling(api.listStudents, 10000);
  const [name, setName] = useState("");
  const [rollNumber, setRollNumber] = useState("");
  const [files, setFiles] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState(null);
  const [formSuccess, setFormSuccess] = useState(null);
  const [deletingId, setDeletingId] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setFormError(null);
    setFormSuccess(null);

    if (!name.trim() || !rollNumber.trim()) {
      setFormError("Name and roll number are required.");
      return;
    }
    if (files.length === 0) {
      setFormError("Upload at least one clear photo of the student's face.");
      return;
    }

    setSubmitting(true);
    try {
      const images = await Promise.all(files.map(fileToBase64));
      const result = await api.registerStudent(name.trim(), rollNumber.trim(), images);
      setFormSuccess(`Registered ${result.name} successfully.`);
      setName("");
      setRollNumber("");
      setFiles([]);
      refetch();
    } catch (err) {
      setFormError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (studentId) => {
    setDeletingId(studentId);
    try {
      await api.deleteStudent(studentId);
      refetch();
    } catch (err) {
      setFormError(err.message);
    } finally {
      setDeletingId(null);
    }
  };

  const moduleUnavailable = error?.message?.includes("unavailable");

  return (
    <>
      <PageHeading
        title="Students"
        subtitle="Enrolled students used for face-recognition attendance"
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="glass-panel p-4 lg:col-span-1">
          <h3 className="font-display font-semibold text-slate-100 text-[15px] mb-3 flex items-center gap-2">
            <UserPlus size={16} /> Register Student
          </h3>
          <form onSubmit={handleSubmit} className="space-y-3">
            <div>
              <label className="text-xs text-slate-400 block mb-1">Full Name</label>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full glass-card px-3 py-2 text-sm text-slate-200 outline-none bg-base-800"
                placeholder="e.g. Aman Kumar"
              />
            </div>
            <div>
              <label className="text-xs text-slate-400 block mb-1">Roll Number</label>
              <input
                value={rollNumber}
                onChange={(e) => setRollNumber(e.target.value)}
                className="w-full glass-card px-3 py-2 text-sm text-slate-200 outline-none bg-base-800"
                placeholder="e.g. 21CS001"
              />
            </div>
            <div>
              <label className="text-xs text-slate-400 block mb-1">
                Reference Photos ({files.length} selected)
              </label>
              <input
                type="file"
                accept="image/*"
                multiple
                onChange={(e) => setFiles(Array.from(e.target.files || []))}
                className="w-full text-xs text-slate-400 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:bg-violet-500/90 file:text-white file:text-xs"
              />
              <p className="text-[11px] text-slate-500 mt-1">
                Use 1-3 clear, front-facing photos with only this student's face visible.
              </p>
            </div>

            {formError && (
              <p className="text-xs text-accent-red flex items-center gap-1.5">
                <AlertCircle size={13} /> {formError}
              </p>
            )}
            {formSuccess && (
              <p className="text-xs text-accent-green">{formSuccess}</p>
            )}

            <button
              type="submit"
              disabled={submitting}
              className="w-full flex items-center justify-center gap-2 text-sm font-medium px-3 py-2 rounded-lg bg-violet-500/90 hover:bg-violet-500 disabled:opacity-50 text-white transition-colors"
            >
              {submitting && <Loader2 size={14} className="animate-spin" />}
              {submitting ? "Registering..." : "Register Student"}
            </button>
          </form>
        </div>

        <div className="glass-panel p-4 lg:col-span-2">
          <h3 className="font-display font-semibold text-slate-100 text-[15px] mb-3">
            Enrolled Students {students ? `(${students.length})` : ""}
          </h3>

          {loading && <p className="text-sm text-slate-500">Loading...</p>}

          {moduleUnavailable && (
            <p className="text-sm text-accent-amber flex items-center gap-2">
              <AlertCircle size={14} /> Face recognition module is unavailable on the
              backend — student registration and recognition are disabled until it's fixed.
            </p>
          )}
          {error && !moduleUnavailable && (
            <p className="text-sm text-accent-red">{error.message}</p>
          )}

          {!loading && !error && (!students || students.length === 0) && (
            <p className="text-sm text-slate-500">No students enrolled yet.</p>
          )}

          {!loading && students && students.length > 0 && (
            <div className="overflow-x-auto -mx-1">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-[11px] text-slate-500 uppercase tracking-wide">
                    <th className="px-3 py-2 font-medium">Name</th>
                    <th className="px-3 py-2 font-medium">Roll Number</th>
                    <th className="px-3 py-2 font-medium"></th>
                  </tr>
                </thead>
                <tbody>
                  {students.map((s) => (
                    <tr key={s.student_id} className="border-t border-white/[0.04]">
                      <td className="px-3 py-2.5 text-slate-200 font-medium">{s.name}</td>
                      <td className="px-3 py-2.5 text-slate-400 font-mono text-xs">{s.roll_number}</td>
                      <td className="px-3 py-2.5 text-right">
                        <button
                          onClick={() => handleDelete(s.student_id)}
                          disabled={deletingId === s.student_id}
                          className="text-slate-500 hover:text-accent-red transition-colors disabled:opacity-50"
                          title="Remove student"
                        >
                          {deletingId === s.student_id ? (
                            <Loader2 size={15} className="animate-spin" />
                          ) : (
                            <Trash2 size={15} />
                          )}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
