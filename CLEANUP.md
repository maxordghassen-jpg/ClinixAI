# ClinixAI — Cleanup Plan

Categorized dead code audit. All entries verified by import tracing.

---

## CATEGORY A — Safe Immediate Removals

These files are provably dead: no active code imports them. Deleting them cannot break anything at runtime.

### Old Patient Pipeline (superseded by LangGraph `patient_graph.py`)

| File | Reason |
|------|--------|
| `agent_service/graphs/patient/navigation_graph.py` | `PatientGraph` imperative pipeline, never imported by `agent_routes.py` or any live node |
| `agent_service/graphs/patient/nodes/executor.py` | Only imported by dead `navigation_graph.py` |
| `agent_service/graphs/patient/nodes/intent_detector.py` | Only imported by dead `navigation_graph.py` |
| `agent_service/graphs/patient/nodes/response_generator.py` | Only imported by dead `navigation_graph.py` |
| `agent_service/graphs/patient/nodes/tool_selector.py` | Only imported by dead `navigation_graph.py` |

### Old Patient Tool Framework (superseded by ActionNode handlers)

| File | Reason |
|------|--------|
| `agent_service/graphs/patient/tools/` (entire directory) | `tools/*/tool.py`, executors, schemas, intents, prompts — only imported by dead `executor.py` and dead `intent_detector.py` |
| `agent_service/graphs/patient/registries/tools_registry.py` | Only imported by dead `executor.py` |
| `agent_service/graphs/patient/registries/__init__.py` | Empty stub for dead registry |
| `agent_service/graphs/patient/prompts/patient_prompts.py` | Only imported by dead nodes; nothing active imports it |
| `agent_service/graphs/patient/prompts/__init__.py` | Empty stub |
| `agent_service/graphs/patient/shared/prompts.py` | Only imported by dead `intent_detector.py` and dead `patient_prompts.py` |
| `agent_service/graphs/patient/shared/__init__.py` | Empty stub for dead module |
| `agent_service/graphs/patient/actions/__init__.py` | Empty stub, no files in directory |

### Dead Shared Utilities

| File | Reason |
|------|--------|
| `agent_service/graphs/shared/memory_extractor.py` | `MemoryExtractor` regex extractor, replaced by LLM `IntentNode`. Not imported anywhere active. |
| `agent_service/graphs/shared/context_recovery.py` | `ContextRecovery` rule-based class, not imported by any live node |
| `agent_service/graphs/shared/llm_router.py` | `LLMRouter` raw httpx Groq client. Live code uses `AsyncGroq` SDK directly. Not imported anywhere active. |

### Dead App Layer

| File | Reason |
|------|--------|
| `agent_service/app/memory/session_memory.py` | In-memory Python dict session store, replaced by `RedisMemory`. Not imported. |
| `agent_service/app/core/dependencies.py` | `get_llm_router()` — not called anywhere in active code |

### Dead Doctor Tools

| File | Reason |
|------|--------|
| `agent_service/graphs/doctor/tools/events/tool.py` | Not imported anywhere |
| `agent_service/graphs/doctor/tools/patients/tool.py` | Not imported anywhere |

### Dead Code Inside Active Files

| Location | What to remove |
|----------|---------------|
| `agent_service/graphs/shared/schemas.py` lines 48–69 | Second `IntentSchema` class definition — dead duplicate. Live `IntentNode` defines its own locally. |

---

## CATEGORY B — Compatibility Layers (Keep Temporarily)

These files exist solely to avoid breaking any callers that were written against old APIs. They should be removed once all callers have been verified or migrated.

| File | What it aliases | When to remove |
|------|----------------|----------------|
| `agent_service/graphs/patient/mcp/client.py` | `MCPClient = BaseClient` (from `graphs.shared.mcp.base_client`) | After confirming no external code imports `graphs.patient.mcp.client` |
| `agent_service/graphs/doctor/mcp/client.py` | `MCPClient = BaseClient` | Same — confirm no external callers |
| `agent_service/graphs/shared/services/scheduling/http_client.py` | `SchedulingHTTPClient` stub delegating to `AvailabilityClient`/`AppointmentClient` | After confirming only `AvailabilityEngine` and `AppointmentEngine` were its callers (both already migrated) |

---

## CATEGORY C — Legacy Files to Archive Later

Files that may still have callers outside the audited scope, or that contain partial state you may want to reference before deleting.

| File | Situation |
|------|-----------|
| `agent_service/app/memory/context_merger.py` | Not imported in the audited codebase; may have test or script callers. Verify before removing. |
| `agent_service/graphs/doctor/tools/events/__init__.py` | Empty stub for dead `events/tool.py`. Remove together with the tool. |
| `agent_service/graphs/doctor/tools/patients/__init__.py` | Same — remove with `patients/tool.py`. |

---

## CATEGORY D — Files Still Actively Used

Core runtime files. Do not modify without understanding the full dependency chain.

