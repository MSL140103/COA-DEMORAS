"use client";

import { formatDateTime, formatDuration, formatPct } from "@/lib/format";
import type { AtomicIntervalOut } from "@/lib/types";

export default function TimelineTable({
  intervals,
  onSelect,
}: {
  intervals: AtomicIntervalOut[];
  onSelect: (index: number) => void;
}) {
  let cumulative = 0;

  return (
    <div className="rounded-lg border border-slate-200 bg-white shadow-sm">
      <div className="border-b border-slate-200 px-4 py-3">
        <h2 className="text-sm font-semibold text-slate-900">Atomic Timeline</h2>
        <p className="text-xs text-slate-400">Click a row to see the full traceability chain and override it.</p>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-2">From</th>
              <th className="px-4 py-2">To</th>
              <th className="px-4 py-2">Duration</th>
              <th className="px-4 py-2">Count %</th>
              <th className="px-4 py-2">Counted</th>
              <th className="px-4 py-2">Cumulative</th>
              <th className="px-4 py-2">Rule</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {intervals.map((interval, index) => {
              const counted = interval.duration_seconds * parseFloat(interval.final_time_count_factor);
              cumulative += counted;
              const hasSecondary = interval.secondary_rule_ids.length > 0;
              return (
                <tr
                  key={`${interval.interval_start}-${interval.interval_end}`}
                  className="cursor-pointer hover:bg-slate-50"
                  onClick={() => onSelect(index)}
                >
                  <td className="px-4 py-2 text-slate-700">{formatDateTime(interval.interval_start)}</td>
                  <td className="px-4 py-2 text-slate-700">{formatDateTime(interval.interval_end)}</td>
                  <td className="px-4 py-2 text-slate-500">{formatDuration(interval.duration_seconds)}</td>
                  <td className="px-4 py-2">
                    <span
                      className={`badge ${
                        interval.final_time_count_factor === "1" || parseFloat(interval.final_time_count_factor) === 1
                          ? "bg-emerald-100 text-emerald-800"
                          : parseFloat(interval.final_time_count_factor) === 0
                            ? "bg-red-100 text-red-800"
                            : "bg-amber-100 text-amber-800"
                      }`}
                    >
                      {formatPct(interval.final_time_count_factor)}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-slate-600">{formatDuration(counted)}</td>
                  <td className="px-4 py-2 text-slate-400">{formatDuration(cumulative)}</td>
                  <td className="px-4 py-2">
                    <button className="font-medium text-slate-900 underline decoration-dotted underline-offset-2 hover:text-blue-700">
                      {interval.primary_rule_name}
                    </button>
                    {hasSecondary && <span className="ml-1 text-xs text-slate-400">+{interval.secondary_rule_ids.length}</span>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
