# Sistema Inteligente de Laytime & Demurrage — Arquitectura Propuesta (v0.1 — DRAFT PARA APROBACIÓN)

> Estado: **PENDIENTE DE APROBACIÓN**. Ningún código de aplicación debe escribirse hasta que este documento sea aprobado. Este documento responde a los 30 puntos solicitados. Cuando existe una interpretación contractual o de negocio dudosa, se marca explícitamente como **CONTRACTUAL DECISION REQUIRED** en lugar de asumirse.

## Cómo leer este documento

Cada sección explica **QUÉ** se propone y **POR QUÉ**, y cuando aplica, qué alternativas se descartaron y por qué. Las 10 Reglas Arquitectónicas Críticas (RULE 1–10 del brief) se usan como criterio de diseño en cada decisión: si una opción viola alguna, se descarta aunque sea más simple de implementar.

Convención de flags usadas en todo el documento:

- `CONTRACTUAL DECISION REQUIRED` — falta una decisión de negocio/legal antes de poder codificar esa regla con confianza.
- `OPEN DESIGN QUESTION` — decisión técnica razonable en cualquier dirección; se propone un default pero se pide confirmación.

---

## 1. Proposed System Architecture

### 1.1 Vista de capas

El sistema se organiza en las 11 capas que el brief exige (sección 73), implementadas como módulos con fronteras estrictas — cada capa solo puede llamar a la capa inmediatamente inferior, nunca saltarse capas ni tener dependencias circulares:

```
┌─────────────────────────────────────────────────────────────────┐
│  WORKFLOW LAYER            (estados del voyage, aprobaciones)    │
├─────────────────────────────────────────────────────────────────┤
│  DISPUTE / COUNTER ENGINE  (CP↔SW negociación, versionado)       │
├─────────────────────────────────────────────────────────────────┤
│  COMPARISON ENGINE         (CP vs SW, detección double deduction)│
├─────────────────────────────────────────────────────────────────┤
│  CALCULATION ENGINE        (laytime, demurrage — determinístico) │
├─────────────────────────────────────────────────────────────────┤
│  ATOMIC TIMELINE ENGINE    (intervalos atómicos, one-second rule)│
├─────────────────────────────────────────────────────────────────┤
│  RULES ENGINE              (evaluación de reglas versionadas)    │
├─────────────────────────────────────────────────────────────────┤
│  CONTRACT LAYER            (cláusulas, versiones, fuentes)       │
├─────────────────────────────────────────────────────────────────┤
│  FACTS LAYER               (eventos normalizados, confirmados)   │
├─────────────────────────────────────────────────────────────────┤
│  EXTRACTION LAYER           (IA: SOF/contract → candidatos)      │
├─────────────────────────────────────────────────────────────────┤
│  DOCUMENT LAYER             (ingesta, OCR, almacenamiento)       │
└─────────────────────────────────────────────────────────────────┘
                              │
                    AUDIT LAYER (transversal a todas)
```

**Por qué capas estrictas y no un monolito "por feature":** RULE 1, RULE 2 y RULE 8 (LLM no hace matemática final) solo se pueden garantizar si existe una frontera dura entre "lo que la IA propone" (Extraction Layer) y "lo que se calcula" (Calculation Engine). Si un desarrollador puede, por conveniencia, invocar al LLM directamente desde el Calculation Engine, la garantía se rompe silenciosamente con el tiempo. Las capas se implementan como paquetes Python separados con interfaces tipadas (Pydantic/dataclasses); el Calculation Engine y el Rules Engine **no tienen dependencia de red ni de ningún SDK de IA** — pueden ejecutarse sin conexión a internet y son 100% testeables con pytest puro.

### 1.2 Componentes técnicos

```
┌──────────────┐      ┌───────────────────┐      ┌──────────────────┐
│  Next.js/TS   │◄────►│  FastAPI (Python)  │◄────►│  PostgreSQL        │
│  Frontend     │ REST/│  API + Services    │      │  (fuente de verdad)│
│  (App Router) │ WS   │                    │      └──────────────────┘
└──────────────┘      │  - Extraction svc  │      ┌──────────────────┐
                       │  - Rules engine    │◄────►│  Object Storage    │
                       │  - Calc engine     │      │  (S3-compatible)   │
                       │  - Comparison eng. │      │  documentos/OCR     │
                       │  - Workflow svc    │      └──────────────────┘
                       │  - Audit svc       │      ┌──────────────────┐
                       └─────────┬──────────┘      │  Background worker  │
                                 │                  │  (Celery/RQ/Arq)    │
                                 ▼                  │  OCR, extracción IA │
                       ┌───────────────────┐        │  async, largo       │
                       │  LLM Provider      │        └──────────────────┘
                       │  (Claude API)      │
                       │  SOLO Extraction   │
                       │  Layer lo invoca   │
                       └───────────────────┘
```

**Por qué FastAPI + Python para todo el backend (no Node para el motor de cálculo):** el motor de cálculo debe ser auditable línea por línea por alguien que no es programador (un operador de laytime). Python con tipos explícitos (Decimal para dinero, no float) y librerías de fechas (pendulum/arrow) es el estándar de facto en aplicaciones marítimas/financieras y facilita que expertos de dominio revisen la lógica. Además unifica el lenguaje con la capa de IA (extracción), evitando duplicar modelos de datos en dos lenguajes.

**Por qué worker asíncrono separado:** OCR y llamadas a LLM pueden tardar segundos a minutos por documento. Correrlos en el request-response del API violaría UX y arriesgaría timeouts. El worker persiste resultados como "candidatos" (Extraction Layer) — nunca escribe directamente en Facts Layer ni en Calculation — para preservar Human-in-the-Loop (RULE, sección 2.2).

**Por qué Decimal, no float, en todo el dominio monetario y de tiempo:** errores de redondeo de punto flotante en montos de demurrage son inaceptables cuando se litiga por minutos. Todo el Calculation Engine usa `Decimal` de Python con precisión y modo de redondeo explícitos y documentados por regla (ej. redondeo a favor de qué parte, si aplica) — este es un punto que requiere `CONTRACTUAL DECISION REQUIRED`: la mayoría de charter parties no especifican el redondeo exacto de segundos/minutos residuales; se propone truncar a segundos y no redondear al alza/baja arbitrariamente, pero debe confirmarse contra la práctica de RT.

---

## 2. Detailed Data Model

Se muestran los campos principales de cada entidad de la sección 74 del brief. Todas las entidades con prefijo *Version* son **append-only** (nunca UPDATE destructivo, solo INSERT + puntero "current"), en cumplimiento de RULE 7 e ítem 2.5.

### 2.1 Núcleo de Voyage

```
Voyage
  id, vessel_name, imo_number, voyage_number,
  counterparty_id, sw_user_id, rt_organization,
  load_port, discharge_port, terminal, berth, country,
  operation_type [LOADING|DISCHARGING],
  laycan_from, laycan_to,
  allowed_laytime_value, allowed_laytime_unit [HOURS|RUNNING_DAYS|WEATHER_WORKING_DAYS...],
  demurrage_rate_type [FIXED_PDPRY|WORLDSCALE_PCT],
  demurrage_rate_value, currency,
  worldscale_percentage, worldscale_reference_id,
  daylight_restriction_id (nullable → PortCall-level, ver 2.2),
  sealine, mbm, lightering, lightening, transshipment (bool/enum YES|NO|UNKNOWN),
  applicable_rule_set_id, applicable_rule_set_version_id,
  workflow_state, comments,
  created_by, created_at, updated_at

PortCall
  id, voyage_id, sequence_no,
  port, terminal, berth, operation_type,
  daylight_restriction:
    enabled [YES|NO],
    start_time, end_time,
    applies_to_berthing, applies_to_unberthing,
    applies_to_inward_passage, applies_to_outward_passage,
    other_note, source_document_id, source_comment
```

**Por qué Daylight Restriction vive en PortCall y no en un catálogo global de terminales:** sección 6 del brief prohíbe explícitamente inferir la restricción por terminal. Modelarlo como configuración *del voyage/port call específico*, con su propia fuente documental, es la única forma de que dos voyages al mismo terminal en distintos años/contratos puedan tener tratamientos distintos sin que uno pise al otro.

### 2.2 Documentos y contratos

```
Document
  id, voyage_id, type [SOF|CHARTER_PARTY|SHELLVOY|COA|RECAP|ADDENDUM|
                        RIDER_CLAUSE|CP_CALCULATION|CP_COUNTER|EMAIL|
                        WORLDSCALE_INFO|SUPPORTING|OTHER],
  filename, storage_uri, mime_type, page_count,
  extraction_method [NATIVE_TEXT|OCR|MIXED],
  uploaded_by, uploaded_at, sha256_hash, status

ContractDocument   (especialización de Document para contratos)
  id, document_id, contract_family [SHELLVOY6|COA|RECAP|ADDENDUM|RIDER],
  parent_contract_document_id (nullable — p.ej. Addendum → CP base)

ContractClause
  id, contract_document_id, clause_number, clause_title,
  page_number, raw_text, normalized_text,
  extracted_topics[] [NOR|LAYCAN|WEATHER|DAYLIGHT|SHIFTING|
                       INWARD_PASSAGE|BUNKERING|VESSEL_OPS|AUTHORITIES|
                       STRIKES|BREAKDOWNS|DEMURRAGE|WORLDSCALE|POST_HOSE|
                       CARGO_DOCUMENTS|UNBERTHING|OTHER],
  extraction_confidence, status [SUGGESTED|CONFIRMED|REJECTED],
  confirmed_by, confirmed_at
```

**Por qué `raw_text` y `normalized_text` separados:** el texto crudo (con su formato de OCR, saltos de línea, numeración) es la evidencia legal citable; el texto normalizado es lo que usa el motor de búsqueda semántica de cláusulas (sección 61). Nunca deben confundirse — mostrar al usuario siempre `raw_text` bajo "Original Contract Text" (sección 59).

### 2.3 Facts Layer (eventos SOF)

```
SOFEvent
  id, port_call_id, document_id, page_number,
  event_category [ver catálogo sección 8 del brief, ~60 categorías],
  event_subtype (texto libre para variantes no catalogadas),
  start_time, end_time (nullable si es instantáneo),
  extracted_value (JSON: lo que la IA leyó, inmutable),
  corrected_value (JSON: valor actual tras revisión humana, nullable),
  source_text (cita textual del SOF),
  confidence_score, confidence_status [CONFIRMED|PROBABLE|UNKNOWN|
                                        CONFLICTING_INFORMATION|NEEDS_REVIEW],
  status [EXTRACTED|EDITED|CONFIRMED|REJECTED|SPLIT|MERGED],
  parent_event_id (para split/merge, ver 2.3.1),
  created_at

EventEvidence   (append-only — historial de cada corrección, sección 9)
  id, sof_event_id, field_changed,
  previous_value, new_value, changed_by, changed_at,
  reason, document_id, page_number
```

