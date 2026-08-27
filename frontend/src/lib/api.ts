import type {
  CalculationVersion,
  DocumentOut,
  ExplanationResult,
  SOFEvent,
  Voyage,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }), ...init?.headers },
    cache: "no-store",
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  listVoyages: () => request<Voyage[]>("/voyages"),
  getVoyage: (id: string) => request<Voyage>(`/voyages/${id}`),
  createVoyage: (payload: Record<string, unknown>) =>
    request<Voyage>("/voyages", { method: "POST", body: JSON.stringify(payload) }),

  listSofEvents: (voyageId: string) => request<SOFEvent[]>(`/voyages/${voyageId}/sof-events`),
  createSofEvent: (voyageId: string, payload: Record<string, unknown>) =>
    request<SOFEvent>(`/voyages/${voyageId}/sof-events`, { method: "POST", body: JSON.stringify(payload) }),
  updateSofEvent: (voyageId: string, eventId: string, payload: Record<string, unknown>) =>
    request<SOFEvent>(`/voyages/${voyageId}/sof-events/${eventId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  listDocuments: (voyageId: string) => request<DocumentOut[]>(`/voyages/${voyageId}/documents`),
  uploadDocument: (voyageId: string, file: File, type: string) => {
    const form = new FormData();
    form.append("file", file);
    form.append("type", type);
    return request<{ document: DocumentOut; candidate_events_created: number }>(
      `/voyages/${voyageId}/documents`,
      { method: "POST", body: form }
    );
  },

  runCalculation: (voyageId: string, createdBy: string) =>
    request<CalculationVersion>(`/voyages/${voyageId}/calculations?created_by=${encodeURIComponent(createdBy)}`, {
      method: "POST",
    }),
  listCalculations: (voyageId: string) => request<CalculationVersion[]>(`/voyages/${voyageId}/calculations`),
  latestCalculation: (voyageId: string) => request<CalculationVersion>(`/voyages/${voyageId}/calculations/latest`),
  explainInterval: (voyageId: string, calculationId: string, index: number) =>
    request<ExplanationResult>(`/voyages/${voyageId}/calculations/${calculationId}/intervals/${index}/explanation`),

  createOverride: (voyageId: string, payload: Record<string, unknown>) =>
    request(`/voyages/${voyageId}/overrides`, { method: "POST", body: JSON.stringify(payload) }),
};

export { API_URL };
