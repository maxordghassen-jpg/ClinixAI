# ClinixAI Architecture

## Overview

ClinixAI is a multi-agent healthcare scheduling platform. It exposes a single HTTP API (`agent_service`) that routes conversations through two independent AI graphs — one for patients, one for doctors. Both graphs speak to the same downstream microservices via a shared HTTP client layer.

```
Client (HTTP)
    │
    ▼
agent_service/app         ← FastAPI app, routing, config
    │
    ├── Patient Graph      ← LangGraph StateGraph (5 nodes)
    └── Doctor Graph       ← Imperative pipeline (5 stages)
            │
            ▼
    graphs/shared/mcp/     ← Shared HTTP clients (single source of truth)
            │
            ├── AppointmentClient   → appointment_reservation service
            ├── AvailabilityClient  → disponibility service
            └── GeoClient           → medical_places / geo service
```

---

## Layer Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│  API Layer                                                        │
│  app/main.py  →  app/api/routes/agent_routes.py                  │
│  POST /patient/chat  |  POST /doctor/chat                        │
└────────────────────────┬────────────────────────────────────────┘
                         │
          ┌──────────────┴──────────────┐
          ▼                             ▼
┌──────────────────┐         ┌──────────────────────┐
│  Patient Graph   │         │  Doctor Graph         │
│  (LangGraph)     │         │  (Imperative)         │
│                  │         │                       │
│  MemoryNode      │         │  IntentDetector       │
│  IntentNode      │         │  MemoryNode           │
│  WorkflowNode    │         │  ToolSelector         │
│  ActionNode      │         │  Executor             │
│  StateWriterNode │         │  ResponseGenerator    │
└────────┬─────────┘         └──────────┬────────────┘
         │                              │
         │    ┌─────────────────────────┘
         ▼    ▼
┌────────────────────────────────────────────────────────────────┐
│  Handler Layer  (patient only)                                  │
│  handlers/BookingHandler  handlers/AppointmentsHandler         │
│  handlers/GeoHandler                                           │
└────────────────────────────┬───────────────────────────────────┘
                              │
┌────────────────────────────▼───────────────────────────────────┐
│  ToolCaller Layer  (one per graph)                              │
│  patient/mcp/tool_caller.py  |  doctor/mcp/tool_caller.py      │
│  (thin adapters — delegate to shared MCP clients below)         │
└────────────────────────────┬───────────────────────────────────┘
                              │
┌────────────────────────────▼───────────────────────────────────┐
│  Shared MCP Clients  graphs/shared/mcp/                        │
│  base_client.py  appointment_client.py  availability_client.py │
│  geo_client.py                                                  │
└────────────────────────────┬───────────────────────────────────┘
                              │  HTTP (httpx)
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
   appointment_reservation  disponibility     geo/places
       microservice           microservice     microservice