**2.3.1 Split / Merge sin pérdida de auditoría:** cuando el usuario divide un evento (p.ej. "Bad Weather 08:00–18:00" en dos), se crean nuevos `SOFEvent` con `parent_event_id` apuntando al original, y el original se marca `status=SPLIT` (nunca se borra). Un merge crea un nuevo evento con `parent_event_id` múltiple vía tabla puente `SOFEventMerge(child_event_id, source_event_id)`. Esto preserva sección 53 (reproducibilidad histórica): un cálculo antiguo referenciaba el evento original y debe seguir siendo reconstruible.

### 2.4 Rules Engine

```
RuleDefinition            (identidad estable de la regla, ej. "NOR_ALLOWANCE")
  id, code, name, description, category

RuleVersion               (append-only, sección 44-45)
  id, rule_definition_id, version_no,
  conditions (JSON — ver 11. Rules Engine Design),
  exceptions (JSON),
  parameters (JSON — ej. {"allowance_hours": 6}),
  time_count_factor, demurrage_rate_factor,
  priority, scope [GLOBAL|CONTRACT|COA|RECAP|COUNTERPARTY|COUNTRY|
                    PORT|TERMINAL|VOYAGE|MANUAL],
  scope_ref_id (nullable — a qué COA/puerto/voyage aplica si scope != GLOBAL),
  effective_from, effective_to,
  source_document_id, source_clause_id, source_page,
  status [DRAFT|TESTING|ACTIVE|INACTIVE|SUPERSEDED|ARCHIVED],
  supersedes_version_id (nullable),
  requires_manual_confirmation,
  created_by, created_at

RuleSet
  id, name, description

RuleSetVersion             (append-only — snapshot inmutable de qué RuleVersions componen el set)
  id, rule_set_id, version_no,
  rule_version_ids[] (snapshot congelado — sección 53),
  effective_from, effective_to, status, created_by, created_at

VoyageRuleOverride          (sección 47)
  id, voyage_id, base_rule_version_id, override_rule_version_id,
  reason, approved_by, created_at

RuleConflict                (sección 28, 50)
  id, voyage_id, clause_a_id, clause_b_id,
  document_a_id, document_b_id, page_a, page_b,
  description, potential_impact,
  resolution [nullable hasta decidir], resolved_by, resolved_at, resolution_reason
```

**Por qué `RuleSetVersion` congela una *lista de IDs de RuleVersion* en vez de apuntar a "la versión activa en ese momento":** si mañana se activa `CONOCO_WEATHER V2`, cualquier `RuleSetVersion` ya usado en un cálculo aprobado debe seguir apuntando a V1 para siempre (RULE 7). Congelar la lista de IDs explícitamente, en vez de resolver "activa en fecha X" dinámicamente, hace la reproducibilidad *estructuralmente imposible de romper* incluso si alguien más tarde cambia `effective_to` de una regla antigua por error.

### 2.5 Atomic Timeline / Calculation

```
AtomicInterval               (ver sección 8 de este documento — Atomic Timeline Engine)
  id, port_call_id, calculation_version_id,
  interval_start, interval_end,
  active_event_ids[] (SOFEvent.id),
  matched_rule_version_ids[],
  primary_rule_version_id,
  secondary_rule_version_ids[],
  final_time_count_factor, final_demurrage_rate_factor,
  decision_reason (texto generado — sección 39),
  requires_manual_review (bool)

LaytimePeriod                 (agregación de AtomicIntervals contiguos con mismo tratamiento —
                                para presentación en la tabla de sección 63, no para el cómputo)
  id, calculation_version_id, from_time, to_time, duration,
  event_summary, count_pct, rate_pct, counted_time, deducted_time,
  primary_rule_version_id

Calculation
  id, voyage_id, kind [SW|CP_IMPORTED]

CalculationVersion            (append-only, sección 53 — snapshot total reproducible)
  id, calculation_id, version_no,
  event_snapshot_ids[] (SOFEvent versions usadas),
  rule_set_version_id,
  contract_document_versions[] (si los contratos tienen versión),
  manual_overrides[] (ManualOverride.id aplicados),
  calculation_engine_version (string, ej. git sha / semver del engine),
  results (JSON — ver sección 64: allowed laytime, used, demurrage, etc.),
  status [DRAFT|CALCULATED|APPROVED|SUPERSEDED],
  created_by, created_at
```

**Por qué `AtomicInterval` y `LaytimePeriod` son entidades separadas:** `AtomicInterval` es la unidad *atómica* donde vive la garantía "one second → one treatment" (RULE 1) — no se puede fusionar sin perder la trazabilidad de por qué cada segundo tiene ese tratamiento. `LaytimePeriod` es una vista de presentación (agrupa intervalos atómicos contiguos con el mismo `primary_rule_version_id` y factores idénticos) para no mostrarle al usuario una tabla de 500 filas de segundos. Es un derivado calculado, nunca la fuente de verdad — así la UI puede tener distintos niveles de agregación sin arriesgar el double-deduction guard.

### 2.6 CP / Comparison / Dispute

```
CPSubmission
  id, voyage_id, document_id, submission_type [CP_CALCULATION|CP_COUNTER],
  round_no,
  extracted_fields (JSON — NOR, commencement, allowed laytime, deductions[], etc.),
  status [EXTRACTED|REVIEWED|CONFIRMED]

Comparison
  id, sw_calculation_version_id, cp_submission_id,
  concept_diffs (JSON — tabla sección 66),
  period_diffs[] (ver PeriodDifference),
  overall_status [MATCH|DIFFERENCES_FOUND]

PeriodDifference
  id, comparison_id,
  from_time, to_time,
  cp_position, sw_position, cp_reasoning, sw_reasoning,
  time_difference, applicable_rule_version_id,
  financial_impact,
  potential_double_deduction (bool), double_deduction_detail (JSON)

Dispute
  id, voyage_id, comparison_id, status

Counter
  id, dispute_id, round_no, direction [SW_TO_CP|CP_TO_SW],
  period_difference_id,
  position, reasoning, supporting_document_ids[],
  financial_impact,
  status [OPEN|COUNTER_SENT|CP_REPLIED|ACCEPTED_BY_CP|ACCEPTED_BY_SW|
          REJECTED|AGREED],
  created_by, created_at
```

### 2.7 Overrides, Audit, soporte

```
ManualOverride
  id, target_type [SOF_EVENT|ATOMIC_INTERVAL|RULE_APPLICATION|
                    CP_EXTRACTED_FIELD|OTHER],
  target_id,
  original_value (JSON, preservado siempre), new_value (JSON),
  reason, supporting_clause_id, comment,
  created_by, created_at,
  superseded_by (nullable — un override puede ser reemplazado por otro override, nunca borrado)

AuditLog
  id, entity_type, entity_id, user_id, timestamp,
  field, previous_value, new_value, reason,
  time_impact, financial_impact,
  rule_version_id, calculation_version_id

WeatherEvent        (especialización de SOFEvent con campos propios de sección 30)
  id, sof_event_id, cause, cargo_affected, berthing_affected,
  unberthing_affected, port_closed, hours_since_nor,
  within_48h, within_72h, via_sealine, pampilla_exception,
  lightering, before_demurrage, on_demurrage

RateDefinition
  id, voyage_id, rate_type [FIXED|WORLDSCALE], value, currency, effective_from

WorldscaleReference
  id, ws_year, vessel_size_category, route, flat_rate_source, flat_rate_value,
  source_document_id, source_page

User
  id, name, email, role [SW_OPERATOR|SW_SUPERVISOR|RULES_ADMIN|VIEWER|ADMIN],
  organization
```

**Por qué `ManualOverride` es genérico (`target_type`/`target_id`) en vez de una tabla por tipo de override:** las secciones 76 y RULE 9 exigen que *ningún* override se pierda o se sobrescriba silenciosamente, sin importar sobre qué campo se aplique (un evento, un intervalo, incluso un campo extraído de CP). Una tabla polimórfica única permite que el Audit Layer tenga **un solo lugar** donde consultar "¿qué overrides existen para este voyage?" sin tener que hacer UNION de N tablas y arriesgar olvidar una en un reporte de auditoría.

---

## 3. Database Relationships

```
Voyage 1───* PortCall
Voyage 1───* Document
Voyage 1───1 RuleSetVersion (applicable_rule_set_version_id)
Voyage 1───* VoyageRuleOverride
Voyage 1───* RuleConflict

Document 1───* ContractClause          (vía ContractDocument)
Document 1───* SOFEvent                (source)
Document 1───* CPSubmission

PortCall 1───* SOFEvent
SOFEvent 1───* EventEvidence
SOFEvent 1───* SOFEvent (parent_event_id — split/merge)

RuleDefinition 1───* RuleVersion
RuleVersion *───* RuleSetVersion        (vía tabla puente rule_set_version_members,
                                          congelada al crear el RuleSetVersion)
RuleVersion 1───* RuleApplication       (uso real en un AtomicInterval — ver abajo)
RuleVersion 1───1 ContractClause        (source_clause_id — obligatorio salvo scope=MANUAL,
                                          ver sección 56 "NO RULE WITHOUT SOURCE")

Calculation 1───* CalculationVersion
CalculationVersion 1───* AtomicInterval
CalculationVersion 1───* LaytimePeriod
CalculationVersion *───1 RuleSetVersion
CalculationVersion *───* ManualOverride (aplicados en esa versión)

AtomicInterval *───* SOFEvent            (active_event_ids)
AtomicInterval *───* RuleVersion         (matched_rule_version_ids)
AtomicInterval *───1 RuleVersion         (primary_rule_version_id)

Comparison 1───1 CalculationVersion (SW)
Comparison 1───1 CPSubmission (CP)
Comparison 1───* PeriodDifference
PeriodDifference 1───0..1 Dispute
Dispute 1───* Counter

Todo lo anterior 1───* AuditLog          (entity_type/entity_id genérico)
```

**Relación crítica a resaltar — `RuleApplication`:** se introduce una tabla explícita (no solo el FK `primary_rule_version_id` en `AtomicInterval`) para registrar **cada** regla que compitió por un intervalo, no solo la ganadora:

```
RuleApplication
  id, atomic_interval_id, rule_version_id,
  matched (bool), is_primary (bool),
  evaluation_trace (JSON: qué condiciones se evaluaron y su resultado),
  precedence_reason (por qué ganó o perdió frente a otras)
```

**Por qué:** sección 39 exige mostrar "Secondary Events" y su razón de no aplicar (double deduction guard). Sin `RuleApplication`, reconstruir "qué reglas hicieron match pero perdieron, y por qué" requeriría re-ejecutar el motor — lo cual rompe la reproducibilidad histórica si el motor cambia de versión. Persistir el *trace* de evaluación es lo que permite responder en 1 clic la pregunta de sección 81 ("¿por qué no descontamos weather aquí?") sin recalcular nada.

### 3.1 Integridad referencial y reglas de negocio a nivel DB