| File | Role |
|------|------|
| `agent_service/app/main.py` | FastAPI app, CORS, lifespan |
| `agent_service/app/api/routes/agent_routes.py` | Route handlers, session injection |
| `agent_service/app/config/settings.py` | Environment config |
| `agent_service/app/services/patient_memory_service.py` | MongoDB async writes |
| `agent_service/app/repositories/patient_profile_repo.py` | Patient profile persistence |
| `agent_service/graphs/patient/patient_graph.py` | Live LangGraph graph builder |
| `agent_service/graphs/patient/nodes/memory_node.py` | Redis load, state seed |
| `agent_service/graphs/patient/nodes/workflow_node.py` | Multi-turn step machine |
| `agent_service/graphs/patient/nodes/action_node.py` | 3-way handler router |
| `agent_service/graphs/patient/nodes/state_writer_node.py` | Authoritative Redis write |
| `agent_service/graphs/patient/handlers/booking_handler.py` | Booking flow |
| `agent_service/graphs/patient/handlers/appointments_handler.py` | Appointment queries |
| `agent_service/graphs/patient/handlers/geo_handler.py` | Geo search |
| `agent_service/graphs/patient/mcp/tool_caller.py` | Patient MCP adapter |
| `agent_service/graphs/patient/services/` | Service classes used by handlers |
| `agent_service/graphs/doctor/navigation_graph.py` | Live doctor pipeline |
| `agent_service/graphs/doctor/nodes/` (all) | Doctor pipeline nodes |
| `agent_service/graphs/doctor/tools/appointments/executor.py` | Appointment tool |
| `agent_service/graphs/doctor/tools/availability/executor.py` | Availability tool |
| `agent_service/graphs/doctor/mcp/tool_caller.py` | Doctor MCP adapter |
| `agent_service/graphs/shared/mcp/` (all) | Shared HTTP clients |
| `agent_service/graphs/shared/scheduling_engine/` (all) | Pure scheduling logic |
| `agent_service/graphs/shared/services/scheduling/availability_engine.py` | Availability I/O layer |
| `agent_service/graphs/shared/services/scheduling/appointment_engine.py` | Appointment I/O layer |
| `agent_service/graphs/shared/normalizers/date_normalizer.py` | Date parsing |
| `agent_service/graphs/shared/normalizers/time_normalizer.py` | Time string normalization |
| `agent_service/graphs/shared/schemas.py` | `AgentState`, `IntentSchema`, `WorkflowState` |
| `agent_service/graphs/shared/nodes/intent_node.py` | LLM intent detection (LangGraph node) |
| `agent_service/graphs/shared/trace.py` | Structured logging |
| `agent_service/graphs/shared/formatting.py` | Response text helpers |
| `agent_service/graphs/shared/slot_formatter.py` | Slot list formatting |
| `agent_service/graphs/shared/booking_responses.py` | Standard booking replies |
| `agent_service/graphs/shared/workflow_state_cleaner.py` | Redis cleanup post-workflow |

---

## CATEGORY E — Files Needing Future Consolidation

These are active but have overlap or technical debt worth addressing in a future pass.

| File | Issue |
|------|-------|
| `agent_service/graphs/shared/schemas.py` | `IntentSchema` (lines 48–69, dead duplicate) should be deleted; remainder is fine |
| `agent_service/graphs/shared/services/scheduling/` | `AvailabilityEngine` and `AppointmentEngine` are thin I/O wrappers — could eventually be merged into a single `SchedulingService` |
| `agent_service/graphs/patient/services/` | Multiple small service classes; some may overlap with handler logic |
| `agent_service/graphs/shared/formatting.py` + `booking_responses.py` + `slot_formatter.py` | Three separate text-formatting modules — could be unified |

---

## Removal Checklist

Use this checklist when executing the cleanup. Tick each file after deleting.

### Category A (safe, do first)

```
[ ] graphs/patient/navigation_graph.py
[ ] graphs/patient/nodes/executor.py
[ ] graphs/patient/nodes/intent_detector.py
[ ] graphs/patient/nodes/response_generator.py
[ ] graphs/patient/nodes/tool_selector.py
[ ] graphs/patient/tools/  (entire directory)
[ ] graphs/patient/registries/tools_registry.py
[ ] graphs/patient/registries/__init__.py
[ ] graphs/patient/prompts/patient_prompts.py
[ ] graphs/patient/prompts/__init__.py
[ ] graphs/patient/shared/prompts.py
[ ] graphs/patient/shared/__init__.py
[ ] graphs/patient/actions/__init__.py
[ ] graphs/shared/memory_extractor.py
[ ] graphs/shared/context_recovery.py
[ ] graphs/shared/llm_router.py
[ ] app/memory/session_memory.py
[ ] app/core/dependencies.py
[ ] graphs/doctor/tools/events/tool.py
[ ] graphs/doctor/tools/patients/tool.py
[ ] graphs/shared/schemas.py  — delete lines 48–69 (dead IntentSchema)
```

### Category B (after import verification)

```
[ ] graphs/patient/mcp/client.py        — verify no external callers
[ ] graphs/doctor/mcp/client.py         — verify no external callers
[ ] graphs/shared/services/scheduling/http_client.py  — verify no callers
```

### Category C (after extended verification)

```
[ ] app/memory/context_merger.py        — check test files and scripts
[ ] graphs/doctor/tools/events/__init__.py
[ ] graphs/doctor/tools/patients/__init__.py
```
