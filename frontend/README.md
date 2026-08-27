# Frontend — Laytime & Demurrage MVP1

Next.js (App Router) + TypeScript + Tailwind. See the [repo root README](../README.md)
for the full setup (backend + database) and usage flow.

```bash
npm install
cp .env.local.example .env.local
npm run dev
```

Talks to the FastAPI backend via `NEXT_PUBLIC_API_URL` (defaults to
`http://localhost:8000`).

## Structure

- `src/app` — routes: voyage list (`/`) and voyage detail (`/voyages/[id]`).
- `src/components` — `SofEventsTable`, `DocumentUpload`, `CalculationSummary`,
  `TimelineTable`, `ExplanationDrawer` (the click-a-rule traceability panel + manual
  override form).
- `src/lib` — typed API client, formatting helpers, the event category catalogue
  (mirrors `backend/app/domain/facts/models.py`).