- Toda tabla `*Version` es **INSERT-only** a nivel de aplicación; se refuerza con un trigger de Postgres que rechaza `UPDATE`/`DELETE` salvo por un rol de sistema restringido (para GDPR/legal holds, no para uso normal).
- `RuleVersion.source_clause_id` es `NOT NULL` cuando `scope != 'MANUAL'` (constraint a nivel de aplicación + check de integridad en el servicio de activación) — materializa RULE 4 en el modelo de datos, no solo en el UI.
- Constraint de integridad temporal en `AtomicInterval`: para un mismo `calculation_version_id`, los intervalos deben ser **contiguos y no solapados** (`interval_end[i] == interval_start[i+1]`), validado por un job de integridad tras cada cálculo (sección 41).

---

## 4. Document Processing Architecture

```
Upload (UI) ──► Document Layer
                  │  guarda archivo en Object Storage (hash SHA-256 para dedupe)
                  │  crea Document(status=UPLOADED)
                  ▼
            Text Extraction Pipeline (worker async)
                  │
                  ├─ 1. Native text extraction
                  │     PDF: pdfplumber/pymupdf → texto + coordenadas por página
                  │     DOCX: python-docx
                  │     XLSX: openpyxl (para CP calculations en Excel)
                  │
                  ├─ 2. ¿Cobertura de texto nativo suficiente? (heurística: 
                  │     % de página con texto extraído / densidad esperada)
                  │        SI → skip OCR
                  │        NO (escaneado / imagen) → OCR (Tesseract u OCR de proveedor cloud)
                  │
                  ├─ 3. Normalización: unifica en un documento intermedio
                  │     "PageText" con {page_no, text, bbox_map, source=[NATIVE|OCR]}
                  │
                  └─► Document.status = TEXT_READY
```

**Por qué "native text first, OCR only if needed" (sección 4 del brief):** OCR introduce errores de reconocimiento (fechas, horas, números — exactamente los datos más sensibles del dominio). El texto nativo de un PDF generado digitalmente es 100% exacto carácter por carácter. Forzar OCR siempre degradaría la calidad de extracción sin necesidad. La heurística de cobertura (paso 2) evita el caso mixto (PDF escaneado con una capa de texto OCR de mala calidad ya embebida) tratándolo como "necesita OCR real" si la densidad de texto nativo es sospechosamente baja o contiene caracteres de reemplazo.

**`bbox_map` (coordenadas por palabra/línea):** se persiste para poder implementar sección 60 "VIEW IN CONTRACT" — resaltar el texto exacto en la página exacta requiere saber dónde está cada palabra, no solo el texto plano.

**Manejo de Excel para CP Calculations:** los cálculos de contraparte suelen llegar como Excel con fórmulas y layouts variables. Se trata como un extractor especializado (sección 18 — CP Import), no genérico: primero se intenta un parser estructural basado en patrones comunes de laytime sheets (columnas Date/Time/Event/Remarks), y si falla, se degrada a extracción asistida por IA sobre el texto tabular, siempre pidiendo confirmación humana (nunca se auto-confirma un CP import).

---

## 5. SOF Extraction Design

```
PageText[] ──► LLM Extraction (Claude, structured output / tool-use JSON schema)
                  │
                  │  Prompt: catálogo cerrado de event_category (sección 8) +
                  │  reglas de equivalencia semántica (Anchor Aweigh = Anchor Up = Heave Up Anchor)
                  │  + instrucción explícita: "extract only, do not interpret contractually"
                  │
                  ▼
        SOFEvent[] candidatos (status=EXTRACTED, confidence_score, confidence_status)
                  │
                  ▼
        Deduplication & conflict pass (determinístico, no IA):
          - mismo event_category + timestamps solapados en distintas páginas → CONFLICTING_INFORMATION
          - eventos sin par (ej. "Commenced Loading" sin "Completed Loading") → NEEDS_REVIEW
                  │
                  ▼
        Human Review Table (sección 9) ── nunca se salta este paso
```

**Diseño del prompt de extracción — principios:**

1. **Salida estructurada obligatoria** (JSON Schema / tool-use de Claude), no texto libre parseado con regex — reduce alucinación de formato y permite validación automática de tipos (timestamps ISO8601, categorías del enum cerrado).
2. **Catálogo cerrado + campo `event_subtype` libre**: si el modelo encuentra un evento que no calza en el catálogo de ~60 categorías, debe usar `event_category=OTHER` + `event_subtype` descriptivo, nunca inventar una categoría nueva silenciosamente. Esto evita que categorías "fantasma" contaminen el Rules Engine (que hace match por categoría exacta).
3. **Confidence por campo, no solo por evento**: fecha, hora y categoría pueden tener confidence distinto (ej. "NOR Tendered" con hora clara 99%, pero la categoría exacta —¿es NOR o es un email de aviso previo?— 60%). El modelo reporta un `field_confidences` JSON además del `confidence_score` agregado.
4. **Cita obligatoria (`source_text`)**: cada evento debe venir con el fragmento textual exacto de donde se extrajo. Un evento sin `source_text` se marca automáticamente `NEEDS_REVIEW` — es una validación determinística post-LLM, no algo que se le pida "por favor" al modelo.
5. **Equivalencias semánticas como tabla de datos, no como conocimiento implícito del prompt**: se mantiene un `EventSynonymMap` versionado (mismo patrón que Rules) para que agregar "Heave Anchor" como sinónimo de "Anchor Aweigh" sea un cambio de datos, no un cambio de prompt/código.

**`CONTRACTUAL DECISION REQUIRED` — no aplica aquí (esta capa es puramente factual), pero nota de diseño:** la extracción **nunca** decide si un evento "cuenta" o no; eso es 100% responsabilidad del Rules Engine. El prompt está explícitamente instruido a no emitir juicios contractuales (RULE 8, RULE 5 — facts/rules separation).

---

## 6. Contract Clause Extraction Design

Mismo patrón de pipeline que SOF (documento → texto nativo/OCR → LLM estructurado → revisión humana), pero con salida distinta:

```
ContractDocument ──► Clause Segmentation (determinístico + IA asistida)
                        │  detecta numeración de cláusulas (regex sobre patrones comunes:
                        │  "Clause 15", "15.", "(a)", roman numerals) + fallback IA para
                        │  layouts no estándar (RECAPs en formato de email/telex)
                        ▼
                  ContractClause[] (raw_text, page_number, clause_number)
                        │
                        ▼
                  Topic Classification (IA, multi-label sobre catálogo cerrado sección 55)
                        │
                        ▼
                  Rule Suggestion (IA propone: rule_definition candidata, parámetros
                  extraídos ej. "6 hours" → allowance_hours=6, factor "50%" → 0.5)
                        │
                        ▼
                  Human Review ──► si se aprueba: crea RuleVersion(status=DRAFT,
                                    source_clause_id=<esta cláusula>)
                        │
                        ▼
                  Activation (acción humana separada, sección 52 — DRAFT nunca calcula)
```

**Por qué "Rule Suggestion" es un paso separado de "Topic Classification":** clasificar que una cláusula "habla de weather" es un problema de clasificación de texto relativamente confiable. Proponer *los parámetros exactos* (¿50% o 100%? ¿48h o 72h? ¿aplica antes o después de demurrage?) es donde el riesgo de alucinación es mayor y donde el brief es más enfático (secciones 24, 26-29) en que no se puede asumir. Separar los pasos permite que un usuario acepte la clasificación de tópico pero rechace/edite completamente los parámetros sugeridos, y que el sistema muestre el nivel de confianza de cada uno independientemente.

**Manejo de jerarquía documental (Addendum modifica RECAP modifica COA modifica Shellvoy base):** `ContractDocument.parent_contract_document_id` permite construir la cadena, pero la **resolución de precedencia real** (qué cláusula gana cuando dos documentos hablan del mismo tema) es responsabilidad del Rules Engine vía `priority` + scope, nunca inferida automáticamente de la jerarquía documental — ver sección 15 de este documento (Rule Precedence).

`CONTRACTUAL DECISION REQUIRED`: no existe un estándar universal de que "Addendum > RECAP > COA > Rider > Shellvoy Base" sea siempre correcto (el brief mismo lo advierte en sección 50). El sistema debe permitir configurar la jerarquía **por relación de contratos específica**, y cuando dos cláusulas de igual precedencia declarada entren en conflicto, debe generar un `RuleConflict` en vez de decidir.

---

## 7. Facts Normalization Model

Objetivo: convertir eventos extraídos (con confidence variable, posibles duplicados, timestamps en formatos distintos) en un set de `SOFEvent` **confirmados** que alimentan el Atomic Timeline Engine.

```
Normalización determinística (no IA) aplicada tras cada edición humana:
  1. Timezone normalization: todo timestamp se almacena en UTC + se guarda el
     offset/timezone original del puerto para mostrarlo en la UI en hora local.
     CONTRACTUAL DECISION REQUIRED: ¿laytime se calcula en hora local del puerto
     o en una zona horaria fija del contrato? Shellvoy no siempre lo especifica
     explícitamente; se propone default = hora local del puerto de la operación,
     pero debe confirmarse, especialmente para voyages que cruzan medianoche con
     cambio de DST.
  2. Ordenamiento cronológico y detección de secuencias imposibles
     (ej. "Completed Loading" antes de "Commenced Loading" → NEEDS_REVIEW,
     bloquea confirmación hasta resolver).
  3. Cálculo de duración para eventos de rango (start/end) vs. eventos
     instantáneos (solo un timestamp, duración=0, usados como marcadores/boundary).
  4. Un evento solo pasa a status=CONFIRMED por acción humana explícita
     (botón "Confirm" en la tabla de sección 9) — nunca automáticamente,
     ni siquiera con confidence=100%.
```

**Por qué la normalización es determinística y separada de la extracción IA:** si el timezone o el ordenamiento se resolvieran "dentro" del LLM, dos extracciones del mismo documento en momentos distintos podrían dar resultados de normalización ligeramente distintos (no determinismo del LLM). Mover esto a código determinístico garantiza que, dado el mismo set de eventos confirmados, la normalización siempre produce el mismo resultado — precondición para RULE 7.

**`FACTS ≠ RULES` en el modelo:** nótese que `SOFEvent` (sección 2.3) no tiene ningún campo de "count %" ni "treatment". Esa separación de columnas — no solo de capas de código — es deliberada: es estructuralmente imposible que alguien escriba "Bad Weather, 50%" directamente en la tabla de facts. El % vive únicamente en `AtomicInterval.final_time_count_factor`, derivado de `RuleVersion`, nunca en `SOFEvent`.

---

## 8. Atomic Timeline Engine Design

Implementa literalmente el algoritmo de secciones 36-39 del brief.

