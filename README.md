# Sistema Inteligente de Laytime & Demurrage

MVP1 del sistema descrito en [`docs/architecture/SYSTEM_ARCHITECTURE.md`](docs/architecture/SYSTEM_ARCHITECTURE.md).
Motor de cálculo de laytime/demurrage 100% determinístico (sin IA en la matemática),
con timeline atómico, prevención estructural de doble descuento, versionado de
cálculos y overrides manuales auditables.

## Qué incluye este MVP1

- **Backend** (`backend/`, FastAPI + PostgreSQL): motor de dominio puro
  (`app/domain`) — facts, rules engine, atomic timeline engine, laytime/demurrage
  calculation, no-double-deduction integrity check — más la API REST y persistencia.
- **Extracción de SOF** (`backend/app/extraction`): extracción nativa de texto de PDF
  (pdfplumber) + un extractor heurístico determinístico basado en palabras clave
  (sin dependencia de un proveedor de IA). Cada evento extraído queda en
  `NEEDS_REVIEW` — nunca se usa en un cálculo sin confirmación humana.
- **Frontend** (`frontend/`, Next.js + TypeScript + Tailwind): creación de voyages,
  tabla editable de eventos SOF, carga de documentos, ejecución de cálculo, timeline
  con panel de explicación clickeable (evidencia SOF → regla → cláusula → impacto) y
  formulario de override manual.
- **42 tests unitarios** (`backend/tests/unit`) cubriendo el subconjunto de MVP1 de
  los 30 casos de prueba del brief: NOR+6, weather 50%, shifting+weather sin doble
  descuento, agotamiento de laytime a mitad de intervalo, demurrage full→half rate,
  override manual, y reproducibilidad de cálculo.

Lo que **no** está en MVP1 (ver `docs/architecture/SYSTEM_ARCHITECTURE.md` sección
23-24 para el roadmap completo): extracción de cláusulas contractuales con IA,
Weather Engine completo (48h/72h, sealine, Pampilla), import de cálculos de CP,
Comparison/Counter workflow, Rule Management UI, roles/permisos granulares.

## Arquitectura del motor (por qué importa)

- `app/domain` no tiene **ninguna** dependencia de base de datos, red o IA. Es
  puro Python, 100% testeable con pytest, y es la única capa que hace matemática.
- La IA (cuando se agregue en MVP2+) solo puede vivir en `app/extraction`, detrás de
  la interfaz `SOFExtractor` — nunca puede decidir cuánto cuenta un período.
- Cada intervalo atómico (`AtomicInterval`) tiene exactamente un tratamiento final
  (`final_time_count_factor`) — la garantía de "no double deduction" es estructural,
  verificada activamente por `app/domain/timeline/integrity.py` en cada cálculo.

## Abrirla sin instalar nada (Render)

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/MSL140103/COA-DEMORAS)

Este repo incluye [`render.yaml`](render.yaml), que describe los 3 servicios
necesarios (Postgres + backend + frontend) para que Render los cree juntos. Pasos:

1. Entra a [render.com](https://render.com) y crea una cuenta gratis (con GitHub,
   sin descargar nada).
2. Click en el botón de arriba, o desde el dashboard: **New +** → **Blueprint** →
   selecciona el repo `MSL140103/COA-DEMORAS` → rama `claude/laytime-demurrage-system-tmbr5u`.
3. Render detecta `render.yaml` y muestra los 3 servicios a crear (`laytime-db`,
   `laytime-backend`, `laytime-frontend`) — click **Apply**.
4. Espera a que los 3 terminen de construirse (unos minutos la primera vez).
5. Abre la URL de `laytime-frontend` (algo como `https://laytime-frontend.onrender.com`)
   — esa es la app.

Notas del plan gratuito de Render: los servicios se "duermen" tras ~15 min sin uso
(la primera carga tras eso tarda 30-60s en despertar) y la base de datos gratuita
expira a los 90 días — para uso real conviene pasar a un plan pago antes de eso.

## Correr localmente

### Requisitos
- Python 3.11+
- Node.js 20+
- PostgreSQL 16 (local o vía Docker)

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

cp .env.example .env   # ajusta la URL de conexión si es necesario

# con Postgres corriendo localmente (db "laytime", user "laytime"):
alembic upgrade head

uvicorn app.main:app --reload --port 8000
```

Tests del motor de dominio (no requieren base de datos):

```bash
cd backend && source .venv/bin/activate
pytest tests/unit -v
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Abre http://localhost:3000 — por defecto ya apunta al backend en `localhost:8000`
(no necesitas configurar nada; ver `.env.local.example` si el backend corre en otro
puerto/host).

### Con Docker Compose (Postgres + backend + frontend)

```bash
docker compose up --build
```

## Flujo de uso (MVP1)

1. Crear un voyage (vessel, allowed laytime, demurrage rate, NOR allowance).
2. Subir un SOF en PDF — se extraen eventos candidatos automáticamente
   (`NEEDS_REVIEW`), o agregar eventos manualmente.
3. Revisar y **confirmar** cada evento en la tabla de SOF Events.
4. "Run Calculation" — construye el timeline atómico, calcula laytime y demurrage,
   verifica integridad (no double deduction).
5. Click en cualquier fila del timeline → panel de explicación completo (evidencia
   SOF, regla aplicada, regla(s) secundarias, razón, fuente contractual).
6. Si se necesita corregir un período: "Override this period" — crea una nueva
   versión del cálculo, preservando la sugerencia original del motor.

## Reglas base incluidas (provisionales)

`backend/app/domain/rules/seed.py` define un rule set mínimo (`NOR_ALLOWANCE` 6h,
`WEATHER_WINDOW` 50%, `SHIFTING_TREATMENT` 0%) marcado explícitamente como
`scope=MANUAL` con `source_note` indicando que son reglas provisionales sin cláusula
contractual real vinculada — por diseño (`RULE 4: NO RULE WITHOUT SOURCE`), el motor
nunca trata una regla sin fuente como si estuviera confirmada contractualmente.
Reemplazar por reglas reales (con `source_clause_id`) es trabajo de MVP2 (Contract
Clause Extraction).
