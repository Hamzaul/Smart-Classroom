import React from "react";

export default function PageHeading({ title, subtitle, action }) {
  return (
    <div className="flex items-start justify-between gap-4 mb-1">
      <div>
        <h2 className="font-display font-semibold text-lg text-slate-100">{title}</h2>
        {subtitle && <p className="text-xs text-slate-500 mt-0.5">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}