```python
# Pseudocódigo determinístico — sin IA, 100% testeable

def build_atomic_timeline(events: list[SOFEvent], rule_set_version: RuleSetVersion,
                           port_call: PortCall) -> list[AtomicInterval]:
    # 1. Recolectar todos los boundaries (start y end de cada evento confirmado,
    #    más boundaries estructurales: NOR+6, laycan start, demurrage commencement
    #    provisional, weather-window edges de 48h/72h desde NOR, daylight windows)
    boundaries = sorted(set(collect_all_boundaries(events, rule_set_version, port_call)))

    intervals = []
    for start, end in pairwise(boundaries):
        if start == end:
            continue
        active_events = [e for e in events if e.overlaps(start, end)]
        matches = evaluate_all_rules(active_events, rule_set_version, context=(start, end))
        primary, secondary = resolve_precedence(matches)   # ver sección 15
        intervals.append(AtomicInterval(
            interval_start=start, interval_end=end,
            active_event_ids=[e.id for e in active_events],
            matched_rule_version_ids=[m.rule_version_id for m in matches],
            primary_rule_version_id=primary.rule_version_id,
            secondary_rule_version_ids=[m.rule_version_id for m in secondary],
            final_time_count_factor=primary.time_count_factor,
            final_demurrage_rate_factor=primary.demurrage_rate_factor,
            decision_reason=render_reason(primary, secondary, active_events),
        ))
    return intervals
```

**Por qué recolectar boundaries "estructurales" (weather-window de 48h/72h, daylight) y no solo boundaries de eventos SOF:** una regla puede cambiar de tratamiento **en un instante que no corresponde a ningún evento SOF** (ej. a las 72h exactas desde NOR, sin que ocurra nada físico en ese momento). Sección 31 del brief exige dividir automáticamente un evento que cruza ese límite. Si el boundary no se agrega explícitamente a la lista, el intervalo atómico "se saltaría" ese cambio de regla. Estos boundaries estructurales se calculan primero (son función pura de `NOR_time + rule.parameters`), y se tratan como "boundaries virtuales" sin necesidad de crear un `SOFEvent` falso para representarlos.

**Complejidad y rendimiento:** un voyage típico tiene decenas de eventos, no miles — construir intervalos atómicos por fuerza bruta (`O(n log n)` para ordenar boundaries, `O(n·m)` para evaluar reglas por intervalo contra el rule set) es más que suficiente; no se requiere optimización prematura. Se pone un límite razonable (ej. 10,000 intervalos) con alerta si se excede, como señal de datos anómalos más que de performance.

**Integrity check (sección 41) como parte del mismo engine, no un paso aparte:** tras construir los intervalos, un validador determinístico confirma `sum(interval durations) == gross_timeline_duration` y que no haya huecos ni solapes. Si falla, la `CalculationVersion` se marca con `CALCULATION INTEGRITY ERROR` y **no puede pasar a `APPROVED`** — se modela como un `status` bloqueante, no solo un warning visual.

---

## 9. Laytime Calculation Engine Design

Puramente aritmético sobre la lista de `AtomicInterval` ya resuelta — este motor **no evalúa reglas**, solo suma:

```python
def calculate_laytime(intervals: list[AtomicInterval], commencement: datetime,
                       allowed_laytime: Duration) -> LaytimeResult:
    cumulative = Decimal(0)
    demurrage_commencement = None
    for interval in intervals:
        if interval.interval_end <= commencement:
            continue  # antes de commencement, no cuenta aún
        elapsed = effective_duration(interval, commencement)  # recorta si el intervalo
                                                                # cruza el commencement
        counted = elapsed * interval.final_time_count_factor
        cumulative += counted
        interval.cumulative_counted_laytime = cumulative       # persistido para tabla sección 63
        if demurrage_commencement is None and cumulative >= allowed_laytime:
            demurrage_commencement = interpolate_crossing_point(interval, cumulative, allowed_laytime)
    return LaytimeResult(used_laytime=min(cumulative, allowed_laytime),
                          remaining_laytime=max(allowed_laytime - cumulative, 0),
                          excess_time=max(cumulative - allowed_laytime, 0),
                          demurrage_commencement=demurrage_commencement)
```

**Por qué `interpolate_crossing_point` y no simplemente "el intervalo donde se cruza":** el `Allowed Laytime` puede agotarse **a mitad de un intervalo atómico** (ej. intervalo de 3 horas al 100%, pero solo faltaban 47 minutos para agotar el allowed laytime). Sección 22 exige el timestamp *exacto*, no el intervalo. Esto implica que el mismo intervalo atómico puede estar "parte en laytime, parte en demurrage" — el motor debe soportar el split fraccional del intervalo solo para efectos de este cálculo (sin fragmentar el `AtomicInterval` persistido, cuya integridad como unidad de "one treatment" se mantiene; el split de agotamiento es una vista derivada del cálculo, documentada en `LaytimeResult`, no una reescritura del timeline).

**Commencement como resultado de un sub-cálculo, no un input manual:** el motor de commencement (NOR+6 vs. securely moored, "whichever occurs first" — sección 11) se modela como su propio sub-módulo determinístico que produce un `CommencementDetermination` con los candidatos, la regla aplicada y la selección — exactamente el formato de sección 11 del brief. Este resultado alimenta a `calculate_laytime` como el parámetro `commencement`.

`CONTRACTUAL DECISION REQUIRED` (unidad de allowed laytime): sección 5 permite `allowed_laytime_unit` como horas, running days, o *weather working days*. El tratamiento de "weather working days" (donde ciertos días, ej. domingos/feriados, no cuentan salvo que se use la carga) introduce una lógica de calendario adicional no detallada en el brief. Se propone soportarlo en el motor como un `calendar_rule` configurable por voyage (parámetro del Rule Set, no hardcodeado), pero su especificación exacta debe confirmarse antes de implementar MVP4+ (no bloquea MVP1, que puede asumir `HOURS` o `RUNNING_DAYS` simples).

---

## 10. Demurrage Calculation Engine Design

```python
def calculate_demurrage(intervals: list[AtomicInterval], demurrage_commencement: datetime,
                         rate: DemurrageRate) -> DemurrageResult:
    full_rate_time = half_rate_time = other_rate_time = Decimal(0)
    for interval in intervals:
        if interval.interval_end <= demurrage_commencement:
            continue
        on_demurrage_duration = effective_duration(interval, demurrage_commencement)
        rate_factor = interval.final_demurrage_rate_factor   # distinto de time_count_factor (sección 24)
        bucket = classify_rate_bucket(rate_factor)  # 1.0 → full, 0.5 → half, otro → other
        allocate(bucket, on_demurrage_duration, rate_factor)

    daily_rate = resolve_daily_rate(rate)  # FIXED o WORLDSCALE resuelto (sección 23)
    amount = (full_rate_time * daily_rate
              + half_rate_time * daily_rate * Decimal("0.5")
              + other_rate_time_weighted_amount)
    return DemurrageResult(...)
```

**Por qué `time_count_factor` y `demurrage_rate_factor` son campos separados en todo el sistema (no un solo "%"):** es el corazón de sección 24 (Shellvoy 15(2)). El mismo evento puede requerir que el tiempo *cuente* al 100% para efectos de determinar cuándo se agota el laytime, pero que la *tarifa* de demurrage aplicable a ese tiempo (si ya está en demurrage) sea 50%. Colapsar esto en un solo número haría estructuralmente imposible representar ese caso — es una decisión de modelo de datos, no solo de UI.

**Resolución de tarifa Worldscale (sección 23):** `resolve_daily_rate` para `WORLDSCALE_PCT` busca en `WorldscaleReference` por año/categoría de buque/ruta. Si no hay una referencia exacta y confirmada, el resultado es `UNKNOWN / REVIEW REQUIRED` (sección 2.7 del brief: no inventar) — el cálculo puede continuar mostrando tiempo pero el monto final queda bloqueado hasta que un usuario confirme la referencia Worldscale manualmente.

**Pro-rata de "running day or part thereof":** la cláusula citada en sección 22 dice "per running day or pro rata for part thereof" — esto es una decisión de redondeo de negocio, no técnica. `CONTRACTUAL DECISION REQUIRED`: ¿el pro-rata se calcula en fracciones exactas de día (ej. 0.734 días × rate/día) o hay una práctica de redondeo hacia arriba a la siguiente unidad (ej. cuartos de día)? Se propone default de fracción exacta (más defendible matemáticamente y lo más común en Shellvoy), pero debe confirmarse contra la práctica real de SW/RT antes de aprobar montos.

---

## 11. Rules Engine Design

### 11.1 Modelo de condiciones (Rule Builder — sección 48)

Las condiciones de una `RuleVersion` se almacenan como una expresión estructurada (JSON tipo árbol AST), no como código:

```json
{
  "all": [
    {"field": "event.category", "op": "eq", "value": "WEATHER"},
    {"field": "context.hours_since_nor", "op": "lte", "value": {"param": "weather_window_hours"}},
    {"field": "voyage.via_sealine", "op": "eq", "value": false}
  ]
}
```

con soporte de `all` (AND), `any` (OR), `not`, y operadores (`eq`, `neq`, `lte`, `gte`, `in`, `between`). Los `field` referencian un **contexto de evaluación** fijo y documentado (no arbitrario) que el Atomic Timeline Engine construye por intervalo: propiedades del/los evento(s) activo(s), propiedades del voyage, y variables derivadas (`hours_since_nor`, `is_before_demurrage`, `is_on_demurrage`, etc.).

**Por qué JSON-AST y no un DSL de texto libre ni Python evaluado dinámicamente:** 
1. *Seguridad*: nunca se ejecuta código arbitrario (`eval`) generado por reglas — elimina una clase entera de vulnerabilidades (RCE vía regla maliciosa).
2. *Editable visualmente*: sección 48 pide un Rule Builder visual futuro; un AST tipado mapea 1:1 a componentes de UI (dropdown de campo, dropdown de operador, input de valor) sin necesidad de parser.
3. *Testeable*: cada nodo del AST es una función pura evaluable independientemente en tests unitarios.

### 11.2 Motor de evaluación

```python
def evaluate_all_rules(active_events, rule_set_version, context) -> list[RuleMatch]:
    candidates = rule_set_version.rules_matching_category(active_events)
    matches = []
    for rule_version in candidates:
        if evaluate_condition_tree(rule_version.conditions, build_eval_context(active_events, context)):
            if not evaluate_condition_tree(rule_version.exceptions or NONE, ...):
                matches.append(RuleMatch(rule_version, ...))
    return matches
```

Cada evaluación se persiste como `RuleApplication.evaluation_trace` (sección 3 de este documento) — no solo el resultado, sino cada condición evaluada y su valor booleano, para que la explicación de sección 57-59 pueda mostrarse sin volver a ejecutar el motor.

### 11.3 Parametrización (sección 49)

