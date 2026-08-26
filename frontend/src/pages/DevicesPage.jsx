import React from "react";
import { Cpu, Wifi, WifiOff } from "lucide-react";
import PageHeading from "../components/PageHeading.jsx";
import { usePolling } from "../hooks/usePolling.js";
import { formatTime } from "../utils/format.js";
import api from "../api/client.js";

export default function DevicesPage() {
  const { data: esp32, loading } = usePolling(api.esp32Status, 10000);

  const online = !!esp32?.online;

  return (
    <>
      <PageHeading title="Devices (IoT)" subtitle="ESP32 classroom alert hardware" />

      <div className="glass-panel p-5 flex items-center gap-4">
        <div className={`p-3 rounded-xl ${online ? "bg-accent-green/15 text-accent-green" : "bg-white/5 text-slate-500"}`}>
          <Cpu size={24} />
        </div>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h3 className="font-display font-semibold text-slate-100 text-base">ESP32 Gateway</h3>
            <span className={`flex items-center gap-1 text-xs font-medium ${online ? "text-accent-green" : "text-accent-red"}`}>
              {online ? <Wifi size={13} /> : <WifiOff size={13} />}
              {loading ? "Checking..." : online ? "Online" : "Offline"}
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Drives the classroom's LED / buzzer / LCD alert unit over WiFi.
          </p>
        </div>
      </div>

      <div className="glass-panel p-4">
        <h3 className="font-display font-semibold text-slate-100 text-[15px] mb-3">Connection Details</h3>
        <dl className="grid grid-cols-2 gap-y-3 text-sm">
          <dt className="text-slate-500">Status</dt>
          <dd className={online ? "text-accent-green" : "text-accent-red"}>
            {online ? "Online" : esp32?.reason === "ESP32 service disabled" ? "Disabled" : "Offline"}
          </dd>

          <dt className="text-slate-500">Last Successful Command</dt>
          <dd className="text-slate-300 font-mono text-xs">
            {esp32?.last_success ? formatTime(esp32.last_success * 1000) : "Never"}
          </dd>

          <dt className="text-slate-500">Last Error</dt>
          <dd className="text-slate-300 text-xs break-all">{esp32?.last_error || "None"}</dd>
        </dl>

        {!online && (
          <p className="text-xs text-slate-500 mt-4 pt-4 border-t border-white/[0.06]">
            The rest of the dashboard continues to work normally without the
            ESP32 — it only drives physical LED/buzzer/LCD alerts in the
            classroom. See <code className="text-slate-400">hardware/README.md</code> in
            the project for wiring and flashing instructions.
          </p>
        )}
      </div>
    </>
  );
}