```

---

## Folder Responsibilities

### `app/`
FastAPI application shell.
- `main.py` — lifespan, CORS, router mount
- `api/routes/agent_routes.py` — two POST endpoints, session injection
- `config/settings.py` — environment config (Pydantic BaseSettings)
- `services/patient_memory_service.py` — MongoDB fire-and-forget writes for patient intelligence
- `repositories/patient_profile_repo.py` — read/write `clinix_agent.patient_profiles`

### `graphs/patient/`
LangGraph-based patient assistant.
- `patient_graph.py` — `build_patient_graph()`, compiles the StateGraph
- `nodes/memory_node.py` — loads Redis state, seeds `AgentState`
- `nodes/workflow_node.py` — step-machine: drives multi-turn booking, geo, appointments workflows
- `nodes/action_node.py` — 3-way router: delegates to `BookingHandler`, `AppointmentsHandler`, `GeoHandler`
- `nodes/state_writer_node.py` — **single authoritative Redis write point** per turn
- `handlers/` — one handler per domain (booking, appointments, geo); use `ToolCaller` for MCP calls
- `mcp/tool_caller.py` — delegates all patient MCP calls to shared clients
- `mcp/client.py` — backward-compat alias: `MCPClient = BaseClient`

### `graphs/doctor/`
Imperative pipeline for the doctor assistant.
- `navigation_graph.py` — `DoctorGraph` class, runs the 5-stage pipeline + terminal Redis write
- `nodes/intent_detector.py` — AsyncGroq LLM call, produces `IntentSchema`
- `nodes/memory_node.py` — loads doctor state from Redis
- `nodes/tool_selector.py` — routes intent action to the right executor class
- `nodes/executor.py` — delegates to per-domain executor (appointments, availability)
- `nodes/response_generator.py` — formats final reply via LLM
- `tools/appointments/executor.py` — appointment read/write via `ToolCaller`
- `tools/availability/executor.py` — availability template + exception management via `ToolCaller`
- `mcp/tool_caller.py` — delegates all doctor MCP calls to shared clients
- `mcp/client.py` — backward-compat alias: `MCPClient = BaseClient`

### `graphs/shared/`
Cross-graph infrastructure. Nothing here is graph-specific.

**`mcp/`** — Single HTTP client implementation.
- `base_client.py` — `BaseClient(httpx.AsyncClient)` with retry logic and error handling
- `appointment_client.py` — all appointment API calls
- `availability_client.py` — all availability/exception API calls
- `geo_client.py` — geo search calls

**`scheduling_engine/`** — Pure Python scheduling logic. No I/O, no HTTP, importable from seed scripts.
- `slot_generator.py` — time parsing, slot generation from ranges and legacy templates
- `recurrence_engine.py` — French weekday maps, day-name resolution
- `exception_resolver.py` — blocked-day and override detection
- `conflict_detector.py` — filter slots against booked times
- `availability_resolver.py` — combined resolver (template + exception + conflicts)
- `next_available_engine.py` — async scan for next available date

**`services/scheduling/`** — I/O layer wrapping the pure engine.
- `availability_engine.py` — `AvailabilityEngine`: reads templates via MCP, delegates slot logic to engine
- `appointment_engine.py` — `AppointmentEngine`: reads bookings via MCP, delegates to engine
- `http_client.py` — backward-compat stub (deprecated, wraps shared MCP clients)

**`normalizers/`**
- `date_normalizer.py` — `DateNormalizer.normalize()` / `normalize_safe()`: multilingual date parsing
- `time_normalizer.py` — time string normalization

**Other shared utilities**
- `schemas.py` — `AgentState`, `IntentSchema`, `WorkflowState` (the `IntentSchema` at line 48 is dead)
- `trace.py` — structured `trace(tag, session_id, msg)` logging
- `formatting.py` — response text helpers
- `slot_formatter.py` — slot list → human-readable text
- `booking_responses.py` — standard booking reply strings
- `workflow_state_cleaner.py` — clears Redis workflow keys post-completion
- `nodes/intent_node.py` — shared LangGraph node: AsyncGroq LLM → `IntentSchema`

### `scripts/`
Standalone data utilities. Not part of the running service.
- `seed_availability.py` — seeds availability templates (disponibilites collection)
- `seed_appointments.py` — seeds realistic appointments from real free slots
- `seed_patients.py` — seeds patient profiles
- `utils/index_helpers.py` — MongoDB index helpers

---

## Scheduling Engine

The scheduling engine (`graphs/shared/scheduling_engine/`) is the **single source of truth** for all slot generation and scheduling calculations. It is pure Python with no imports from FastAPI, httpx, settings, or any app context.

### Data Flow

```
Availability Template (MongoDB)
    │  "ranges": [{start, end}, ...]     ← new format
    │  "slots":  [{start, end, status}]  ← legacy format
    ▼
generate_slots(template, duration)       ← slot_generator.py
    │
    ▼
[list of "HH:MM" start strings]
    │
    ├── filter by exception (exception_resolver.py)
    │       "closure" / "vacation"  → block entire day
    │       "override"              → replace with override_ranges slots
    │
    ├── filter against booked times (conflict_detector.py)
    │       filter_free(all_slots, booked_times)
    │
    ▼