Se prohíbe a nivel de convención de código (enforced en code review / linting de nombres) crear `RuleDefinition.code` del estilo `NOR_PLUS_6`, `NOR_PLUS_8`. El catálogo de `RuleDefinition` es un conjunto pequeño y estable de *tipos* de regla (`NOR_ALLOWANCE`, `WEATHER_WINDOW`, `POST_HOSE_ALLOWANCE`, `INWARD_PASSAGE_EXCLUSION`, `SHIFTING_TREATMENT`, `STRIKE_TREATMENT`, `UNALLOCATED_BEYOND_CONTROL`, etc.); toda la variación (6h vs 8h, 48h vs 72h) vive en `RuleVersion.parameters`.

---

## 12. Rule Versioning Design

Ya cubierto en el modelo de datos (sección 2.4) — se resumen aquí las invariantes operativas:

1. **Nunca UPDATE de una `RuleVersion` activa.** Editar una regla activa desde la UI crea una nueva `RuleVersion` (`version_no + 1`) con `status=DRAFT`, vinculada vía `supersedes_version_id`. La versión anterior permanece `ACTIVE` hasta que la nueva pase por `TESTING → ACTIVE` explícitamente (sección 52).
2. **Un `RuleSetVersion` es un snapshot congelado.** Activar una nueva `RuleVersion` no cambia automáticamente el `RuleSetVersion` que voyages existentes están usando — un usuario con permiso debe crear explícitamente un nuevo `RuleSetVersion` que la incluya y decidir a qué voyages futuros aplica.
3. **`effective_from`/`effective_to`** permiten reglas estacionales, pero **no determinan solas** qué versión usa un cálculo — eso lo fija el `RuleSetVersion` congelado en el `CalculationVersion` (evita que un cambio retroactivo de `effective_to` altere cálculos históricos — sección 44).

---

## 13. Rule Management Design

CRUD completo restringido a rol `RULES_ADMIN` (sección 27 — seguridad), con las siguientes operaciones sobre `RuleVersion` (sección 43):

| Acción | Efecto | Restricción |
|---|---|---|
| Create | nueva `RuleDefinition` + `RuleVersion(status=DRAFT)` | requiere `source_document_id`+`source_clause_id` o justificación explícita para `scope=MANUAL` |
| Edit | solo si `status=DRAFT` (edita in-place); si `ACTIVE`, crea nueva versión | — |
| Duplicate | clona una `RuleVersion` a `DRAFT` con nuevo `rule_definition_id` o como nueva versión | útil para adaptar una regla existente a otro puerto/contrato |
| Test | ejecuta contra un `RuleSimulator` (sección 51) sin afectar cálculos reales | requiere al menos un voyage/caso de prueba |
| Activate | `DRAFT/TESTING → ACTIVE`; si existe una versión `ACTIVE` previa del mismo `RuleDefinition` con solapamiento de `scope`, la mueve a `SUPERSEDED` | requiere confirmación explícita + comentario |
| Deactivate | `ACTIVE → INACTIVE` (deja de aplicar a cálculos nuevos; no afecta históricos) | — |
| Supersede | equivalente a Activate de una nueva versión | — |
| Archive | `INACTIVE/SUPERSEDED → ARCHIVED` (oculta de listados normales, nunca se borra) | — |

**UI de Rules Management** vive en la pantalla "Rules" por voyage (sección 75) y en una pantalla global de administración de reglas (fuera del contexto de un voyage específico) para gestionar el catálogo base.

---

## 14. Contractual Traceability Design

Implementa la cadena de sección 62 como una **vista materializada de consulta**, no como un proceso adicional — toda la información ya existe en el modelo de datos de la sección 2; esta sección describe cómo se ensambla para presentación:

```
GET /api/atomic-intervals/{id}/explanation
  →  {
       sof_evidence: [{event, source_document, page, source_text}, ...],
       fact: {category, start, end},
       atomic_interval: {start, end, active_events},
       matched_rules: [...],
       selected_rule: {rule_version, precedence_reason},
       contract_clause: {document, clause_number, page, raw_text, highlight_bbox},
       time_treatment: {count_pct, rate_pct},
       calculation: {elapsed, counted, deducted},
       financial_impact: {amount, currency}
     }
```

Este endpoint único alimenta tanto el "Clickable Rule" (sección 59) como el asistente de preguntas de sección 81 ("¿por qué descontamos estas 2 horas?") — la respuesta en lenguaje natural a esa pregunta es una **plantilla de texto determinística** rellenada con estos datos, no una llamada a un LLM en el momento de la consulta. Esto garantiza que la explicación sea siempre exacta y reproducible, y que no haya riesgo de que un LLM "explique mal" un cálculo ya determinístico.

**Por qué NO usar un LLM para generar la explicación en tiempo real:** aunque sería tentador pedirle a un LLM que redacte una explicación más natural, hacerlo introduciría una fuente no determinística sobre datos ya 100% conocidos — viola el espíritu de RULE 8 aunque técnicamente no sea "matemática". Se prefiere una plantilla de texto (con partes condicionales, ej. el párrafo de sección 81 sobre no-double-deduction) que es trivialmente testeable y auditable.

---

## 15. Rule Precedence Resolution

Cuando múltiples `RuleVersion` hacen match sobre el mismo `AtomicInterval` (sección 39, secondary events):

```python
def resolve_precedence(matches: list[RuleMatch]) -> tuple[RuleMatch, list[RuleMatch]]:
    if not matches:
        return DEFAULT_COUNT_RULE, []   # fallback: cuenta 100% si nada hace match — nunca "sin regla"
    if len(matches) == 1:
        return matches[0], []
    # 1. Mayor priority explícita gana
    ranked = sorted(matches, key=lambda m: (-m.rule_version.priority, m.rule_version.scope_specificity()))
    top_priority = ranked[0].rule_version.priority
    tied = [m for m in ranked if m.rule_version.priority == top_priority]
    if len(tied) == 1:
        return tied[0], ranked[1:]
    # 2. Empate en priority → scope más específico gana (VOYAGE > TERMINAL > PORT >
    #    COUNTRY > COUNTERPARTY > RECAP > COA > CONTRACT > GLOBAL)
    scope_ranked = sorted(tied, key=lambda m: SCOPE_SPECIFICITY[m.rule_version.scope])
    if scope_ranked[0].rule_version.scope != scope_ranked[1].rule_version.scope:
        return scope_ranked[0], [m for m in matches if m != scope_ranked[0]]
    # 3. Sigue empatado → NO SE DECIDE AUTOMÁTICAMENTE
    raise RuleConflictDetected(matches)   # crea RuleConflict, bloquea auto-cálculo del intervalo,
                                            # marca requires_manual_review=True
```

**Por qué existe un `DEFAULT_COUNT_RULE` fallback y no "sin regla = error":** un intervalo sin ninguna regla especial que le aplique (tiempo normal de carga, sin weather, sin shifting, etc.) es el caso más común — debe contar 100% por default contractual estándar de laytime. Este fallback en sí es una `RuleVersion` versionada normal (`scope=GLOBAL`, `priority` más baja posible) — no un caso especial en el código — para que quede sujeto a las mismas reglas de auditoría y trazabilidad que cualquier otra.

**Por qué un empate real dispara `RuleConflictDetected` en vez de "primera que matchea" o "orden alfabético":** RULE 10 exige explícitamente que los conflictos se señalicen, no se inventen. Elegir arbitrariamente por orden de inserción sería exactamente el tipo de decisión silenciosa que el brief prohíbe. La sección 39 (secondary events) NO es lo mismo que un empate de precedencia real: cuando hay jerarquía clara (ej. Shifting con priority explícita más alta que Weather), Weather se vuelve "secondary" correctamente sin necesidad de conflicto — el conflicto solo se dispara cuando el sistema *no puede* decidir con las reglas configuradas.

`CONTRACTUAL DECISION REQUIRED`: el orden de especificidad de scope propuesto arriba (`VOYAGE > TERMINAL > PORT > COUNTRY > COUNTERPARTY > RECAP > COA > CONTRACT > GLOBAL`) es un default razonable de "lo más específico gana", pero el brief (sección 50) advierte explícitamente que no debe asumirse una jerarquía como jurídicamente correcta. Se propone que este orden sea **configurable globalmente** (tabla `ScopePrecedenceConfig`, editable solo por `RULES_ADMIN`), con este orden como valor inicial sujeto a confirmación legal/comercial.

---

## 16. No Double Deduction Algorithm

Ya descrito estructuralmente en la sección 8 de este documento (Atomic Timeline). Se detalla aquí la garantía formal y su verificación:

**Garantía por construcción:** dado que `AtomicInterval` particiona el timeline en intervalos **disjuntos y contiguos** (nunca solapados, por construcción a partir de boundaries ordenados) y cada intervalo tiene **exactamente un** `final_time_count_factor`, es matemáticamente imposible que un mismo segundo reciba dos deducciones — no hay ningún paso del algoritmo que sume deducciones de múltiples reglas sobre el mismo rango de tiempo. La suma de sección 9 (`calculate_laytime`) itera intervalos disjuntos exactamente una vez cada uno.

**Verificación activa (defensa en profundidad, no solo confianza en el diseño):**

```python
def integrity_check(intervals: list[AtomicInterval], gross_start, gross_end) -> IntegrityResult:
    total = sum(i.duration for i in intervals)
    gross = gross_end - gross_start
    if total != gross:
        return IntegrityResult(ok=False, error="CALCULATION INTEGRITY ERROR — POSSIBLE DOUBLE DEDUCTION",
                                detail=f"sum(intervals)={total} != gross={gross}")
    for a, b in pairwise(sorted(intervals, key=lambda i: i.interval_start)):
        if a.interval_end != b.interval_start:
            return IntegrityResult(ok=False, error="GAP OR OVERLAP DETECTED", detail=(a, b))
    return IntegrityResult(ok=True)
```

Este check corre automáticamente después de **cada** construcción de `AtomicInterval[]` (no es opcional, no es solo para un botón de "validar") y su resultado se persiste en `CalculationVersion.integrity_status`. Una `CalculationVersion` con integridad fallida no puede transicionar a `status=APPROVED` — se aplica como constraint en el servicio de Workflow, no solo como advertencia visual.

**Detección de double deduction en el cálculo de CP (sección 40):** se aplica el *mismo* algoritmo de intervalos atómicos sobre los `CPSubmission.extracted_fields` reconstruidos (ranges de deducción que CP reporta), no un algoritmo distinto — reutilizar el motor de intervalos atómicos como herramienta de auditoría del cálculo ajeno (no solo para calcular el propio) es deliberado: garantiza que "double deduction" signifique exactamente lo mismo cuando se le aplica a SW que cuando se le aplica a CP.

---

## 17. Manual Override Design

```
Override request (UI) ──► ManualOverride(original_value=<snapshot actual>,
                                          new_value=<propuesto>, reason, supporting_clause_id)
                              │
                              ▼
                     Recalculation trigger (automático)
                              │  crea nueva CalculationVersion que incorpora el override
                              │  como parte de manual_overrides[] del snapshot (sección 53)
                              ▼
                     AtomicInterval afectado se reconstruye con el valor override,
                     pero el AtomicInterval "sugerido originalmente" NO se borra —
                     queda referenciado desde el override (original_value)
```

