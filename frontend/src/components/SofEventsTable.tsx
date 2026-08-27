"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { categoryColor, confidenceColor, eventStatusColor } from "@/lib/categoryColor";
import { EVENT_CATEGORIES } from "@/lib/eventCategories";
import { formatDateTime } from "@/lib/format";
import type { SOFEvent } from "@/lib/types";

function toLocalInput(iso: string | null | undefined): string {
  if (!iso) return "";
  return iso.slice(0, 16);
}

export default function SofEventsTable({
  voyageId,
  events,
  onChanged,
  currentUser,
}: {
  voyageId: string;
  events: SOFEvent[];
  onChanged: () => void;
  currentUser: string;
}) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [newEvent, setNewEvent] = useState({ category: "NOR_TENDERED", start_time: "", end_time: "" });
  const [busy, setBusy] = useState(false);

  const confirm = async (event: SOFEvent) => {
    setBusy(true);
    try {
      await api.updateSofEvent(voyageId, event.id, {
        status: "CONFIRMED",
        changed_by: currentUser || "unknown",
        reason: "Reviewed and confirmed against SOF",
      });
      onChanged();
    } finally {
      setBusy(false);
    }
  };

  const saveEdit = async (event: SOFEvent, patch: Record<string, unknown>) => {
    setBusy(true);
    try {
      await api.updateSofEvent(voyageId, event.id, {
        ...patch,
        changed_by: currentUser || "unknown",
        reason: "Manual correction during SOF review",
      });
      setEditingId(null);
      onChanged();
    } finally {
      setBusy(false);
    }
  };

  const addEvent = async () => {
    if (!newEvent.start_time) return;
    setBusy(true);
    try {
      await api.createSofEvent(voyageId, {
        category: newEvent.category,
        start_time: new Date(newEvent.start_time).toISOString().slice(0, 19),
        end_time: newEvent.end_time ? new Date(newEvent.end_time).toISOString().slice(0, 19) : null,
        confidence_status: "CONFIRMED",
      });
      setNewEvent({ category: "NOR_TENDERED", start_time: "", end_time: "" });
      setShowAdd(false);
      onChanged();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="rounded-lg border border-slate-200 bg-white shadow-sm">
      <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
        <h2 className="text-sm font-semibold text-slate-900">SOF Events</h2>
        <button className="btn-secondary text-xs" onClick={() => setShowAdd((s) => !s)}>
          {showAdd ? "Cancelar" : "+ Agregar evento"}
        </button>
      </div>

      {showAdd && (
        <div className="flex flex-wrap items-end gap-3 border-b border-slate-200 bg-slate-50 px-4 py-3">
          <label className="flex flex-col gap-1 text-xs">
            <span className="font-medium text-slate-500">Category</span>
            <select
              className="input"
              value={newEvent.category}
              onChange={(e) => setNewEvent({ ...newEvent, category: e.target.value })}
            >
              {EVENT_CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs">
            <span className="font-medium text-slate-500">Start</span>
            <input
              type="datetime-local"
              className="input"
              value={newEvent.start_time}
              onChange={(e) => setNewEvent({ ...newEvent, start_time: e.target.value })}
            />
          </label>
          <label className="flex flex-col gap-1 text-xs">
            <span className="font-medium text-slate-500">End (opcional)</span>
            <input
              type="datetime-local"
              className="input"
              value={newEvent.end_time}
              onChange={(e) => setNewEvent({ ...newEvent, end_time: e.target.value })}
            />
          </label>
          <button className="btn-primary text-xs" disabled={busy} onClick={addEvent}>
            Guardar
          </button>
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-2">Category</th>
              <th className="px-4 py-2">From</th>
              <th className="px-4 py-2">To</th>
              <th className="px-4 py-2">Source</th>
              <th className="px-4 py-2">Confidence</th>
              <th className="px-4 py-2">Status</th>
              <th className="px-4 py-2 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {events.map((ev) => (
              <EventRow
                key={ev.id}
                event={ev}
                editing={editingId === ev.id}
                busy={busy}
                onEdit={() => setEditingId(ev.id)}
                onCancelEdit={() => setEditingId(null)}
                onSave={(patch) => saveEdit(ev, patch)}
                onConfirm={() => confirm(ev)}
              />
            ))}
            {events.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-8 text-center text-slate-400">
                  Sin eventos todavía. Sube un SOF o agrega eventos manualmente.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function EventRow({
  event,
  editing,
  busy,
  onEdit,
  onCancelEdit,
  onSave,
  onConfirm,
}: {
  event: SOFEvent;
  editing: boolean;
  busy: boolean;
  onEdit: () => void;
  onCancelEdit: () => void;
  onSave: (patch: Record<string, unknown>) => void;
  onConfirm: () => void;
}) {
  const [start, setStart] = useState(toLocalInput(event.start_time));
  const [end, setEnd] = useState(toLocalInput(event.end_time));
  const [category, setCategory] = useState(event.category);

  if (editing) {
    return (
      <tr className="bg-blue-50/40">
        <td className="px-4 py-2">
          <select className="input" value={category} onChange={(e) => setCategory(e.target.value)}>
            {EVENT_CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </td>
        <td className="px-4 py-2">
          <input type="datetime-local" className="input" value={start} onChange={(e) => setStart(e.target.value)} />
        </td>
        <td className="px-4 py-2">
          <input type="datetime-local" className="input" value={end} onChange={(e) => setEnd(e.target.value)} />
        </td>
        <td className="px-4 py-2 text-xs text-slate-400" colSpan={2}>
          {event.source_text ?? "—"}
        </td>
        <td className="px-4 py-2">
          <span className={`badge ${eventStatusColor(event.status)}`}>{event.status}</span>
        </td>
        <td className="px-4 py-2 text-right space-x-2">
          <button
            className="btn-primary text-xs"
            disabled={busy}
            onClick={() =>
              onSave({
                category,
                start_time: new Date(start).toISOString().slice(0, 19),
                end_time: end ? new Date(end).toISOString().slice(0, 19) : null,
              })
            }
          >
            Guardar
          </button>
          <button className="btn-secondary text-xs" onClick={onCancelEdit}>
            Cancelar
          </button>
        </td>
      </tr>
    );
  }

  return (
    <tr className="hover:bg-slate-50">
      <td className="px-4 py-2">
        <span className={`badge ${categoryColor(event.category)}`}>{event.category}</span>
        {event.subtype && <span className="ml-1 text-xs text-slate-400">({event.subtype})</span>}
      </td>
      <td className="px-4 py-2 text-slate-700">{formatDateTime(event.start_time)}</td>
      <td className="px-4 py-2 text-slate-700">{formatDateTime(event.end_time)}</td>
      <td className="px-4 py-2 max-w-[220px] truncate text-xs text-slate-400" title={event.source_text ?? undefined}>
        {event.source_text ?? "manual entry"}
        {event.page_number ? ` (p.${event.page_number})` : ""}
      </td>
      <td className="px-4 py-2">
        <span className={`badge ${confidenceColor(event.confidence_status)}`}>{event.confidence_status}</span>
      </td>
      <td className="px-4 py-2">
        <span className={`badge ${eventStatusColor(event.status)}`}>{event.status}</span>
      </td>
      <td className="px-4 py-2 text-right space-x-2">
        <button className="btn-secondary text-xs" onClick={onEdit}>
          Editar
        </button>
        {event.status !== "CONFIRMED" && (
          <button className="btn-primary text-xs" disabled={busy} onClick={onConfirm}>
            Confirmar
          </button>
        )}
      </td>
    </tr>
  );
}
