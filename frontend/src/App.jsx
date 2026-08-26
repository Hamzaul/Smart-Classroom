import React, { useCallback, useEffect, useMemo, useState } from "react";
import Sidebar from "./components/Sidebar.jsx";
import Header from "./components/Header.jsx";
import { usePolling } from "./hooks/usePolling.js";
import api from "./api/client.js";
import { formatTime } from "./utils/format.js";

import DashboardPage from "./pages/DashboardPage.jsx";
import LiveMonitoringPage from "./pages/LiveMonitoringPage.jsx";
import StudentsPage from "./pages/StudentsPage.jsx";
import AttendancePage from "./pages/AttendancePage.jsx";
import AnalyticsPage from "./pages/AnalyticsPage.jsx";
import ReportsPage from "./pages/ReportsPage.jsx";
import AlertsPage from "./pages/AlertsPage.jsx";
import DevicesPage from "./pages/DevicesPage.jsx";
import ModelsAIPage from "./pages/ModelsAIPage.jsx";
import SettingsPage from "./pages/SettingsPage.jsx";
import UsersPage from "./pages/UsersPage.jsx";
import LogsPage from "./pages/LogsPage.jsx";
import BackupPage from "./pages/BackupPage.jsx";

const MAX_HISTORY_POINTS = 40;

export default function App() {
  const [activePage, setActivePage] = useState("dashboard");
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [liveStudents, setLiveStudents] = useState([]);
  const [attentionHistory, setAttentionHistory] = useState([]);
  const [now, setNow] = useState(nowLabels());
  // Real camera state, reported by LiveFeedPanel itself (permission granted,
  // stream started/stopped, each frame actually sent) — replaces the old
  // `liveStudents.length >= 0` check, which was always true and therefore
  // never reflected whether the camera was actually connected.
  const [cameraState, setCameraState] = useState({
    active: false,
    permission: "unknown",
    lastFrameAt: null,
  });
  const handleCameraStateChange = useCallback((next) => {
    setCameraState((prev) => ({ ...prev, ...next }));
  }, []);

  useEffect(() => {
    const t = setInterval(() => setNow(nowLabels()), 1000);
    return () => clearInterval(t);
  }, []);

  // Shared, cross-page polled data. Kept at this level (rather than
  // re-fetched per-page) so switching pages doesn't cause a flash of
  // empty state, and so Header's search always has a student list ready.
  const { data: attendanceData } = usePolling(api.attendanceToday, 8000);
  const { data: alertsData } = usePolling(() => api.recentAlerts(20), 6000);
  const { data: classSummary } = usePolling(api.classSummary, 4000);
  const { data: esp32Status } = usePolling(api.esp32Status, 15000);
  const { data: enrolledStudents } = usePolling(api.listStudents, 20000);
  const { data: systemStatusData } = usePolling(api.systemStatus, 15000);
  // Real, Firestore-backed daily analytics (see backend GET
  // /api/analytics/daily). Replaces the old buildDailyAnalyticsPlaceholder,
  // which fabricated 6 of every 7 "historical" days as zeros. When Firebase
  // isn't configured this now returns storage_available: false and an
  // empty `days` array instead of fake data — the UI shows an empty state.
  const { data: dailyAnalyticsData } = usePolling(() => api.dailyAnalytics(7), 60000);

  const handleFrameResult = useCallback((result) => {
    setLiveStudents(result.students || []);
    const scores = (result.students || [])
      .filter((s) => s.is_known)
      .map((s) => s.attention_score);
    if (scores.length > 0) {
      const avg = Math.round(
        scores.reduce((a, b) => a + b, 0) / scores.length
      );
      setAttentionHistory((prev) => {
        const next = [
          ...prev,
          { label: formatTime(result.timestamp), value: avg },
        ];
        return next.slice(-MAX_HISTORY_POINTS);
      });
    }
  }, []);

  const distributionCounts = useMemo(() => {
    const counts = { excellent: 0, high: 0, medium: 0, low: 0, very_low: 0 };
    liveStudents.forEach((s) => {
      const key = (s.attention_level || "medium").toLowerCase();
      if (key in counts) counts[key] += 1;
    });
    return counts;
  }, [liveStudents]);

  const lowAttentionStudents = useMemo(
    () =>
      liveStudents
        .filter((s) => s.is_known && s.attention_score < 40)
        .sort((a, b) => a.attention_score - b.attention_score)
        .slice(0, 6),
    [liveStudents]
  );

  const totalStudents = attendanceData?.records?.length ?? liveStudents.length;
  const presentCount = attendanceData?.summary?.present ?? 0;

  const stats = {
    total: totalStudents || "--",
    present: presentCount,
    absent: Math.max((totalStudents || 0) - presentCount, 0),
    avgAttention: classSummary?.avg_attention ?? 0,
    lowAttention: classSummary?.low_attention_count ?? 0,
    sleeping: classSummary?.sleeping_count ?? 0,
    yawning: classSummary?.yawning_count ?? 0,
  };

  const systemStatus = [
    // Real camera state reported by LiveFeedPanel — actually reflects
    // whether getUserMedia succeeded and is still active, not a proxy
    // derived from unrelated attention-history data.
    { label: "Camera", online: cameraState.active },
    { label: "AI Engine", online: classSummary?.pipeline_available ?? false },
    // Authoritative Firebase state from /api/system/status, not inferred
    // from whether an attendance summary happens to be present.
    { label: "Firebase", online: !!systemStatusData?.firebase_available },
    { label: "ESP32 Gateway", online: !!esp32Status?.online },
  ];

  const dailyAnalyticsDays = dailyAnalyticsData?.days ?? [];
  const dailyAnalyticsAvailable = dailyAnalyticsData?.storage_available ?? false;

  const alertCount = (alertsData || []).length;

  return (
    <div className="flex min-h-screen">
      <Sidebar
        activePage={activePage}
        onNavigate={setActivePage}
        alertCount={alertCount}
        systemStatus={systemStatus}
        now={now}
        mobileOpen={sidebarOpen}
        onCloseMobile={() => setSidebarOpen(false)}
      />

      <div className="flex-1 min-w-0">
        <Header
          activePage={activePage}
          alertCount={alertCount}
          onToggleSidebar={() => setSidebarOpen((v) => !v)}
          onNavigate={setActivePage}
          students={enrolledStudents || []}
        />

        <main className="p-5 space-y-5 max-w-[1600px] mx-auto">
          {renderPage(activePage, {
            handleFrameResult,
            attentionHistory,
            distributionCounts,
            stats,
            liveStudents,
            presentCount,
            totalStudents,
            alertsData,
            lowAttentionStudents,
            dailyAnalyticsDays,
            dailyAnalyticsAvailable,
            classSummary,
            setActivePage,
            handleCameraStateChange,
          })}
        </main>
      </div>
    </div>
  );
}