**Sobre qué se puede hacer override:** cualquier salida automática — clasificación de evento, categoría, matched rule, primary rule seleccionada en un empate de precedencia, factor final de un intervalo, valor extraído de un CP. Todos comparten la misma tabla polimórfica (sección 2.7).

**Por qué el override dispara una nueva `CalculationVersion` completa y no un parche in-place:** RULE 7 (reproducibilidad histórica) exige que un cálculo aprobado anteriormente sin ese override siga siendo reconstruible exactamente como era. Un override, por más pequeño que sea, es una nueva versión del cálculo — nunca una mutación de la versión existente. Esto también resuelve naturalmente RULE 9 (overrides nunca se sobrescriben silenciosamente): como cada override queda ligado a la `CalculationVersion` donde se introdujo, un override posterior que lo reemplace crea su propia entrada nueva (`superseded_by`), preservando ambas en el historial.

**Permisos:** un override requiere rol `SW_OPERATOR` como mínimo; overrides sobre reglas contractuales (vs. simples correcciones de eventos) pueden requerir `SW_SUPERVISOR` — a definir en sección 27 (Seguridad).

---

## 18. CP Import Architecture

```
CP Document (Excel/PDF) ──► Document Layer (igual que cualquier documento)
                               ▼
                     CP Extraction (especializada, sección 4.1 de este doc)
                       - parser estructural de laytime sheets comunes (patrones de
                         columnas Date/Time/Event/Remarks/Hours/Deduction)
                       - fallback IA estructurada para layouts no estándar
                               ▼
                     CPSubmission(extracted_fields=JSON, status=EXTRACTED)
                               ▼
                     Human Review (misma filosofía que SOF — tabla editable,
                     nunca se confía 100% en la extracción de un documento de un tercero)
                               ▼
                     CPSubmission(status=CONFIRMED) ──► listo para Comparison Engine
```

**Por qué CP Import usa su propio extractor especializado y no simplemente "el extractor de SOF aplicado a otro documento":** un CP calculation ya es en sí mismo un cálculo con estructura tabular semi-estandarizada (columnas de fecha/hora/evento/horas/deducción/motivo), muy distinta de la prosa narrativa de un SOF. Tratarlo como "otro SOF" perdería la oportunidad de extraer directamente los campos agregados que sección 65 pide (allowed laytime, deductions, used laytime, demurrage amount) sin tener que re-derivarlos de eventos sueltos.

**Nunca se recalcula automáticamente el cálculo de CP con el Rules Engine propio de SW.** El objetivo de este módulo es capturar *lo que CP dice*, tal cual, para compararlo — no "corregir" el cálculo de CP silenciosamente. La corrección/objeción a CP ocurre explícitamente en el Comparison/Counter Engine (secciones 19-20), nunca de forma implícita en la importación.

---

## 19. CP vs SW Comparison Engine

```python
def compare(sw_version: CalculationVersion, cp: CPSubmission) -> Comparison:
    concept_diffs = compare_concepts(sw_version.results, cp.extracted_fields)  # tabla sección 66
    period_diffs = compare_periods(sw_version.atomic_intervals, cp.reconstructed_periods)  # sección 67
    for pd in period_diffs:
        pd.potential_double_deduction = detect_cp_double_deduction(cp.reconstructed_periods, pd)  # sección 40
    overall = MATCH if not period_diffs and not concept_diffs else DIFFERENCES_FOUND
    return Comparison(concept_diffs=concept_diffs, period_diffs=period_diffs, overall_status=overall)
```

**`compare_periods` — algoritmo:** se reconstruye para CP un timeline de intervalos usando el mismo motor de intervalos atómicos (sección 16), pero alimentado por los rangos de deducción que CP reporta con su tratamiento declarado (no con el Rules Engine de SW). Luego se hace un **diff estructural** contra los intervalos de SW: para cada intervalo atómico de SW, se busca el/los intervalo(s) de CP que lo solapan y se compara el `final_time_count_factor`/`final_demurrage_rate_factor`. Donde difieren, se genera un `PeriodDifference` con el rango exacto de discrepancia (que puede ser más fino que el intervalo original de cualquiera de los dos, gracias a construir un timeline atómico combinado de boundaries de ambas fuentes).

**Por qué reconstruir intervalos atómicos de CP en vez de comparar "línea por línea" las tablas de ambos:** las filas de un cálculo de CP y de SW casi nunca tienen exactamente los mismos límites de tiempo (CP puede agrupar 08:00–14:00 como una sola línea de "Weather 50%" mientras SW la parte en 3 tramos por cruce de boundary de 72h). Comparar filas textualmente produciría falsos positivos masivos. Comparar en la unidad atómica (segundo/minuto) es la única forma de aislar la discrepancia real, sin importar cómo cada parte agrupó su presentación.

---

## 20. Counter Workflow

Ya modelado en sección 2.6 (`Dispute`, `Counter`). El flujo de estados (sección 68, 69):

```
PeriodDifference (DIFFERENCES_FOUND)
        │  usuario SW decide objetar
        ▼
Counter(round_no=1, direction=SW_TO_CP, status=OPEN)
        │  se marca status=COUNTER_SENT al "enviar" (acción de negocio, no técnica —
        │  el sistema no envía el email; registra que fue enviado y opcionalmente
        │  adjunta el documento generado)
        ▼
CP responde (import de un nuevo CPSubmission tipo CP_COUNTER, round_no=2)
        │  se re-ejecuta compare_periods sobre este nuevo round
        ▼
Counter(round_no=2, direction=CP_TO_SW, status=CP_REPLIED) creado automáticamente
        │  vinculado al Counter(round_no=1) vía dispute_id — nunca se sobrescribe
        ▼
... N rounds ...
        ▼
Counter final: status=AGREED (ambas partes) ──► Dispute.status=AGREED
        │
        ▼  (cuando TODOS los PeriodDifference del voyage están AGREED/no aplican)
Voyage.workflow_state = APPROVED ──► READY_TO_SEND_RT ──► SENT_TO_RT ──► CLOSED
```

**Por qué cada `Counter` es una fila nueva (nunca se edita un counter existente):** sección 69 exige explícitamente "never overwrite versions". Esto también da, gratis, un historial de negociación completo y cronológico por `PeriodDifference` — necesario si RT eventualmente pregunta "¿cómo llegaron a este acuerdo?".

**Relación con Manual Override:** cuando un `Counter` es `AGREED`, el sistema genera automáticamente un `ManualOverride` sobre el `AtomicInterval` correspondiente con `reason` apuntando al `Counter.id` — así el acuerdo negociado queda incorporado al cálculo SW oficial siguiendo el mismo mecanismo de sección 17, preservando la sugerencia original del Rules Engine para comparación histórica.

---

## 21. Audit / Versioning Architecture

**Principio unificador:** todo lo que en este documento se describe como "append-only"/"nunca se borra" (`SOFEvent` corrections, `RuleVersion`, `CalculationVersion`, `ManualOverride`, `Counter`) alimenta el mismo `AuditLog` (sección 2.7) mediante un **hook transversal a nivel de servicio** (no depende de que cada desarrollador recuerde loguear manualmente): cada servicio de escritura del dominio pasa por una capa `AuditedRepository` que, en la misma transacción de DB, inserta el registro de negocio *y* la fila de `AuditLog` correspondiente.

```
Service layer
   │
   ▼
AuditedRepository.save(entity, user, reason)
   │  BEGIN TRANSACTION
   │    INSERT/nueva versión de la entidad de negocio
   │    INSERT AuditLog(entity_type, entity_id, user, timestamp, field, prev, new, reason, ...)
   │  COMMIT
```

**Por qué a nivel de repositorio y no como triggers de base de datos:** los triggers de DB no tienen acceso fácil al `user_id` de la sesión de aplicación ni al `reason` de negocio (texto libre que el usuario ingresa en el override). Ponerlo en la capa de repositorio permite capturar el contexto de negocio completo; se complementa (no se reemplaza) con el trigger de INSERT-only de la sección 3.1 como defensa en profundidad contra bypasses accidentales del ORM.

**Consulta de auditoría:** pantalla "Audit History" (sección 75) por voyage, filtrable por entidad/usuario/rango de fecha, mostrando siempre el par `previous_value → new_value` y el `reason`, nunca solo "algo cambió".

---

## 22. Main UI Screens

Estructura por Voyage (sección 75), con detalle de propósito y componente clave de cada una:

1. **Overview** — resumen ejecutivo del voyage: estado de workflow, montos CP vs SW vs Agreed, alertas activas (sección 77), próxima acción pendiente.
2. **Documents** — grid de documentos subidos por tipo, estado de extracción (texto listo / OCR pendiente / error), preview con viewer de PDF con resaltado (soporta "VIEW IN CONTRACT").
3. **Contract** — lista de `ContractClause` por documento, buscador (sección 61), y editor de reglas sugeridas vinculado a Rules.
4. **SOF Events** — la tabla editable de sección 9 (From/To/Event/Category/Source/Confidence/Status), con acciones de editar/split/merge/confirmar.
5. **Timeline** — la tabla de sección 63 (intervalos agregados como `LaytimePeriod`), con "Rule" clickeable (sección 59) abriendo un panel de explicación (sección 14 de este doc), y la línea de `Cumulative Counted Laytime` resaltando el punto de `Demurrage Commencement`.
6. **SW Calculation** — resultados de sección 64, con historial de `CalculationVersion` navegable (comparar V4 vs V5).
7. **CP Calculation** — vista de lo importado de CP (sección 65), editable antes de confirmar.
8. **Comparison** — tabla de sección 66 + drill-down a `PeriodDifference` (sección 67), con badges de "POTENTIAL CP DOUBLE DEDUCTION".
9. **Counter** — kanban o timeline de rounds (sección 68-69) por `PeriodDifference`.
10. **Rules** — reglas aplicables a este voyage (heredadas + overrides), con acceso al Rule Management global si el usuario tiene permiso.
11. **Audit History** — la vista de sección 21 de este documento.

**Componente transversal — "Explain Panel":** un panel lateral/modal reutilizado en Timeline, Comparison y el asistente de sección 81, que consume el endpoint único de sección 14 (`GET /atomic-intervals/{id}/explanation`). Construirlo como un componente único evita que la lógica de "cómo se explica una deducción" se duplique (e inevitablemente diverja) entre pantallas.

---

## 23. MVP Scope

Se adopta el MVP1 exactamente como está definido en la sección 79 del brief, sin modificaciones — está bien acotado y ya prioriza correctamente lo estructural (atomic timeline, no double deduction, versionado) sobre lo cosmético (contract extraction avanzada, weather engine fino, CP import). Se detalla a continuación qué implica cada ítem en términos del modelo de este documento, para dejar explícito el alcance real:

