import React, { useState } from "react";
import LiveFeedPanel from "../components/LiveFeedPanel.jsx";
import StudentAttentionList from "../components/StudentAttentionList.jsx";
import PageHeading from "../components/PageHeading.jsx";

export default function LiveMonitoringPage({ onFrameResult, onCameraStateChange, liveStudents }) {
  const [lastUpdate, setLastUpdate] = useState(null);

  const handleFrame = (result) => {
    setLastUpdate(Date.now());
    onFrameResult(result);
  };

  return (
    <>
      <PageHeading
        title="Live Monitoring"
        subtitle="Full-resolution classroom feed with real-time face detection and attention overlays"
      />
      <LiveFeedPanel onFrameResult={handleFrame} onCameraStateChange={onCameraStateChange} />
      {lastUpdate && (
        <p className="text-[11px] text-slate-500 -mt-2">
          Last frame processed {new Date(lastUpdate).toLocaleTimeString()}
        </p>
      )}
      <StudentAttentionList students={liveStudents} />
    </>
  );
}
