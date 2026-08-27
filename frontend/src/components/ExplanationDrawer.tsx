"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { categoryColor } from "@/lib/categoryColor";
import { formatDateTime, formatDuration, formatPct, intervalKey } from "@/lib/format";
import type { AtomicIntervalOut, ExplanationResult } from "@/lib/types";

export default function ExplanationDrawer({
  voyageId,
  calculationId,
  index,
  currentUser,
  onClose,
  onOverridden,
}: {
  voyageId: string;
  calculationId: string;
  index: number;
  currentUser: string;
  onClose: () => void;
  onOverridden: () => void;
}) {
  const [data, setData] = useState<ExplanationResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showOverride, setShowOverride] = useState(false);

  useEffect(() => {
    setData(null);
    api
      .explainInterval(voyageId, calculationId, index)
      .then(setData)
      .catch((e) => setError(String(e)));
  }, [voyageId, calculationId, index]);

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-slate-900/30" onClick={onClose}>
      <div
        className="h-full w-full max-w-lg overflow-y-auto bg-white p-6 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-sm font-semibold uppercase tracking-wide text-slate-500">Explanation</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-700">
            ✕
          </button>
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}
        {!data && !error && <p className="text-sm text-slate-400">Loading…</p>}

        {data && (
          <div className="space-y-6">
            <Section title="Period">
              <p className="text-sm text-slate-700">
                {formatDateTime(data.interval.interval_start)} → {formatDateTime(data.interval.interval_end)} (
                {formatDuration(data.interval.duration_seconds)})
              </p>
              <p className="mt-1 text-sm">
                Treatment: <b>{formatPct(data.interval.final_time_count_factor)}</b> counted,{" "}
                <b>{formatPct(data.interval.final_demurrage_rate_factor)}</b> demurrage rate
              </p>
            </Section>

            <Section title="SOF Evidence — what happened?">
              <ul className="space-y-2">
                {data.sof_evidence.length === 0 && <li className="text-sm text-slate-400">No active events (default treatment).</li>}
                {data.sof_evidence.map((ev) => (
                  <li key={ev.id} className="rounded-md border border-slate-100 bg-slate-50 p-2 text-sm">
                    <span className={`badge ${categoryColor(ev.category)} mb-1`}>{ev.category}</span>
                    <div className="text-xs text-slate-500">
                      {formatDateTime(ev.start_time)} {ev.end_time ? `→ ${formatDateTime(ev.end_time)}` : ""}
                    </div>
                    {ev.source_text && <div className="mt-1 text-xs italic text-slate-400">&ldquo;{ev.source_text}&rdquo;</div>}
                  </li>
                ))}
              </ul>
            </Section>

            <Section title="Selected Rule — contractual basis">
              {data.selected_rule && (
                <div className="space-y-1 text-sm">
                  <p className="font-medium text-slate-900">{data.selected_rule.name}</p>
                  <p className="text-xs text-slate-500">
                    time count {formatPct(data.selected_rule.time_count_factor)} · demurrage rate{" "}
                    {formatPct(data.selected_rule.demurrage_rate_factor)} · scope {data.selected_rule.scope}
                  </p>
                  {data.selected_rule.source_clause_id ? (
                    <p className="text-xs text-slate-500">
                      Source: clause {data.selected_rule.source_clause_id}
                      {data.selected_rule.source_page ? `, p.${data.selected_rule.source_page}` : ""}
                    </p>
                  ) : (
                    <p className="text-xs text-amber-700">SOURCE NOT LINKED — {data.selected_rule.source_note}</p>
                  )}
                </div>
              )}
            </Section>

            {data.secondary_rules.length > 0 && (
              <Section title="Secondary rules — no additional deduction">
                <ul className="space-y-1">
                  {data.secondary_rules.map(
                    (r) =>
                      r && (
                        <li key={r.id} className="text-sm text-slate-600">
                          {r.name} — matched but did not change the outcome (NO DOUBLE DEDUCTION)
                        </li>
                      )
                  )}
                </ul>
              </Section>
            )}

            <Section title="Why">
              <p className="text-sm text-slate-700">{data.decision_reason}</p>
            </Section>

            <div className="border-t border-slate-200 pt-4">
              {!showOverride ? (
                <button className="btn-secondary text-sm" onClick={() => setShowOverride(true)}>
                  Override this period
                </button>
              ) : (
                <OverrideForm
                  voyageId={voyageId}
                  interval={data.interval}
                  currentUser={currentUser}
                  onDone={() => {
                    setShowOverride(false);
                    onOverridden();
                  }}
                  onCancel={() => setShowOverride(false)}
                />
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</h3>
      {children}
    </div>
  );
}

function OverrideForm({
  voyageId,
  interval,
  currentUser,
  onDone,
  onCancel,
}: {
  voyageId: string;
  interval: AtomicIntervalOut;
  currentUser: string;
  onDone: () => void;
  onCancel: () => void;
}) {
  const [timeFactor, setTimeFactor] = useState(interval.final_time_count_factor);
  const [rateFactor, setRateFactor] = useState(interval.final_demurrage_rate_factor);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    if (!reason.trim()) {
      setError("Reason is required — overrides must always be explained.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await api.createOverride(voyageId, {
        target_key: intervalKey(interval.interval_start, interval.interval_end),
        new_time_count_factor: parseFloat(timeFactor),
        new_demurrage_rate_factor: parseFloat(rateFactor),
        reason,
        created_by: currentUser || "unknown",
      });
      onDone();
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-3 rounded-md border border-amber-200 bg-amber-50 p-3">
      <div className="grid grid-cols-2 gap-3">
        <label className="flex flex-col gap-1 text-xs">
          <span className="font-medium text-slate-600">Time Count Factor</span>
          <input className="input" type="number" min="0" max="1" step="0.05" value={timeFactor}
            onChange={(e) => setTimeFactor(e.target.value)} />
        </label>
        <label className="flex flex-col gap-1 text-xs">
          <span className="font-medium text-slate-600">Demurrage Rate Factor</span>
          <input className="input" type="number" min="0" max="1" step="0.05" value={rateFactor}
            onChange={(e) => setRateFactor(e.target.value)} />
        </label>
      </div>
      <label className="flex flex-col gap-1 text-xs">
        <span className="font-medium text-slate-600">Reason (required)</span>
        <textarea className="input" rows={2} value={reason} onChange={(e) => setReason(e.target.value)} />
      </label>
      {error && <p className="text-xs text-red-600">{error}</p>}
      <div className="flex gap-2">
        <button className="btn-primary text-xs" disabled={busy} onClick={submit}>
          {busy ? "Saving…" : "Save override & recalculate"}
        </button>
        <button className="btn-secondary text-xs" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </div>
  );
}
