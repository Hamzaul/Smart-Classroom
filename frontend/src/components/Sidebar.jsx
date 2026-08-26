import React from "react";
import {
  LayoutDashboard,
  Video,
  Users,
  CalendarCheck,
  LineChart,
  FileText,
  Bell,
  Cpu,
  Brain,
  Settings,
  UserCog,
  ScrollText,
  DatabaseBackup,
  ShieldCheck,
  X,
} from "lucide-react";
import { classNames } from "../utils/format.js";

const NAV_ITEMS = [
  { key: "dashboard", label: "Dashboard", icon: LayoutDashboard },
  { key: "live", label: "Live Monitoring", icon: Video },
  { key: "students", label: "Students", icon: Users },
  { key: "attendance", label: "Attendance", icon: CalendarCheck },
  { key: "analytics", label: "Analytics", icon: LineChart },
  { key: "reports", label: "Reports", icon: FileText },
  { key: "alerts", label: "Alerts", icon: Bell, badgeKey: "alertCount" },
  { key: "devices", label: "Devices (IoT)", icon: Cpu },
  { key: "models", label: "Models & AI", icon: Brain },
  { key: "settings", label: "Settings", icon: Settings },
  { key: "users", label: "Users", icon: UserCog },
  { key: "logs", label: "Logs", icon: ScrollText },
  { key: "backup", label: "Backup", icon: DatabaseBackup },
];

function SidebarContent({ activePage, onNavigate, alertCount, systemStatus, now, onClose }) {
  const statusItems = systemStatus || [];
  const allOnline = statusItems.length > 0 && statusItems.every((s) => s.online);
  const anyOnline = statusItems.some((s) => s.online);

  return (
    <>
      <div className="flex items-center gap-2.5 px-2 mb-7">
        <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-violet-500 to-violet-600 flex items-center justify-center shadow-glow shrink-0">
          <ShieldCheck size={18} className="text-white" />
        </div>
        <div className="flex-1 min-w-0">
          <p className="font-display font-semibold text-slate-100 text-[15px] leading-tight">
            Smart Classroom
          </p>
          <p className="text-[11px] text-slate-500 leading-tight mt-0.5">
            AI Attention &amp; Attendance
          </p>
        </div>
        {onClose && (
          <button onClick={onClose} className="lg:hidden p-1 text-slate-500 hover:text-slate-200">
            <X size={18} />
          </button>
        )}
      </div>

      <nav className="flex-1 space-y-1 overflow-y-auto">
        {NAV_ITEMS.map(({ key, label, icon: Icon, badgeKey }) => (
          <button
            key={key}
            onClick={() => {
              onNavigate(key);
              onClose?.();
            }}
            className={classNames(
              "nav-item w-full text-left",
              activePage === key && "nav-item-active"
            )}
          >
            <Icon size={17} strokeWidth={2} />
            <span className="flex-1">{label}</span>
            {badgeKey === "alertCount" && alertCount > 0 && (
              <span className="text-[11px] font-semibold px-1.5 py-0.5 rounded-md bg-accent-red/90 text-white">
                {alertCount}
              </span>
            )}
          </button>
        ))}
      </nav>

      <div className="mt-4 glass-card p-3.5">
        <div className="flex items-center justify-between mb-2.5">
          <span className="text-xs font-semibold text-slate-300">
            System Status
          </span>
          <span
            className={classNames(
              "flex items-center gap-1 text-[11px] font-medium",
              allOnline ? "text-accent-green" : anyOnline ? "text-accent-amber" : "text-accent-red"
            )}
          >
            <span
              className={classNames(
                "w-1.5 h-1.5 rounded-full animate-pulse",
                allOnline ? "bg-accent-green" : anyOnline ? "bg-accent-amber" : "bg-accent-red"
              )}
            />
            {allOnline
              ? "All Systems Operational"
              : anyOnline
              ? "Partial Outage"
              : "Systems Offline"}
          </span>
        </div>
        <ul className="space-y-1.5 text-[11px]">
          {(systemStatus || []).map((item) => (
            <li key={item.label} className="flex items-center justify-between">
              <span className="text-slate-500">{item.label}</span>
              <span
                className={
                  item.online ? "text-accent-green" : "text-accent-red"
                }
              >
                {item.online ? "Online" : "Offline"}
              </span>
            </li>
          ))}
        </ul>
      </div>

      <div className="mt-3 px-1 text-[11px] text-slate-500">
        <p>{now?.dateLabel}</p>
        <p className="font-mono text-slate-400 mt-0.5">{now?.timeLabel}</p>
      </div>
    </>
  );
}

export default function Sidebar({
  activePage,
  onNavigate,
  alertCount = 0,
  systemStatus,
  now,
  mobileOpen = false,
  onCloseMobile,
}) {
  return (
    <>
      {/* Desktop: persistent sidebar, lg breakpoint and up */}
      <aside className="hidden lg:flex flex-col w-[248px] shrink-0 h-screen sticky top-0 border-r border-white/[0.06] bg-base-900/70 backdrop-blur-xl px-4 py-5">
        <SidebarContent
          activePage={activePage}
          onNavigate={onNavigate}
          alertCount={alertCount}
          systemStatus={systemStatus}
          now={now}
        />
      </aside>

      {/* Mobile/tablet: slide-in drawer, triggered by the Header hamburger
          button. Without this, the whole navigation was unreachable below
          the lg breakpoint — the hamburger button existed but did nothing. */}
      {mobileOpen && (
        <div className="lg:hidden fixed inset-0 z-40">
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={onCloseMobile}
          />
          <aside className="absolute left-0 top-0 h-full w-[280px] flex flex-col bg-base-900 border-r border-white/[0.06] px-4 py-5 shadow-2xl transition-transform">
            <SidebarContent
              activePage={activePage}
              onNavigate={onNavigate}
              alertCount={alertCount}
              systemStatus={systemStatus}
              now={now}
              onClose={onCloseMobile}
            />
          </aside>
        </div>
      )}
    </>
  );
}
