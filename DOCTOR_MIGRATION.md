# Doctor Graph — Migration Roadmap

## Current vs Target Architecture

```
CURRENT (imperative, old executor pattern)          TARGET (handler pattern, aligned with patient)
─────────────────────────────────────────────────   ──────────────────────────────────────────────────
DoctorGraph.run()                                   DoctorGraph.run()
  IntentDetector   ← LLMRouter (raw httpx)            IntentDetector   ← shared IntentNode (AsyncGroq)
  MemoryNode       ← MemoryExtractor                  MemoryNode       ← MemoryExtractor (unchanged)
  ToolSelector     ← trivial (1 line)                 ActionNode       ← routes to domain handlers
  Executor         ← ToolsRegistry dispatch           ResponseGenerator
  └── ToolsRegistry                                   StateWriterNode  ← extracted from DoctorGraph
      ├── AppointmentsTool → AppointmentsExecutor
      └── AvailabilityTool → AvailabilityExecutor     handlers/
  ResponseGenerator                                     AppointmentsHandler (= AppointmentsExecutor)
  terminal Redis write (inline)                         AvailabilityHandler (= AvailabilityExecutor)
```

---

## Incremental Migration Steps

### Step 1 — Collapse dispatch layers into ActionNode + Handlers  ← DONE
**What changes:** Replace `ToolSelector + Executor + ToolsRegistry + {X}Tool` (4 layers, zero logic) with a single `ActionNode` that routes directly to domain handlers. Extract terminal Redis write into `StateWriterNode`.

**What is created:**
- `handlers/appointments_handler.py` — AppointmentsExecutor logic, class renamed to AppointmentsHandler
- `handlers/availability_handler.py` — AvailabilityExecutor logic, class renamed to AvailabilityHandler
- `nodes/action_node.py` — 2-way router: appointments | availability
- `nodes/state_writer_node.py` — terminal Redis write extracted from DoctorGraph.run()

**What becomes dead (cleanup pass after Step 1):**
- `nodes/tool_selector.py`
- `nodes/executor.py`
- `registries/tools_registry.py` + `registries/__init__.py`
- `tools/appointments/tool.py`
- `tools/availability/tool.py`
- `tools/appointments/executor.py` (logic moved to handlers)
- `tools/availability/executor.py` (logic moved to handlers)

**Pipeline after Step 1:**
```
IntentDetector → MemoryNode → ActionNode → ResponseGenerator → StateWriterNode
```

**Risk:** None. The handlers contain identical logic to the executors. The MCP layer, LLMRouter, MemoryExtractor, and all external interfaces are untouched.

---

### Step 2 — Migrate IntentDetector to shared IntentNode
**What changes:** Replace `LLMRouter` (raw httpx Groq) with the shared `IntentNode` (AsyncGroq SDK). Requires aligning the doctor prompt schema with the shared IntentNode's `IntentSchema` format.

**Prerequisite:** Verify `IntentResult` (in `schemas.py`) and `IntentSchema` (in `intent_node.py`) produce compatible outputs for the doctor's handlers.

**Risk:** Low-medium. LLM output format must be tested carefully. The fallback in `IntentDetector._fallback()` still works as a safety net.

---

### Step 3 — Add WorkflowNode for multi-turn doctor flows (if needed)
**What changes:** If doctor needs multi-turn workflows (e.g., guided availability setup, rescheduling confirmation), add a `WorkflowNode` step machine between `MemoryNode` and `ActionNode`.

**Currently:** Doctor is fully stateless — each turn is self-contained. This step is only needed when multi-turn flows are designed.

**Risk:** None until this step is started. No changes required now.

---

### Step 4 — Migrate to LangGraph StateGraph
**What changes:** Replace `DoctorGraph.run()` imperative loop with a compiled LangGraph `StateGraph`, identical to `patient_graph.py`.

**Benefit:** Consistent debugging, tracing, conditional edges, and future extensibility.

**Risk:** Low once Steps 1–3 are complete — by that point the pipeline is already node-shaped.

---

## Target Folder Structure (after all steps)

```
graphs/doctor/
  doctor_graph.py             ← build_doctor_graph() (LangGraph StateGraph)
  nodes/
    memory_node.py            ← unchanged
    action_node.py            ← routes to handlers
    response_generator.py     ← unchanged
    state_writer_node.py      ← extracted terminal Redis write
  handlers/
    appointments_handler.py   ← appointment read/write/manage logic
    availability_handler.py   ← availability template + exception logic
  tools/
    appointments/
      intents.py              ← KEEP (action sets, is_schedule_view)
      prompts.py              ← KEEP (LLM prompt)
      schemas.py              ← KEEP (AppointmentToolInput)
    availability/
      intents.py              ← KEEP
      prompts.py              ← KEEP
      schemas.py              ← KEEP if needed
  shared/
    prompts.py                ← KEEP (DOCTOR_INTENT_PROMPT)
  mcp/
    tool_caller.py            ← unchanged
    client.py                 ← compat alias (Category B)
```

---

## Design Rules (enforced from patient graph)

| Layer | Responsibility |
|-------|---------------|
| `ActionNode` | Orchestration and routing only — no business logic |
| `Handlers` | Domain workflow logic — call services and ToolCaller |
| `Services` | Reusable business operations (if/when added) |
| `ToolCaller` | HTTP adapter — delegates to shared MCP clients |
| `StateWriterNode` | Single authoritative Redis write per turn |
| `SchedulingEngine` | Centralized slot calculation — no duplication |