Free slot strings ready for booking
```

### Why Pure Python

The engine has no I/O so it can be:
- Imported directly by seed scripts without a running app
- Unit-tested without mocking HTTP
- Called from both patient handlers and doctor executors
- Extended without touching HTTP clients

### French Weekday Convention

Availability templates store day names in French (`lundi`, `mardi`, ..., `dimanche`). All weekday-to-int and int-to-weekday conversions are centralized in `recurrence_engine.py`.

---

## MCP Layer

`graphs/shared/mcp/` is the **only** place where HTTP calls to downstream microservices are made.

### Design Principles

1. One client class per microservice domain
2. All clients extend `BaseClient` (shared retry, timeout, error handling)
3. Both patient and doctor `ToolCaller` classes delegate to these shared clients
4. No graph-specific code in the shared clients

### Client–Service Mapping

| Client | Service | Base URL env var |
|--------|---------|-----------------|
| `AppointmentClient` | appointment_reservation | `APPOINTMENT_SERVICE_URL` |
| `AvailabilityClient` | disponibility | `AVAILABILITY_SERVICE_URL` |
| `GeoClient` | geo/medical_places | `GEO_SERVICE_URL` |

### ToolCaller Pattern

Each graph has its own `ToolCaller` (thin adapter):

```python
# patient/mcp/tool_caller.py
class ToolCaller:
    def __init__(self):
        self._appointments  = AppointmentClient()
        self._availability  = AvailabilityClient()
        self._geo           = GeoClient()

    async def get_free_slots(self, doctor_id, date):
        return await self._appointments.get_free_slots(doctor_id, date)
    # ...
```

This keeps graph code decoupled from HTTP implementation details while maintaining a stable interface.

---

## State and Memory

### Redis (Short-term)

Workflow state lives in Redis with a 1800s TTL. Keys per session:

- `session:{id}:state` — `AgentState` dict (patient graph)
- `session:{id}:doctor_state` — doctor graph state
- `session:{id}:workflow` — active workflow step and context

`StateWriterNode` is the **single authoritative write point** for the patient graph. All intermediate nodes return updated state dicts; only `StateWriterNode` writes to Redis.

### MongoDB (Long-term)

Patient intelligence (preferences, history, summaries) is stored in `clinix_agent.patient_profiles` via `PatientMemoryService` (fire-and-forget, non-blocking).

---

## Compatibility Layers

Three backward-compat stubs exist to prevent import breakage during migration. They should be removed once all callers have been updated.

| File | Replaces | Status |
|------|----------|--------|
| `graphs/patient/mcp/client.py` | Old patient `MCPClient` class | Safe to remove once verified no external callers |
| `graphs/doctor/mcp/client.py` | Old doctor `MCPClient` class | Same |
| `graphs/shared/services/scheduling/http_client.py` | `SchedulingHTTPClient` | Safe to remove once `AvailabilityEngine`/`AppointmentEngine` confirmed as sole callers |

---

## Migration Notes

### What Changed (recent refactors)

1. **ActionNode decomposition** — Monolithic `action_node.py` replaced by handler pattern (`BookingHandler`, `AppointmentsHandler`, `GeoHandler`).

2. **MCP centralization** — All HTTP calls now route through `graphs/shared/mcp/`. Patient and doctor `ToolCaller` classes are thin adapters. Two old `client.py` files replaced with backward-compat aliases.

3. **Scheduling engine centralization** — All slot generation extracted from seed scripts, `AvailabilityEngine`, and doctor executors into `graphs/shared/scheduling_engine/`. Seven duplicate implementations removed.

4. **DateNormalizer** — `normalize_safe()` added; both doctor tool executors now use shared normalizer. Duplicate `_normalize_date()` helpers removed.

### Old Patient Pipeline (Dead)

`graphs/patient/navigation_graph.py` contains an old imperative `PatientGraph` pipeline:

```
IntentDetector → MemoryNode → ToolSelector → Executor → ResponseGenerator
```

This was superseded by the LangGraph graph in `patient_graph.py`. The file is **never imported** by live code and should be deleted. Five additional files exist only to support it (see cleanup plan).

---

## Future Cleanup Notes

See **CLEANUP.md** for the full categorized list. Short version:

- **12 dead files** can be removed immediately (old patient pipeline, dead shared utilities)
- **3 compatibility stubs** should be removed after import verification
- **Dead `IntentSchema` block** in `schemas.py` should be deleted
- `graphs/doctor/tools/events/` and `graphs/doctor/tools/patients/` tool.py files are unused — verify before removing
- `app/memory/context_merger.py` — check if any external callers remain before removing
