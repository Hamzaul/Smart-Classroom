import React from "react";
import { Brain, CheckCircle2, XCircle, Database } from "lucide-react";
import PageHeading from "../components/PageHeading.jsx";
import { usePolling } from "../hooks/usePolling.js";
import api from "../api/client.js";

const MODULE_LABELS = {
  face_detection: "Face Detection",
  eye_tracking: "Eye Tracking / Face Mesh",
  head_pose: "Head Pose Estimation",
  sleep_yawn_detection: "Sleep & Yawn Detection",
  attention_engine: "Attention Scoring Engine",
  face_recognition: "Face Recognition",
  classroom_pipeline: "Full Processing Pipeline",
};

export default function ModelsAIPage() {
  const { data, loading, error } = usePolling(api.systemStatus, 15000);
  const modules = data?.modules || [];

  return (
    <>
      <PageHeading
        title="Models & AI"
        subtitle="Real initialization status of every AI/CV module — never shown as Online if it failed to start"
      />

      {loading && <p className="text-sm text-slate-500">Loading...</p>}
      {error && <p className="text-sm text-accent-red">{error.message}</p>}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {modules.map((m) => {
          const online = m.status === "online";
          return (
            <div key={m.key} className="glass-panel p-4 flex items-start gap-3">
              <div className={`p-2 rounded-lg ${online ? "bg-accent-green/15 text-accent-green" : "bg-accent-red/15 text-accent-red"}`}>
                {online ? <CheckCircle2 size={18} /> : <XCircle size={18} />}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <Brain size={13} className="text-slate-500" />
                  <h4 className="text-sm font-medium text-slate-200">
                    {MODULE_LABELS[m.key] || m.key}
                  </h4>
                </div>
                <p className={`text-xs mt-1 ${online ? "text-accent-green" : "text-accent-red"}`}>
                  {online ? "Online" : "Failed to initialize"}
                </p>
                {!online && m.error && (
                  <p className="text-[11px] text-slate-500 mt-1.5 break-all font-mono">{m.error}</p>
                )}
              </div>
            </div>
          );
        })}
      </div>

      <div className="glass-panel p-4">
        <h3 className="font-display font-semibold text-slate-100 text-[15px] mb-3 flex items-center gap-2">
          <Database size={15} /> System Dependencies
        </h3>
        <dl className="grid grid-cols-2 gap-y-3 text-sm">
          <dt className="text-slate-500">Live Camera Pipeline</dt>
          <dd className={data?.pipeline_available ? "text-accent-green" : "text-accent-red"}>
            {data?.pipeline_available ? "Available" : "Unavailable"}
          </dd>
          <dt className="text-slate-500">Firebase / Firestore</dt>
          <dd className={data?.firebase_available ? "text-accent-green" : "text-accent-amber"}>
            {data?.firebase_available ? "Connected" : "Not configured"}
          </dd>
          <dt className="text-slate-500">ESP32 Service</dt>
          <dd className={data?.esp32_configured ? "text-accent-green" : "text-slate-400"}>
            {data?.esp32_configured ? "Configured" : "Disabled"}
          </dd>
        </dl>
        {!data?.pipeline_available && (
          <p className="text-xs text-slate-500 mt-4 pt-4 border-t border-white/[0.06]">
            The live camera pipeline needs every CV module above to be online.
            Check the backend startup logs (Logs page) for the specific import
            or initialization error against a failed module.
          </p>
        )}
      </div>
    </>
  );
}
