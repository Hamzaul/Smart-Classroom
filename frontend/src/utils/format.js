export function levelBadgeClass(level) {
  const normalized = (level || "").toLowerCase().replace(/\s+/g, "_");
  return `badge badge-${normalized || "medium"}`;
}

export function formatLevel(level) {
  if (!level) return "Unknown";
  return level.charAt(0).toUpperCase() + level.slice(1).replace(/_/g, " ");
}

export function formatTime(isoOrEpoch) {
  if (!isoOrEpoch) return "--:--";
  const date =
    typeof isoOrEpoch === "number"
      ? new Date(isoOrEpoch * 1000)
      : new Date(isoOrEpoch);
  if (Number.isNaN(date.getTime())) return "--:--";
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function classNames(...parts) {
  return parts.filter(Boolean).join(" ");
}

export function attentionColor(score) {
  if (score >= 80) return "#34D399";
  if (score >= 60) return "#38BDF8";
  if (score >= 40) return "#FBBF24";
  if (score >= 20) return "#FB923C";
  return "#F87171";
}
