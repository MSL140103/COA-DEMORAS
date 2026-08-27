"use client";

import { useRef, useState } from "react";
import { api } from "@/lib/api";

export default function DocumentUpload({ voyageId, onUploaded }: { voyageId: string; onUploaded: () => void }) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [docType, setDocType] = useState("SOF");
  const inputRef = useRef<HTMLInputElement>(null);

  const onFile = async (file: File) => {
    setBusy(true);
    setMessage(null);
    try {
      const result = await api.uploadDocument(voyageId, file, docType);
      setMessage(
        docType === "SOF"
          ? `"${file.name}" procesado — ${result.candidate_events_created} eventos candidatos creados (requieren revisión).`
          : `"${file.name}" subido y texto extraído.`
      );
      onUploaded();
    } catch (err) {
      setMessage(`Error: ${String(err)}`);
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = "";
    }
  };

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <h2 className="mb-3 text-sm font-semibold text-slate-900">Documents</h2>
      <div className="flex flex-wrap items-center gap-3">
        <select className="input w-40" value={docType} onChange={(e) => setDocType(e.target.value)}>
          <option value="SOF">Statement of Facts</option>
          <option value="CHARTER_PARTY">Charter Party</option>
          <option value="SHELLVOY">Shellvoy</option>
          <option value="COA">COA</option>
          <option value="RECAP">RECAP</option>
          <option value="CP_CALCULATION">CP Calculation</option>
          <option value="OTHER">Other</option>
        </select>
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf"
          disabled={busy}
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) onFile(file);
          }}
          className="text-sm text-slate-600 file:mr-3 file:rounded-md file:border-0 file:bg-slate-900 file:px-3 file:py-2 file:text-xs file:font-medium file:text-white hover:file:bg-slate-700"
        />
        {busy && <span className="text-xs text-slate-400">Procesando…</span>}
      </div>
      {message && <p className="mt-2 text-xs text-slate-500">{message}</p>}
      <p className="mt-2 text-xs text-slate-400">
        Extracción nativa de texto + heurística determinística (sin IA) para MVP1 — cada evento creado queda en{" "}
        <span className="font-mono">NEEDS_REVIEW</span> hasta confirmación humana.
      </p>
    </div>
  );
}
