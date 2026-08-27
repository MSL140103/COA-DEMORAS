"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { formatDateTime, formatMoney } from "@/lib/format";
import type { Voyage } from "@/lib/types";

const emptyForm = {
  vessel_name: "",
  voyage_number: "",
  counterparty: "",
  sw_user: "",
  load_port: "",
  discharge_port: "",
  terminal: "",
  berth: "",
  operation_type: "LOADING",
  allowed_laytime_value: "72",
  allowed_laytime_unit: "HOURS",
  demurrage_rate_type: "FIXED_PDPRY",
  demurrage_rate_value: "50000",
  currency: "USD",
  nor_allowance_hours: "6",
  created_by: "",
};

export default function HomePage() {
  const [voyages, setVoyages] = useState<Voyage[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(emptyForm);
  const [submitting, setSubmitting] = useState(false);

  const load = () => {
    api
      .listVoyages()
      .then(setVoyages)
      .catch((e) => setError(String(e)));
  };

  useEffect(load, []);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await api.createVoyage({
        ...form,
        allowed_laytime_value: parseFloat(form.allowed_laytime_value),
        demurrage_rate_value: parseFloat(form.demurrage_rate_value),
        nor_allowance_hours: parseFloat(form.nor_allowance_hours),
      });
      setForm(emptyForm);
      setShowForm(false);
      load();
    } catch (err) {
      setError(String(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="mx-auto max-w-5xl w-full px-6 py-10">
      <div className="flex items-center justify-between mb-8">
        <div>
          <p className="text-xs font-mono uppercase tracking-wider text-slate-500">
            Laytime &amp; Demurrage — MVP1
          </p>
          <h1 className="text-2xl font-semibold text-slate-900">Voyages</h1>
        </div>
        <button
          onClick={() => setShowForm((s) => !s)}
          className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
        >
          {showForm ? "Cancelar" : "+ Nuevo Voyage"}
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-md border border-red-300 bg-red-50 px-4 py-3 text-sm text-red-800">
          {error}
        </div>
      )}

      {showForm && (
        <form
          onSubmit={onSubmit}
          className="mb-8 grid grid-cols-2 gap-4 rounded-lg border border-slate-200 bg-white p-6 shadow-sm"
        >
          <Field label="Vessel Name">
            <input required className="input" value={form.vessel_name}
              onChange={(e) => setForm({ ...form, vessel_name: e.target.value })} />
          </Field>
          <Field label="Voyage Number">
            <input required className="input" value={form.voyage_number}
              onChange={(e) => setForm({ ...form, voyage_number: e.target.value })} />
          </Field>
          <Field label="Counterparty">
            <input className="input" value={form.counterparty}
              onChange={(e) => setForm({ ...form, counterparty: e.target.value })} />
          </Field>
          <Field label="SW User">
            <input className="input" value={form.sw_user}
              onChange={(e) => setForm({ ...form, sw_user: e.target.value })} />
          </Field>
          <Field label="Operation Type">
            <select className="input" value={form.operation_type}
              onChange={(e) => setForm({ ...form, operation_type: e.target.value })}>
              <option value="LOADING">Loading</option>
              <option value="DISCHARGING">Discharging</option>
            </select>
          </Field>
          <Field label="Load Port">
            <input className="input" value={form.load_port}
              onChange={(e) => setForm({ ...form, load_port: e.target.value })} />
          </Field>
          <Field label="Discharge Port">
            <input className="input" value={form.discharge_port}
              onChange={(e) => setForm({ ...form, discharge_port: e.target.value })} />
          </Field>
          <Field label="Terminal / Berth">
            <div className="flex gap-2">
              <input className="input" placeholder="Terminal" value={form.terminal}
                onChange={(e) => setForm({ ...form, terminal: e.target.value })} />
              <input className="input" placeholder="Berth" value={form.berth}
                onChange={(e) => setForm({ ...form, berth: e.target.value })} />
            </div>
          </Field>
          <Field label="Allowed Laytime">
            <div className="flex gap-2">
              <input required type="number" step="0.01" className="input" value={form.allowed_laytime_value}
                onChange={(e) => setForm({ ...form, allowed_laytime_value: e.target.value })} />
              <select className="input" value={form.allowed_laytime_unit}
                onChange={(e) => setForm({ ...form, allowed_laytime_unit: e.target.value })}>
                <option value="HOURS">Hours</option>
                <option value="RUNNING_DAYS">Running Days</option>
              </select>
            </div>
          </Field>
          <Field label="NOR Allowance (hours)">
            <input required type="number" step="0.5" className="input" value={form.nor_allowance_hours}
              onChange={(e) => setForm({ ...form, nor_allowance_hours: e.target.value })} />
          </Field>
          <Field label="Demurrage Rate (per day)">
            <div className="flex gap-2">
              <input required type="number" step="0.01" className="input" value={form.demurrage_rate_value}
                onChange={(e) => setForm({ ...form, demurrage_rate_value: e.target.value })} />
              <input className="input w-24" value={form.currency}
                onChange={(e) => setForm({ ...form, currency: e.target.value })} />
            </div>
          </Field>
          <Field label="Created By (your email)">
            <input className="input" value={form.created_by}
              onChange={(e) => setForm({ ...form, created_by: e.target.value })} />
          </Field>
          <div className="col-span-2 flex justify-end">
            <button
              type="submit"
              disabled={submitting}
              className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
            >
              {submitting ? "Creando…" : "Crear Voyage"}
            </button>
          </div>
        </form>
      )}

      <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white shadow-sm">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-3">Vessel</th>
              <th className="px-4 py-3">Voyage</th>
              <th className="px-4 py-3">Counterparty</th>
              <th className="px-4 py-3">Port</th>
              <th className="px-4 py-3">Allowed Laytime</th>
              <th className="px-4 py-3">Demurrage Rate</th>
              <th className="px-4 py-3">State</th>
              <th className="px-4 py-3">Created</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {(voyages ?? []).map((v) => (
              <tr key={v.id} className="hover:bg-slate-50">
                <td className="px-4 py-3">
                  <Link href={`/voyages/${v.id}`} className="font-medium text-slate-900 hover:underline">
                    {v.vessel_name}
                  </Link>
                </td>
                <td className="px-4 py-3 text-slate-600">{v.voyage_number}</td>
                <td className="px-4 py-3 text-slate-600">{v.counterparty ?? "—"}</td>
                <td className="px-4 py-3 text-slate-600">{v.load_port ?? v.discharge_port ?? "—"}</td>
                <td className="px-4 py-3 text-slate-600">
                  {v.allowed_laytime_value} {v.allowed_laytime_unit}
                </td>
                <td className="px-4 py-3 text-slate-600">{formatMoney(v.demurrage_rate_value, v.currency)}/day</td>
                <td className="px-4 py-3">
                  <span className="rounded-full bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700">
                    {v.workflow_state}
                  </span>
                </td>
                <td className="px-4 py-3 text-slate-500">{formatDateTime(v.created_at)}</td>
              </tr>
            ))}
            {voyages !== null && voyages.length === 0 && (
              <tr>
                <td colSpan={8} className="px-4 py-8 text-center text-slate-400">
                  No hay voyages todavía. Crea el primero.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </main>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1 text-sm">
      <span className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</span>
      {children}
    </label>
  );
}
