"use client";

import { formatDateTime, formatDuration, formatMoney } from "@/lib/format";
import type { CalculationVersion, Voyage } from "@/lib/types";

export default function CalculationSummary({ calc, voyage }: { calc: CalculationVersion; voyage: Voyage }) {
  const { commencement, laytime, demurrage, integrity } = calc.results;

  return (
    <div className="rounded-lg border border-slate-200 bg-white shadow-sm">
      <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
        <h2 className="text-sm font-semibold text-slate-900">
          SW Calculation — v{calc.version_no}
        </h2>
        <span className={`badge ${integrity.ok ? "bg-emerald-100 text-emerald-800" : "bg-red-100 text-red-800"}`}>
          {integrity.ok ? "Integrity OK" : integrity.error}
        </span>
      </div>

      <div className="grid grid-cols-1 gap-6 p-4 md:grid-cols-3">
        <div>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Commencement</h3>
          <dl className="space-y-1 text-sm">
            {commencement.candidates.map((c) => (
              <div key={c.label} className="flex justify-between gap-4">
                <dt className="text-slate-500">{c.label}</dt>
                <dd className={c.time === commencement.selected ? "font-semibold text-slate-900" : "text-slate-600"}>
                  {formatDateTime(c.time)}
                </dd>
              </div>
            ))}
            <div className="mt-2 flex justify-between gap-4 border-t border-slate-100 pt-2">
              <dt className="font-medium text-slate-700">Selected</dt>
              <dd className="font-semibold text-slate-900">{formatDateTime(commencement.selected)}</dd>
            </div>
            <div className="text-xs text-slate-400">{commencement.rule_applied}</div>
          </dl>
        </div>

        <div>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Laytime</h3>
          <dl className="space-y-1 text-sm">
            <Row label="Allowed" value={`${voyage.allowed_laytime_value} ${voyage.allowed_laytime_unit}`} />
            <Row label="Gross Elapsed" value={formatDuration(laytime.gross_elapsed_seconds)} />
            <Row label="Used" value={formatDuration(laytime.used_laytime_seconds)} bold />
            <Row label="Remaining" value={formatDuration(laytime.remaining_laytime_seconds)} />
            <Row label="Excess" value={formatDuration(laytime.excess_time_seconds)} />
          </dl>
        </div>

        <div>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">Demurrage</h3>
          <dl className="space-y-1 text-sm">
            <Row label="Commencement" value={formatDateTime(laytime.demurrage_commencement)} />
            <Row label="Full rate time" value={formatDuration(demurrage.full_rate_time_seconds)} />
            <Row label="Half rate time" value={formatDuration(demurrage.half_rate_time_seconds)} />
            <Row label="Daily rate" value={formatMoney(demurrage.daily_rate, voyage.currency)} />
            <div className="mt-2 flex justify-between gap-4 border-t border-slate-100 pt-2">
              <dt className="font-medium text-slate-700">Amount</dt>
              <dd className="font-semibold text-slate-900">{formatMoney(demurrage.amount, voyage.currency)}</dd>
            </div>
          </dl>
        </div>
      </div>
    </div>
  );
}

function Row({ label, value, bold }: { label: string; value: string; bold?: boolean }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-slate-500">{label}</dt>
      <dd className={bold ? "font-semibold text-slate-900" : "text-slate-700"}>{value}</dd>
    </div>
  );
}
