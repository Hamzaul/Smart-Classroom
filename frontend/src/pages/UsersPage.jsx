import React, { useState } from "react";
import { UserCog, Plus, Trash2, Loader2, AlertCircle } from "lucide-react";
import PageHeading from "../components/PageHeading.jsx";
import { usePolling } from "../hooks/usePolling.js";
import api from "../api/client.js";

export default function UsersPage() {
  const { data: users, loading, refetch } = usePolling(api.listUsers, 15000);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("instructor");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [deletingId, setDeletingId] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await api.createUser(name, email, role);
      setName("");
      setEmail("");
      refetch();
    } catch (err) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (userId) => {
    setDeletingId(userId);
    try {
      await api.deleteUser(userId);
      refetch();
    } catch (err) {
      setError(err.message);
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <>
      <PageHeading
        title="Users"
        subtitle="Dashboard admin/instructor accounts (not students — see the Students page for those)"
      />

      <div className="glass-panel p-3.5 flex items-start gap-2.5">
        <AlertCircle size={15} className="text-accent-amber mt-0.5 shrink-0" />
        <p className="text-xs text-slate-400">
          This project doesn't implement authentication/login yet, so these
          accounts are stored in memory on the backend (not persisted to a
          database) and aren't used to gate access to the dashboard itself.
          This is a real, working CRUD list — just not wired to a login flow.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="glass-panel p-4 lg:col-span-1">
          <h3 className="font-display font-semibold text-slate-100 text-[15px] mb-3 flex items-center gap-2">
            <Plus size={16} /> Add User
          </h3>
          <form onSubmit={handleSubmit} className="space-y-3">
            <div>
              <label className="text-xs text-slate-400 block mb-1">Name</label>
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full glass-card px-3 py-2 text-sm text-slate-200 outline-none bg-base-800"
              />
            </div>
            <div>
              <label className="text-xs text-slate-400 block mb-1">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full glass-card px-3 py-2 text-sm text-slate-200 outline-none bg-base-800"
              />
            </div>
            <div>
              <label className="text-xs text-slate-400 block mb-1">Role</label>
              <select
                value={role}
                onChange={(e) => setRole(e.target.value)}
                className="w-full glass-card px-3 py-2 text-sm text-slate-200 outline-none bg-base-800"
              >
                <option value="administrator">Administrator</option>
                <option value="instructor">Instructor</option>
                <option value="viewer">Viewer</option>
              </select>
            </div>
            {error && <p className="text-xs text-accent-red">{error}</p>}
            <button
              type="submit"
              disabled={submitting}
              className="w-full flex items-center justify-center gap-2 text-sm font-medium px-3 py-2 rounded-lg bg-violet-500/90 hover:bg-violet-500 disabled:opacity-50 text-white transition-colors"
            >
              {submitting && <Loader2 size={14} className="animate-spin" />}
              {submitting ? "Adding..." : "Add User"}
            </button>
          </form>
        </div>

        <div className="glass-panel p-4 lg:col-span-2">
          <h3 className="font-display font-semibold text-slate-100 text-[15px] mb-3 flex items-center gap-2">
            <UserCog size={16} /> Accounts {users ? `(${users.length})` : ""}
          </h3>
          {loading && <p className="text-sm text-slate-500">Loading...</p>}
          {!loading && users && (
            <div className="overflow-x-auto -mx-1">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-[11px] text-slate-500 uppercase tracking-wide">
                    <th className="px-3 py-2 font-medium">Name</th>
                    <th className="px-3 py-2 font-medium">Email</th>
                    <th className="px-3 py-2 font-medium">Role</th>
                    <th className="px-3 py-2 font-medium"></th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => (
                    <tr key={u.user_id} className="border-t border-white/[0.04]">
                      <td className="px-3 py-2.5 text-slate-200 font-medium">{u.name}</td>
                      <td className="px-3 py-2.5 text-slate-400 text-xs">{u.email}</td>
                      <td className="px-3 py-2.5">
                        <span className="badge badge-medium capitalize">{u.role}</span>
                      </td>
                      <td className="px-3 py-2.5 text-right">
                        <button
                          onClick={() => handleDelete(u.user_id)}
                          disabled={deletingId === u.user_id || users.length === 1}
                          title={users.length === 1 ? "Cannot delete the last user" : "Remove user"}
                          className="text-slate-500 hover:text-accent-red transition-colors disabled:opacity-30"
                        >
                          {deletingId === u.user_id ? (
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
