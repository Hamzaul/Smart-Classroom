import React from "react";
import LiveFeedPanel from "../components/LiveFeedPanel.jsx";
import AttentionOverTimeChart from "../components/AttentionOverTimeChart.jsx";
import AttentionDistributionChart from "../components/AttentionDistributionChart.jsx";
import StatCardsRow from "../components/StatCardsRow.jsx";
import StudentAttentionList from "../components/StudentAttentionList.jsx";
import {
  AttendanceSummaryCard,
  LowAttentionStudentsCard,
} from "../components/AttendanceAndLowAttention.jsx";
import RecentAlertsPanel from "../components/RecentAlertsPanel.jsx";
import DailyAnalyticsPanel from "../components/DailyAnalyticsPanel.jsx";
import QuickActionsBar from "../components/QuickActionsBar.jsx";

export default function DashboardPage({
  onFrameResult,
  onCameraStateChange,
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
  onNavigate,
}) {
  return (
    <>
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <LiveFeedPanel onFrameResult={onFrameResult} onCameraStateChange={onCameraStateChange} />

        <div className="glass-panel p-4">
          <h2 className="font-display font-semibold text-slate-100 text-[15px] mb-3">
            Attention Over Time
          </h2>
          <AttentionOverTimeChart points={attentionHistory} />
        </div>

        <div className="glass-panel p-4">
          <h2 className="font-display font-semibold text-slate-100 text-[15px] mb-3">
            Attention Distribution
          </h2>
          <AttentionDistributionChart counts={distributionCounts} />
        </div>
      </div>

      <StatCardsRow stats={stats} />

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <StudentAttentionList students={liveStudents} />
        <AttendanceSummaryCard
          present={presentCount}
          total={totalStudents || presentCount}
        />
        <RecentAlertsPanel alerts={alertsData || []} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <LowAttentionStudentsCard students={lowAttentionStudents} />
        <DailyAnalyticsPanel
          days={dailyAnalyticsDays}
          available={dailyAnalyticsAvailable}
          summary={{
            avgAttention: classSummary?.avg_attention ?? 0,
            maxAttention: Math.max(
              ...(attentionHistory.map((p) => p.value) || [0]),
              0
            ),
            minAttention:
              attentionHistory.length > 0
                ? Math.min(...attentionHistory.map((p) => p.value))
                : 0,
            totalAlerts: (alertsData || []).length,
          }}
        />
      </div>

      <QuickActionsBar onNavigate={onNavigate} />
    </>
  );
}