| # | Ítem del brief | Qué entidades/módulos de este doc activa |
|---|---|---|
| 1-5 | Create Voyage, Laycan, Allowed Laytime, Demurrage Rate, Daylight Restriction | `Voyage`, `PortCall` (secciones 2.1) — CRUD simple, sin IA |
| 6-7 | Upload SOF, Extract SOF | `Document`, pipeline de extracción nativa (sección 4), extracción IA básica (sección 5) — sin OCR avanzado aún, PDF nativo es suficiente para MVP1 |
| 8-9 | Human Review, Editable Events | `SOFEvent`, `EventEvidence` (sección 2.3), tabla de sección 9 |
| 10 | Atomic Timeline | Motor completo de sección 8 de este doc — **no se simplifica**, es la base de todo lo demás |
| 11 | NOR + 6 | Sub-módulo de commencement (sección 9 de este doc), como `RuleVersion` real desde el día 1 (no hardcodeado) |
| 12-13 | Basic Rules, 0/50/100% | `RuleDefinition`/`RuleVersion` con un set mínimo de reglas base (weather genérico, shifting genérico) — Rules Engine completo (sección 11), solo con menos reglas pre-cargadas |
| 14 | No Double Deduction | Sección 16 de este doc — algoritmo + integrity check, no negociable desde MVP1 |
| 15-17 | Used Laytime, Demurrage Commencement, Demurrage Amount | Motores de secciones 9-10 de este doc |
| 18 | Manual Override | Sección 17 de este doc, completo |
| 19 | Explanation per period | Endpoint de sección 14, UI simplificada (sin "View in Contract" con highlight de página aún — eso es MVP2) |
| 20 | Version Calculation | `CalculationVersion` completo desde MVP1 (es estructural, no se puede agregar después sin migración dolorosa) |

**Por qué el motor de Atomic Timeline, No-Double-Deduction, y CalculationVersion van completos desde MVP1 y no se simplifican "para ir rápido":** son los tres elementos que son estructuralmente costosos de agregar retroactivamente (requieren rediseño de modelo de datos y recálculo de todo lo existente). El resto (extracción IA más sofisticada, weather engine fino, CP import, contract clause extraction) son capas que se pueden *añadir* sin romper lo ya construido, porque todas leen del mismo modelo atómico. Esto es consistente con las fases MVP2-7 del brief, que agregan fuentes de reglas y comparación sin tocar el core.

---

## 24. Development Phases

Se sigue el orden MVP1→MVP7 del brief (sección 79) como fases de entrega, con un detalle adicional de "Definition of Done" técnico por fase para que la aprobación de cada fase sea verificable:

| Fase | Contenido | Definition of Done |
|---|---|---|
| **MVP1** | Voyage, SOF upload+extract+review, Atomic Timeline, NOR+6, reglas básicas 0/50/100%, No Double Deduction, cálculo de laytime/demurrage, override, versionado, explicación por período | Suite de tests 1-6, 19-23, 26, 29-30 (sección 78) en verde; un voyage real de prueba calculado manualmente coincide con el sistema |
| **MVP2** | Upload de contratos, clause extraction, rule suggestion, vínculo fuente↔regla, "View in Contract" | Tests de sección 56 (no rule without source); al menos una regla del set base viene de una cláusula real extraída, no hardcodeada a mano |
| **MVP3** | Rules Engine avanzado (AST completo), Rule Management UI, Rule Versioning UI, Rule Simulator | Tests 24-26 (rule conflict, voyage override, historical rule version); simulación de cambio de regla muestra impacto financiero correctamente |
| **MVP4** | Weather Engine completo (48h/72h, sealine, Pampilla), daylight restriction aplicado en cálculo | Tests 10-15 |
| **MVP5** | CP Import (Excel/PDF), Comparison Engine, detección de double deduction en CP | Tests 27-28 |
| **MVP6** | Counter Workflow completo, multi-round | Flujo end-to-end de disputa simulada con 2+ rounds hasta AGREED |
| **MVP7** | Workflow states completos, RT handoff, aprobación final, permisos por rol | Tests de sección 77 (validaciones) todos activos como gates de workflow |

**Nota de secuenciamiento:** MVP4 (Weather Engine) se puede desarrollar en paralelo a MVP2/MVP3 una vez que el Rules Engine de MVP3 esté listo, ya que Weather es "solo" un conjunto de `RuleVersion` más complejas sobre el mismo motor — no requiere cambios de arquitectura. Se lista después por prioridad de negocio (el brief la pide en ese orden), no por dependencia técnica dura.

---

## 25. Automated Testing Strategy

**Pirámide de testing, alineada a las capas de la sección 1:**

- **Unit tests (mayoría, ejecutan en milisegundos, sin DB ni red):** Rules Engine (evaluación de condiciones AST), Atomic Timeline Engine (construcción de intervalos dado un set fijo de eventos+reglas), Laytime/Demurrage Calculation Engine (aritmética pura), No-Double-Deduction integrity check. Estos son los 30 casos de la sección 78 del brief — se implementan literalmente como fixtures de "eventos + rule set → resultado esperado", sin mockear nada porque estos motores no tienen dependencias externas.
- **Integration tests (DB real vía testcontainers, sin red externa):** repositorios, versionado (`RuleVersion`/`CalculationVersion` append-only enforcement), constraints de integridad referencial (sección 3.1), flujo completo Comparison→Counter.
- **Contract/extraction tests (con LLM real pero *no* bloqueantes de CI en cada commit):** un set fijo de documentos de muestra (SOF reales anonimizados) con extracción esperada, corridos periódicamente (no en cada PR, por costo/latencia/no-determinismo) para detectar regresión de calidad de prompt. Estos tests **nunca** validan matemática — solo calidad de extracción (recall/precision de eventos, categorías correctas).
- **E2E tests (Playwright):** flujos de UI críticos — crear voyage → subir SOF → confirmar eventos → ver cálculo → override → ver explicación.

**Mapeo directo de los 30 casos de la sección 78 del brief:** cada uno se implementa como un test parametrizado del Atomic Timeline + Calculation Engine, usando `RuleVersion` de prueba fijas (fixtures versionadas en el repo de tests, no dependientes de datos de producción) — esto es lo que permite validar RULE 1-10 de forma continua en CI sin necesitar un voyage real.

**Regla de CI:** ningún cambio al Calculation Engine, Rules Engine o Atomic Timeline Engine puede mergearse si reduce la cobertura de los 30 casos base o si el integrity check (sección 16 de este doc) falla en cualquier fixture existente.

---

## 26. Edge Cases

Además de las validaciones ya listadas en la sección 77 del brief (que se implementan literalmente como reglas de validación del Workflow Layer, cada una con su propio código de alerta), se identifican estos casos límite adicionales de diseño:

- **Evento SOF con `start_time` pero sin `end_time` conocido aún** (operación en curso, ej. voyage todavía no completado): el `AtomicInterval` final queda abierto (`interval_end = NULL` o `now()` para cálculo provisional) y el cálculo se marca `PROVISIONAL` — nunca se confunde con un cálculo final.
- **Corrección de un evento que ya fue usado en una `CalculationVersion` `APPROVED`:** la corrección se permite (los eventos no son inmutables, solo versionados), pero **no** modifica retroactivamente la `CalculationVersion` aprobada — dispara automáticamente la creación de una nueva `CalculationVersion` en estado `DRAFT` marcada "affected by event correction after approval", visible como alerta en Overview.
- **Dos `RuleVersion` con el mismo `RuleDefinition`, mismo `scope`, `effective_from`/`effective_to` solapados, y ambas `ACTIVE`:** no debería ocurrir por el flujo normal de Activate (que supersede automáticamente), pero se agrega un check de integridad periódico (job) que detecta y alerta este estado inconsistente como `RuleConflict` a nivel de configuración (no de voyage).
- **Voyage cuyo `applicable_rule_set_version_id` se definió, pero luego una `RuleVersion` referenciada en ese set pasa a `ARCHIVED`:** archivar **no** elimina el `RuleSetVersion` congelado (sección 12) — el archivado es solo "no disponible para nuevos rule sets", el snapshot ya congelado sigue funcionando para reproducibilidad.
- **Timestamps de SOF sin fecha explícita en la página** (solo hora, la fecha se infiere del contexto/página anterior): se extrae con `confidence_status=NEEDS_REVIEW` obligatorio, nunca se infiere silenciosamente la fecha aunque parezca obvia.
- **Evento que cruza medianoche o cambio de mes/año:** normalización determinística (sección 7 de este doc) debe manejarlo explícitamente con tests dedicados — es una fuente común de bugs de off-by-one en sistemas de laytime.
- **CP reporta un evento/período que no existe en el SOF de SW en absoluto** (no es una diferencia de tratamiento, sino de hechos): se modela como un tipo especial de `PeriodDifference` (`fact_discrepancy=true`) distinto de una diferencia de regla — la UI debe distinguir claramente "no coincidimos en la regla" de "no coincidimos en qué pasó".
- **Allowed laytime en unidades distintas a horas (running days, weather working days) con calendario especial:** ya marcado como `CONTRACTUAL DECISION REQUIRED` en sección 9 de este doc.

---

## 27. Security / Permissions Requirements

**Roles (de `User.role`, sección 2.7):**

| Rol | Puede |
|---|---|
| `VIEWER` | Ver todo dentro de su organización/voyages asignados; no editar nada |
| `SW_OPERATOR` | Crear/editar voyages, revisar/confirmar SOF events, ejecutar cálculo, crear overrides de eventos, importar CP, preparar counters |
| `SW_SUPERVISOR` | Todo lo anterior + aprobar cálculo (`APPROVED`), override de reglas contractuales, enviar counter, mover a `READY_TO_SEND_RT`/`SENT_TO_RT`/`CLOSED` |
| `RULES_ADMIN` | CRUD de `RuleDefinition`/`RuleVersion`/`RuleSet`, activación de reglas, resolución de `RuleConflict` |
| `ADMIN` | Gestión de usuarios/permisos, todo lo anterior |

**Principios:**

- **Least privilege por defecto**, multi-tenant por organización (si en el futuro más de una counterparty/SW office comparte instancia) — cada `Voyage` tiene un `organization_id` implícito vía `sw_user_id`/su organización, y las consultas siempre filtran por organización del usuario autenticado a nivel de repositorio (no solo en el frontend).
- **Separación de funciones (segregation of duties):** quien activa una `RuleVersion` (`RULES_ADMIN`) normalmente no debería ser la misma persona que aprueba el cálculo final de un voyage específico afectado por esa regla (`SW_SUPERVISOR`) — se deja como **recomendación de proceso** configurable, no como restricción técnica dura en MVP1 (podría bloquear equipos pequeños); revisar en MVP7 si se requiere enforcement.
- **Auditoría de acceso, no solo de cambios:** además del `AuditLog` de cambios de datos, se recomienda logging de acceso a documentos sensibles (quién vio qué SOF/contrato) — `OPEN DESIGN QUESTION`: ¿es requisito regulatorio/contractual para este negocio? Si no hay obligación explícita, se puede diferir post-MVP para no añadir complejidad prematura.
- **Documentos y datos en tránsito/reposo:** TLS en tránsito, cifrado en reposo en Object Storage (estándar de cualquier proveedor S3-compatible), sin PII más allá de nombres de usuarios internos — el contenido es comercial/contractual, no datos personales sensibles regulados, pero sí confidencial comercialmente y debe tratarse como tal (control de acceso estricto por organización).
- **Autenticación:** se recomienda SSO/OAuth2 (no password propio) dado el contexto corporativo — a definir con el equipo de IT del usuario; no se asume un proveedor específico sin confirmación.

