import React from "react";
import PageHeading from "../components/PageHeading.jsx";
import AttentionOverTimeChart from "../components/AttentionOverTimeChart.jsx";
import AttentionDistributionChart from "../components/AttentionDistributionChart.jsx";
import StatCardsRow from "../components/StatCardsRow.jsx";

export default function AnalyticsPage({ attentionHistory, distributionCounts, stats }) {
  return (
    <>
      <PageHeading
        title="Analytics"
        subtitle="Class-wide attention trends for the current live session"
      />
      <StatCardsRow stats={stats} />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="glass-panel p-4">
          <h2 className="font-display font-semibold text-slate-100 text-[15px] mb-3">
            Attention Over Time
          </h2>
          {attentionHistory.length === 0 ? (
            <p className="text-sm text-slate-500 py-8 text-center">
              No data yet — start the camera in Live Monitoring to begin collecting attention history.
            </p>
          ) : (
            <AttentionOverTimeChart points={attentionHistory} />
          )}
        </div>
        <div className="glass-panel p-4">
          <h2 className="font-display font-semibold text-slate-100 text-[15px] mb-3">
            Attention Distribution
          </h2>
          <AttentionDistributionChart counts={distributionCounts} />
        </div>
      </div>
      <div className="glass-panel p-4">
        <p className="text-xs text-slate-500">
          Attention history shown here is collected live from this browser
          session. Weekly/monthly trend analytics require Firestore to be
          configured on the backend (see Models &amp; AI → System Status) so
          attention history persists across sessions.
        </p>
      </div>
    </>
  );
}
