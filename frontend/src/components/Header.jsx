import React, { useEffect, useMemo, useRef, useState } from "react";
import { Search, Bell, ChevronDown, Menu } from "lucide-react";

const PAGE_TITLES = {
  dashboard: "Dashboard",
  live: "Live Monitoring",
  students: "Students",
  attendance: "Attendance",
  analytics: "Analytics",
  reports: "Reports",
  alerts: "Alerts",
  devices: "Devices (IoT)",
  models: "Models & AI",
  settings: "Settings",
  users: "Users",
  logs: "Logs",
  backup: "Backup",
};

export default function Header({
  activePage = "dashboard",
  alertCount = 0,
  onToggleSidebar,
  onNavigate,
  students = [],
}) {
  const [query, setQuery] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const searchRef = useRef(null);

  useEffect(() => {
    function handleClickOutside(e) {
      if (searchRef.current && !searchRef.current.contains(e.target)) {
        setSearchOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const results = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    return students
      .filter(
        (s) =>
          s.name?.toLowerCase().includes(q) ||
          s.roll_number?.toLowerCase().includes(q)
      )
      .slice(0, 8);
  }, [query, students]);

  const handleSelect = () => {
    setSearchOpen(false);
    setQuery("");
    onNavigate?.("students");
  };

  return (
    <header className="flex items-center justify-between gap-4 px-6 py-4 border-b border-white/[0.06] bg-base-900/50 backdrop-blur-xl sticky top-0 z-20">
      <div className="flex items-center gap-3">
        <button
          onClick={onToggleSidebar}
          className="lg:hidden p-2 rounded-lg hover:bg-white/5 text-slate-400"
        >
          <Menu size={18} />
        </button>
        <div>
          <div className="flex items-center gap-2">
            <h1 className="font-display font-semibold text-xl text-slate-100">
              {PAGE_TITLES[activePage] || "Dashboard"}
            </h1>
            <span className="flex items-center gap-1.5 text-[11px] font-medium px-2 py-0.5 rounded-full bg-accent-green/15 text-accent-green">
              <span className="w-1.5 h-1.5 rounded-full bg-accent-green animate-pulse" />
              Live
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-0.5">
            Real-time AI Monitoring · Attention Tracking · Automatic
            Attendance
          </p>
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div ref={searchRef} className="relative hidden md:block">
          <div className="flex items-center gap-2 glass-card px-3 py-2 w-72 text-slate-400">
            <Search size={15} />
            <input
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setSearchOpen(true);
              }}
              onFocus={() => setSearchOpen(true)}
              placeholder="Search students, classes..."
              className="bg-transparent outline-none text-sm placeholder:text-slate-500 flex-1 text-slate-200"
            />
            {!query && (
              <kbd className="text-[10px] px-1.5 py-0.5 rounded bg-white/5 border border-white/10 text-slate-500">
                ⌘K
              </kbd>
            )}
          </div>

          {searchOpen && query.trim() && (
            <div className="absolute top-full mt-1.5 w-full glass-panel p-1.5 max-h-72 overflow-y-auto z-30">
              {results.length === 0 ? (
                <p className="text-xs text-slate-500 px-2.5 py-2">
                  No students match "{query}"
                </p>
              ) : (
                results.map((s) => (
                  <button
                    key={s.student_id}
                    onClick={handleSelect}
                    className="w-full text-left px-2.5 py-2 rounded-lg hover:bg-white/5 transition-colors flex items-center justify-between"
                  >
                    <span className="text-sm text-slate-200">{s.name}</span>
                    <span className="text-xs text-slate-500 font-mono">{s.roll_number}</span>
                  </button>
                ))
              )}
            </div>
          )}
        </div>

        <button
          onClick={() => onNavigate?.("alerts")}
          className="relative p-2.5 rounded-lg glass-card text-slate-400 hover:text-slate-200 transition-colors"
        >
          <Bell size={16} />
          {alertCount > 0 && (
            <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-accent-red text-[10px] font-bold flex items-center justify-center text-white">
              {alertCount > 9 ? "9+" : alertCount}
            </span>
          )}
        </button>

        <div className="flex items-center gap-2.5 glass-card pl-1.5 pr-3 py-1.5 cursor-pointer">
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-violet-400 to-accent-blue flex items-center justify-center text-xs font-semibold text-white">
            A
          </div>
          <div className="hidden sm:block leading-tight">
            <p className="text-xs font-medium text-slate-200">Admin</p>
            <p className="text-[10px] text-slate-500">Administrator</p>
          </div>
          <ChevronDown size={14} className="text-slate-500" />
        </div>
      </div>
    </header>
  );
}