---

## 28. Technical Risks

| Riesgo | Impacto | Mitigación propuesta |
|---|---|---|
| **Calidad de extracción IA de SOF/contratos con formatos muy heterogéneos** (distintos brokers, distintos formatos de SOF por terminal/agente) | Alta tasa de `NEEDS_REVIEW`, fricción de usuario | Human review es obligatorio por diseño (no es un "nice to have" que se pueda degradar); invertir en el `EventSynonymMap` y prompts iterativamente con feedback real; medir precisión/recall por lote de documentos reales |
| **Complejidad combinatoria del Rules Engine** (muchas reglas activas simultáneamente pueden generar conflictos de precedencia frecuentes si el modelo de scope/priority no está bien calibrado) | `RuleConflict` excesivos, bloqueando cálculo automático | Empezar con set de reglas mínimo (MVP1-3), medir tasa de conflictos en voyages reales antes de escalar complejidad; `RuleSimulator` (sección 51) para probar antes de activar |
| **Definición exacta de "weather working days" / calendarios especiales** no estandarizada | Bloquea cálculo correcto de `allowed_laytime` en contratos que la usen | Flag `CONTRACTUAL DECISION REQUIRED` ya levantado (sección 9); acotar MVP1 a HOURS/RUNNING_DAYS simples primero |
| **Reproducibilidad histórica a largo plazo** (años) depende de que el `calculation_engine_version` realmente capture cualquier cambio de comportamiento del motor, incluso bugfixes | Un cálculo reproducido con una versión "arreglada" del motor podría diferir del original por una razón correcta (bug fix) pero indistinguible de una razón incorrecta (regresión) | Versionar el Calculation Engine con semver estricto + changelog obligatorio por cambio de comportamiento; tests de regresión (sección 25) como red de seguridad; nunca "arreglar en el motor actual" un bug que afecte cálculos ya `APPROVED` sin re-versionar explícitamente |
| **Volumen/latencia de LLM para documentos largos** (contratos de 40+ páginas, SOFs de voyages complejos con múltiples puertos) | Extracción lenta, costos de API elevados | Procesamiento por página/chunk en el worker async (no bloquea UI); cacheo de extracción por hash de documento (`sha256_hash` en `Document`) para evitar re-procesar el mismo archivo |
| **Ambigüedad de jerarquía contractual real** (sección 50) — es fundamentalmente un problema legal, no técnico | El sistema puede calcular "correctamente" según una jerarquía configurada que no sea la correcta legalmente | El sistema **nunca decide solo**: todo conflicto genera `RuleConflict`/`CONTRACTUAL RULE CONFLICT` (sección 28 del brief) requiriendo selección manual explícita y trazada; el riesgo se transfiere a un proceso humano documentado, no se resuelve técnicamente porque no es un problema técnico |
| **Onboarding de reglas base** (traducir Shellvoy 6 + cláusulas COA/RECAP reales a `RuleVersion` iniciales) es trabajo manual intensivo de dominio, no solo desarrollo | Puede ser el cuello de botella real del proyecto, más que el código | Priorizar en MVP2-3 con participación directa de un experto de laytime del equipo SW, no delegarlo solo a extracción IA sin revisión experta |

---

## 29. Contractual Decisions Still Required

Consolidado de todos los `CONTRACTUAL DECISION REQUIRED` levantados en este documento, para que puedan resolverse como un checklist antes o durante MVP1-4 (se indica cuál MVP los bloquea realmente; varios no bloquean MVP1):

1. **Redondeo de tiempo/dinero residual** (sección 1.2 de este doc) — ¿se trunca a segundos sin redondeo, o existe una práctica de redondeo a favor de una parte? *Bloquea: precisión de montos finales, no bloquea MVP1 (se puede usar el default propuesto y ajustar).*
2. **Timezone de cálculo** (sección 7 de este doc) — ¿hora local del puerto siempre, o zona fija del contrato? *Bloquea: exactitud en voyages con cambios de DST/cruce de zona; no bloquea MVP1 si se asume hora local del puerto como default razonable.*
3. **Tratamiento de "weather working days" / calendarios especiales de allowed laytime** (sección 9 de este doc) — especificación exacta de qué días no cuentan y bajo qué condición. *No bloquea MVP1 (asumir HOURS/RUNNING_DAYS); bloquea cualquier voyage que use ese tipo de unidad.*
4. **Redondeo de "running day or pro rata for part thereof" para demurrage** (sección 10 de este doc) — ¿fracción exacta o redondeo a una unidad práctica? *Bloquea montos finales de demurrage — debe resolverse antes de aprobar cualquier cálculo real, aunque no bloquea desarrollo de MVP1.*
5. **Jerarquía real de precedencia contractual** (Addendum/RECAP/COA/Rider/Shellvoy) y orden de especificidad de `scope` (sección 15 de este doc) — el brief mismo advierte que no debe asumirse. *No bloquea MVP1-2 (pocas reglas, conflictos poco probables); se vuelve crítico en MVP3 cuando el catálogo de reglas crece.*
6. **NOR antes del laycan** (sección 7 del brief) — tratamiento contractual configurable, sin default asumido; requiere una `RuleVersion` explícita basada en la cláusula real del contrato aplicable, no un comportamiento hardcodeado. *No bloquea MVP1 si no hay voyages con este caso en los primeros datos de prueba; bloquea el cálculo correcto para cualquier voyage donde SÍ ocurra.*
7. **Conflicto 48h (Owners Weather) vs 72h (Conoco/COA)** (sección 28 del brief) — ya diseñado como `RuleConflict` de resolución manual explícita; no requiere una decisión previa de arquitectura, pero sí que el usuario de negocio entienda que **cada ocurrencia** deberá resolverse caso a caso salvo que se establezca una regla de precedencia general confirmada.
8. **Cláusula incompleta de gastos de unberthing** (sección 35 del brief, "Any expenses unberthing...") — no se puede crear una regla económica sin el texto completo; se modela como `CONTRACT TEXT REQUIRED`, bloqueado hasta obtener la cláusula completa del contrato real.
9. **¿Requiere el negocio logging de acceso a documentos (no solo de cambios)?** (sección 27 de este doc) — depende de si existe una obligación contractual/regulatoria específica del negocio de SW; no se asume.
10. **Segregación de funciones dura** (RULES_ADMIN vs. SW_SUPERVISOR) — ¿debe ser un control técnico obligatorio desde MVP1, o basta como recomendación de proceso hasta MVP7? (sección 27 de este doc).

---

## 30. Recommended Project Folder Structure

```
coa-demoras/
├── backend/
│   ├── app/
│   │   ├── domain/                     # entidades + lógica pura, sin framework
│   │   │   ├── documents/
│   │   │   ├── facts/                  # SOFEvent, EventEvidence, normalización
│   │   │   ├── contracts/              # ContractClause, ContractDocument
│   │   │   ├── rules/                  # RuleDefinition, RuleVersion, condition AST
│   │   │   ├── timeline/               # Atomic Timeline Engine  (sin IA, sin DB)
│   │   │   ├── calculation/            # Laytime + Demurrage Engine (sin IA, sin DB)
│   │   │   ├── comparison/             # Comparison + double-deduction detection
│   │   │   ├── dispute/                # Dispute, Counter
│   │   │   └── audit/
│   │   ├── extraction/                 # todo lo que toca al LLM — SIEMPRE detrás
│   │   │   │                            # de una interfaz que devuelve "candidatos"
│   │   │   ├── sof_extraction/
│   │   │   ├── contract_extraction/
│   │   │   └── cp_extraction/
│   │   ├── infrastructure/
│   │   │   ├── db/                     # repositorios, modelos ORM, migraciones (alembic)
│   │   │   ├── storage/                # object storage client
│   │   │   ├── ocr/
│   │   │   └── llm/                    # cliente del proveedor de IA, solo usado por extraction/
│   │   ├── api/                        # FastAPI routers — capa delgada, delega a domain/
│   │   ├── workers/                    # tareas async (extracción, OCR)
│   │   └── workflow/                   # estados de Voyage, permisos, orquestación
│   ├── tests/
│   │   ├── unit/                       # domain/ — la mayoría de los 30 casos del brief
│   │   ├── integration/                # con DB real (testcontainers)
│   │   ├── extraction_quality/         # sets de documentos de muestra, no bloqueante en CI normal
│   │   └── e2e/
│   ├── alembic/                        # migraciones DB versionadas
│   └── pyproject.toml
├── frontend/
│   ├── app/                            # Next.js App Router
│   │   └── voyages/[id]/
│   │       ├── overview/
│   │       ├── documents/
│   │       ├── contract/
│   │       ├── sof-events/
│   │       ├── timeline/
│   │       ├── sw-calculation/
│   │       ├── cp-calculation/
│   │       ├── comparison/
│   │       ├── counter/
│   │       ├── rules/
│   │       └── audit/
│   ├── components/
│   │   ├── explain-panel/              # componente compartido de sección 22 de este doc
│   │   └── ...
│   └── lib/
├── docs/
│   └── architecture/
│       └── SYSTEM_ARCHITECTURE.md      # este documento — se mantiene vivo, versionado en git
└── infra/                              # IaC si aplica (a definir con el equipo de IT)
```

**Por qué `domain/` está estrictamente separado de `extraction/` a nivel de carpeta (no solo de convención):** es la materialización física de RULE 8 y RULE 5. Un linter de import-boundaries (ej. `import-linter` en Python) puede configurarse para **fallar el build** si algún módulo de `domain/calculation` o `domain/timeline` importa cualquier cosa de `extraction/` o `infrastructure/llm/` — convirtiendo la regla arquitectónica en una regla de CI verificable, no solo en una intención de diseño.

---

## Resumen de aprobación requerida

Para desbloquear el inicio de implementación de MVP1 se necesita:

1. ✅ Aprobación general de esta arquitectura (o feedback puntual por sección).
2. Confirmación o default aceptado para los ítems 1, 2 y 4 de la sección 29 (redondeo y timezone) — afectan la exactitud de montos desde el primer cálculo real, aunque no bloquean el desarrollo del motor en sí.
3. Un primer set de documentos reales (al menos 1 SOF y 1 Charter Party/Shellvoy reales, anonimizados si es necesario) para calibrar prompts de extracción y validar el catálogo de eventos/cláusulas contra casos reales antes de MVP2.

Con eso, el desarrollo puede comenzar por MVP1 según el detalle de la sección 24.
