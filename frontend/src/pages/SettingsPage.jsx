import React, { useEffect, useState } from "react";
import { Settings as SettingsIcon, Save, AlertCircle, CheckCircle2 } from "lucide-react";
import PageHeading from "../components/PageHeading.jsx";
import api from "../api/client.js";

const LABELS = {
  eye_aspect_ratio: "Eye Aspect Ratio",
  blink_rate: "Blink Rate",
  head_pose: "Head Pose",
  face_presence: "Face Presence",
  sleep_duration: "Sleep Duration",
  yawn_count: "Yawn Count",
  emotion: "Emotion",
};

export default function SettingsPage() {
  const [weights, setWeights] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getAttentionWeights()
      .then((data) => !cancelled && setWeights(data.weights))
      .catch((e) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, []);

  const sum = weights ? Object.values(weights).reduce((a, b) => a + Number(b || 0), 0) : 0;
  const sumValid = Math.abs(sum - 1) < 0.02;

  const handleChange = (key, value) => {
    setWeights((prev) => ({ ...prev, [key]: value }));
    setSuccess(null);
  };

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const numeric = Object.fromEntries(
        Object.entries(weights).map(([k, v]) => [k, Number(v)])
      );
      const data = await api.updateAttentionWeights(numeric);
      setWeights(data.weights);
      setSuccess("Attention weights updated — takes effect immediately, no restart needed.");
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <PageHeading
        title="Settings"
        subtitle="Attention scoring weights — the same config file the AI engine reads"
      />

      <div className="glass-panel p-4 max-w-2xl">
        <h3 className="font-display font-semibold text-slate-100 text-[15px] mb-1 flex items-center gap-2">
          <SettingsIcon size={16} /> Attention Score Weights
        </h3>
        <p className="text-xs text-slate-500 mb-4">
          Must sum to 1.0. These directly control how the attention score is
          computed for every processed frame — see backend/config/attention_weights.json.
        </p>

        {loading && <p className="text-sm text-slate-500">Loading...</p>}

        {weights && (
          <div className="space-y-3">
            {Object.entries(weights).map(([key, value]) => (
              <div key={key} className="flex items-center gap-3">
                <label className="text-sm text-slate-300 w-40 shrink-0">
                  {LABELS[key] || key}
                </label>
                <input
                  type="number"
                  min="0"
                  max="1"
                  step="0.01"
                  value={value}
                  onChange={(e) => handleChange(key, e.target.value)}
                  className="glass-card px-3 py-1.5 text-sm text-slate-200 outline-none bg-base-800 w-24"
                />
              </div>
            ))}

            <div className="flex items-center justify-between pt-2">
              <span className={`text-xs font-mono ${sumValid ? "text-accent-green" : "text-accent-red"}`}>
                Sum: {sum.toFixed(2)} {sumValid ? "✓" : "(must be ~1.00)"}
              </span>
              <button
                onClick={handleSave}
                disabled={saving || !sumValid}
                className="flex items-center gap-2 text-sm font-medium px-4 py-2 rounded-lg bg-violet-500/90 hover:bg-violet-500 disabled:opacity-50 text-white transition-colors"
              >
                <Save size={14} /> {saving ? "Saving..." : "Save Weights"}
              </button>
            </div>

            {error && (
              <p className="text-xs text-accent-red flex items-center gap-1.5">
                <AlertCircle size={13} /> {error}
              </p>
            )}
            {success && (
              <p className="text-xs text-accent-green flex items-center gap-1.5">
                <CheckCircle2 size={13} /> {success}
              </p>
            )}
          </div>
        )}
      </div>
    </>
  );
}