// This is the actual fix for the reported navigation bug: previously
// `activePage` was tracked in state and passed to Sidebar, but nothing
// ever read it to decide what to render in <main> — the dashboard JSX
// was unconditional. Every sidebar click updated state with no visible
// effect. This switch is the missing piece.
function renderPage(activePage, ctx) {
  switch (activePage) {
    case "dashboard":
      return (
        <DashboardPage
          onFrameResult={ctx.handleFrameResult}
          onCameraStateChange={ctx.handleCameraStateChange}
          attentionHistory={ctx.attentionHistory}
          distributionCounts={ctx.distributionCounts}
          stats={ctx.stats}
          liveStudents={ctx.liveStudents}
          presentCount={ctx.presentCount}
          totalStudents={ctx.totalStudents}
          alertsData={ctx.alertsData}
          lowAttentionStudents={ctx.lowAttentionStudents}
          dailyAnalyticsDays={ctx.dailyAnalyticsDays}
          dailyAnalyticsAvailable={ctx.dailyAnalyticsAvailable}
          classSummary={ctx.classSummary}
          onNavigate={ctx.setActivePage}
        />
      );
    case "live":
      return (
        <LiveMonitoringPage
          onFrameResult={ctx.handleFrameResult}
          onCameraStateChange={ctx.handleCameraStateChange}
          liveStudents={ctx.liveStudents}
        />
      );
    case "students":
      return <StudentsPage />;
    case "attendance":
      return <AttendancePage />;
    case "analytics":
      return (
        <AnalyticsPage
          attentionHistory={ctx.attentionHistory}
          distributionCounts={ctx.distributionCounts}
          stats={ctx.stats}
        />
      );
    case "reports":
      return <ReportsPage />;
    case "alerts":
      return <AlertsPage />;
    case "devices":
      return <DevicesPage />;
    case "models":
      return <ModelsAIPage />;
    case "settings":
      return <SettingsPage />;
    case "users":
      return <UsersPage />;
    case "logs":
      return <LogsPage />;
    case "backup":
      return <BackupPage />;
    default:
      return (
        <DashboardPage
          onFrameResult={ctx.handleFrameResult}
          onCameraStateChange={ctx.handleCameraStateChange}
          attentionHistory={ctx.attentionHistory}
          distributionCounts={ctx.distributionCounts}
          stats={ctx.stats}
          liveStudents={ctx.liveStudents}
          presentCount={ctx.presentCount}
          totalStudents={ctx.totalStudents}
          alertsData={ctx.alertsData}
          lowAttentionStudents={ctx.lowAttentionStudents}
          dailyAnalyticsDays={ctx.dailyAnalyticsDays}
          dailyAnalyticsAvailable={ctx.dailyAnalyticsAvailable}
          classSummary={ctx.classSummary}
          onNavigate={ctx.setActivePage}
        />
      );
  }
}

function nowLabels() {
  const d = new Date();
  return {
    dateLabel: d.toLocaleDateString(undefined, {
      weekday: "long",
      day: "2-digit",
      month: "short",
      year: "numeric",
    }),
    timeLabel: d.toLocaleTimeString(),
  };
}


