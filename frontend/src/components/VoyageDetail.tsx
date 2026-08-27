"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { CalculationVersion, SOFEvent, Voyage } from "@/lib/types";
import SofEventsTable from "./SofEventsTable";
import DocumentUpload from "./DocumentUpload";
import CalculationSummary from "./CalculationSummary";
import TimelineTable from "./TimelineTable";
import ExplanationDrawer from "./ExplanationDrawer";

export default function VoyageDetail({ voyageId }: { voyageId: string }) {
  const [voyage, setVoyage] = useState<Voyage | null>(null);
  const [events, setEvents] = useState<SOFEvent[]>([]);
  const [calc, setCalc] = useState<CalculationVersion | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [calcError, setCalcError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);
  const [currentUser, setCurrentUser] = useState("");

  const loadVoyage = useCallback(() => {
    api.getVoyage(voyageId).then(setVoyage).catch((e) => setError(String(e)));
  }, [voyageId]);

  const loadEvents = useCallback(() => {
    api.listSofEvents(voyageId).then(setEvents).catch((e) => setError(String(e)));
  }, [voyageId]);

  const loadLatestCalc = useCallback(() => {
    api
      .latestCalculation(voyageId)
      .then(setCalc)
      .catch(() => setCalc(null));
  }, [voyageId]);

  useEffect(() => {
    loadVoyage();
    loadEvents();
    loadLatestCalc();
  }, [loadVoyage, loadEvents, loadLatestCalc]);

  const runCalculation = async () => {
    setRunning(true);
    setCalcError(null);
    try {
      const result = await api.runCalculation(voyageId, currentUser || "unknown");
      setCalc(result);
    } catch (err) {
      setCalcError(String(err));
    } finally {
      setRunning(false);
    }
  };

  const confirmedCount = events.filter((e) => e.status === "CONFIRMED").length;

  if (error) return <main className="p-10 text-red-600">{error}</main>;
  if (!voyage) return <main className="p-10 text-slate-400">Loading…</main>;

  return (
    <main className="mx-auto max-w-6xl w-full px-6 py-10 space-y-6">
      <div>
        <Link href="/" className="text-xs text-slate-400 hover:underline">
          ← Voyages
        </Link>
        <div className="mt-1 flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-slate-900">
              {voyage.vessel_name} <span className="text-slate-400 font-normal">/ {voyage.voyage_number}</span>
            </h1>
            <p className="text-sm text-slate-500">
              {voyage.counterparty ?? "—"} · {voyage.load_port ?? voyage.discharge_port ?? "—"} ·{" "}
              {voyage.allowed_laytime_value} {voyage.allowed_laytime_unit} allowed
            </p>
          </div>
          <span className="badge bg-slate-100 text-slate-700">{voyage.workflow_state}</span>
        </div>
      </div>

      <div className="flex items-end gap-3 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
        <label className="flex flex-col gap-1 text-xs">
          <span className="font-medium text-slate-500">Your identity (created_by)</span>
          <input
            className="input w-64"
            placeholder="operator@sw.com"
            value={currentUser}
            onChange={(e) => setCurrentUser(e.target.value)}
          />
        </label>
        <button className="btn-primary" disabled={running || confirmedCount === 0} onClick={runCalculation}>
          {running ? "Calculating…" : "Run Calculation"}
        </button>
        <span className="text-xs text-slate-400">{confirmedCount} confirmed event(s)</span>
        {calcError && <span className="text-xs text-red-600">{calcError}</span>}
      </div>

      <DocumentUpload voyageId={voyageId} onUploaded={loadEvents} />

      <SofEventsTable voyageId={voyageId} events={events} onChanged={loadEvents} currentUser={currentUser} />

      {calc && (
        <>
          <CalculationSummary calc={calc} voyage={voyage} />
          <TimelineTable intervals={calc.results.intervals} onSelect={setSelectedIndex} />
        </>
      )}

      {calc && selectedIndex !== null && (
        <ExplanationDrawer
          voyageId={voyageId}
          calculationId={calc.id}
          index={selectedIndex}
          currentUser={currentUser}
          onClose={() => setSelectedIndex(null)}
          onOverridden={() => {
            setSelectedIndex(null);
            loadLatestCalc();
          }}
        />
      )}
    </main>
  );
}
