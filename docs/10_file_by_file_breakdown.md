# ClinixAI — Complete File-by-File Breakdown

---

## AGENT SERVICE

---

### `agent_service/app/main.py`
**Service**: agent_service  
**Purpose**: FastAPI application factory and lifespan handler for the agent service.

Initializes the FastAPI app with:
- CORS middleware (allows requests from Next.js frontend)
- Lifespan context manager that validates Redis and MongoDB connections on startup
- Includes the `agent_routes` router

**Workflow role**: Service entry point. All `/chat` requests start here.

**Interactions**:
- includes: `agent_routes`
- startup validates: `RedisMemory`, MongoDB `clinixai_db`

---

### `agent_service/app/api/routes/agent_routes.py`
**Service**: agent_service  
**Purpose**: Defines the `/chat` HTTP endpoint — the single entry point for all agent interactions.

**Key Classes/Functions**:
- `ChatRequest` (Pydantic model): `message`, `session_id`, `role`, `patient_id`, `doctor_id`, `language`
- `ChatResponse` (Pydantic model): `response`, `session_id`, `memory`, `language`
- `chat()` async handler: Constructs `AgentState`, routes to `patient_graph.ainvoke()` or `run_doctor_pipeline()`, wraps in try/except for graceful error handling

**Implementation notes**: The top-level try/except was added to fix a 502 crash on WFLOW-009 (action_node error propagation). Any unhandled exception now returns a 200 with a graceful error message instead of a 502.

**Interactions**:
- calls: `patient_graph.ainvoke()`, `run_doctor_pipeline()`
- called by: Next.js API proxy (frontend)

---

### `agent_service/app/config/settings.py`
**Service**: agent_service  
**Purpose**: Environment-based configuration using Pydantic `BaseSettings`.

**Key fields**: `GROQ_API_KEY`, `REDIS_URL`, `MONGODB_URI`, `MONGODB_DB`, `AVAILABILITY_SERVICE_URL`, `APPOINTMENT_SERVICE_URL`, `GEO_SERVICE_URL`

**Implementation notes**: `extra = "ignore"` was added to fix Pydantic v2 validation errors when `.env` contained unrecognized keys (e.g., `DATABASE_NAME`).

---

### `agent_service/app/memory/redis_memory.py`
**Service**: agent_service  
**Purpose**: Async Redis client wrapper for session state management.

**Key Class**: `RedisMemory`

**Key Methods**:
- `load_state(session_id)` → `dict`: HGETALL all session keys; JSON-deserializes list/dict values
- `save_state(session_id, memory)`: HSET all memory fields; resets 30-minute TTL
- `delete_keys(session_id, keys)`: DEL specified keys (used during cross-workflow reset)
- `semantic_search(query_embedding, session_id, top_k)` → `list[str]`: Cosine similarity search against cached memory embeddings

**Interactions**:
- called by: `MemoryNode`, `WorkflowNode` (delete_keys), `StateWriterNode`
- calls: Redis via `aioredis`

---

### `agent_service/graphs/shared/schemas.py`
**Service**: agent_service (shared)  
**Purpose**: Defines `AgentState` — the central data contract flowing through all graph nodes.

**Key Class**: `AgentState(BaseModel)`  
Fields: `session_id`, `message`, `memory: dict`, `response`, `language`, `role`

**Workflow role**: Every node receives and returns this object. The `memory` dict is the mutable working state; `response` is written only by ActionNode.

---

### `agent_service/graphs/shared/nodes/intent_node.py`
**Service**: agent_service (shared)  
**Purpose**: LLM-based intent classification node. Classifies user message into one of 11 intents.

**Key Class**: `IntentNode`

**Key Method**: `run(state: AgentState) → AgentState`

**Logic**:
1. Constructs system prompt with intent definitions, 4 contextual override rules, specialty normalization rules
2. Calls Groq API (`llama-3.3-70b-versatile`, T=0) with current message + partial conversation history
3. Parses JSON response: `{intent, language, specialty, doctor_name, date, time}`
4. Merges extracted fields into `state.memory`

**Implementation notes**: Temperature=0.0 ensures deterministic classification. The 4 override rules prevent common misclassifications during multi-turn workflows (e.g., numeric input during doctor selection being classified as `none` instead of `select_doctor`).

**Interactions**:
- calls: Groq API
- called by: patient graph and doctor pipeline (shared)

---

### `agent_service/graphs/shared/workflow_state_cleaner.py`
**Service**: agent_service (shared)  
**Purpose**: Provides static methods to clear specific groups of state keys during cross-workflow resets.

**Key Class**: `WorkflowStateCleaner`

**Key Methods**:
- `clear_full_booking_state(memory, session_id)` → `list[str]`: Removes specialty, doctor_id, doctor_name, doctor_address, date, time, step, and booking-related fields
- `clear_all_appointment_state(memory, session_id)` → `list[str]`: Removes appointment_list, selected_appointment_id, pending_action
- `clear_geo_state(memory, session_id)` → `list[str]`: Removes geo_results, place search fields

**Workflow role**: Called by `WorkflowNode` during cross-workflow reset. Returns list of cleared keys so WorkflowNode can call `RedisMemory.delete_keys()` with them.

---

### `agent_service/graphs/patient/nodes/workflow_node.py`
**Service**: agent_service (patient graph)  
**Purpose**: Step-transition router. Translates intent + context into the correct `step` in `state.memory`. Does not generate any response text.

**Key Class**: `WorkflowNode`

**Key Constants**:
- `ACTIVE_STEPS`: frozenset of ~20 mid-flow step names where ActionNode has control
- `BOOKING_FLOW_STEPS`, `APPOINTMENT_FLOW_STEPS`, `GEO_FLOW_STEPS`, `AVAIL_CHECK_FLOW_STEPS`: frozensets for reset detection
- `_BOOKING_INCOMPATIBLE`, `_APPT_INCOMPATIBLE`, `_GEO_INCOMPATIBLE`, `_AVAIL_CHECK_INCOMPATIBLE`: frozensets of intents that trigger cross-workflow reset

**Key Method**: `run(state: AgentState) → AgentState`

**Logic flow**:
1. Cross-workflow reset check (4 scenarios × intra-appointment reset)
2. ACTIVE_STEPS guard (return state unchanged if mid-flight)
3. Intent-based step routing (11 if/elif branches)

**Implementation notes**: `WorkflowNode` never calls the LLM. It is a pure routing/state-machine node.

---

### `agent_service/graphs/patient/nodes/memory_node.py`
**Service**: agent_service (patient graph)  
**Purpose**: Restores session state from Redis and injects relevant long-term memories.

**Key Class**: `MemoryNode`

**Key Method**: `run(state: AgentState) → AgentState`

**Logic**:
1. `RedisMemory.load_state()` → merge into `state.memory`
2. MongoDB `patient_profiles.find_one({patient_id})` → `state.memory["profile"]`
3. Generate embedding for current message
4. `RedisMemory.semantic_search()` → top-k memories → `state.memory["semantic_memories"]`

---

### `agent_service/graphs/patient/nodes/state_writer_node.py`
**Service**: agent_service (patient graph)  
**Purpose**: Persists updated state to Redis and extracts new long-term memories.

**Key Class**: `StateWriterNode`

**Key Method**: `run(state: AgentState) → AgentState`

**Logic**:
1. `RedisMemory.save_state(session_id, memory)` → persist all memory fields
2. Append turn to conversation_history
3. LLM-based fact extraction from response + user message
4. Insert new `user_memories` documents with embeddings if new facts found
5. `patient_profiles.update_one()` if profile data changed

---

### `agent_service/graphs/patient/handlers/geo_handler.py`
**Service**: agent_service (patient graph)  
**Purpose**: HTTP client wrapper for calling the geo service proximity API.

**Key Class**: `GeoHandler`

**Key Methods**:
- `find_nearby_places(lat, lng, category, specialty, radius)` → `list[dict]`: POST to `/api/nearby`
- `search_manual(query, category, governorate, specialty)` → `list[dict]`: POST to `/api/search/manual`

**Interactions**:
- calls: geo_service (Flask, port 5000)
- called by: ActionNode when `step="searching_places"`

---

## EVALUATION SERVICE

---

### `evaluation_service/schemas/eval_schemas.py`
**Service**: evaluation_service  
**Purpose**: Pydantic models for all evaluation data contracts.

**Key Classes**:
- `EvalRequest`: Input to the evaluation pipeline (message, response, reference, toggles)
- `EvalResult`: Full output with all metric scores, dimensions, provenance
- `JudgeDimension`: Per-dimension LLM judge output (score, explanation, confidence)
- `TrendPoint`: Time-series data point for chart rendering (includes NLP + agent metrics)
- `TrendResponse`: Aggregated trends with averages, best/worst runs
- `EvalScenario`: Scenario definition from the dataset
- `CompareResult`: Side-by-side comparison with delta

---

### `evaluation_service/evaluators/orchestrator.py`
**Service**: evaluation_service  
**Purpose**: Assembles all evaluators, runs them concurrently, and computes weighted overall_score.

**Key Class**: `EvalOrchestrator`

**Key Constants**: `_WEIGHTS` dict (safety: 0.20, workflow: 0.17, hallucination: 0.14, conversational_quality: 0.14, groundedness: 0.10, answer_correctness: 0.09, answer_relevancy: 0.09, memory_relevance: 0.04, context_precision: 0.02, personalization: 0.01)

**Key Method**: `evaluate(request: EvalRequest) → EvalResult`

**Logic**:
1. `asyncio.gather()` all LLM judge calls + NLP metric computations
2. `_score()` helper extracts individual dimension scores
3. Weighted sum for overall_score (inverts hallucination_risk)
4. Assembles `EvalResult` with all scores and metadata

---

### `evaluation_service/evaluators/judge/llm_judge.py`
**Service**: evaluation_service  
**Purpose**: Runs LLM judge calls for all 9 evaluation dimensions.

**Key Function**: `run_judge(request: EvalRequest) → dict[str, JudgeDimension]`

**Logic**:
1. Creates `asyncio.Task` for each applicable dimension
2. Uses `asyncio.gather(*tasks)` for concurrent execution
3. Each task calls Groq API with dimension-specific prompt
4. Parses `{score, explanation, confidence}` JSON from response

**Implementation notes**: Groundedness is always evaluated (new dimension added for faithfulness vs factual hallucination distinction). Multilingual consistency only evaluated when language != "english".

---

### `evaluation_service/evaluators/judge/prompts.py`
**Service**: evaluation_service  
**Purpose**: Prompt engineering for all LLM judge dimensions.

**Key Functions** (one per dimension):
- `conversational_quality_prompt(user_message, agent_response, language, role)`: Minimum 0.80 guarantee for proactive responses; explicit anti-verbosity bias rules; few-shot examples
- `hallucination_judge_prompt(...)`: Factual hallucination only (invented specifics)
- `groundedness_faithfulness_prompt(...)`: Retrieval faithfulness; hedged actions score high
- `workflow_score_prompt(...)`: Task completion and workflow advancement
- `safety_judge_prompt(...)`: Harm detection
- `answer_relevancy_prompt(...)`: Proactive responses score 1.0 (anti-reference-bias rule)
- `answer_correctness_prompt(...)`: CRITICAL ANTI-BIAS RULE — exceeding the reference is not penalized

**Implementation notes**: The SYSTEM_JUDGE includes a "PROACTIVITY IS QUALITY" evaluation philosophy block that calibrates all dimensions toward agentic healthcare behavior.

---

### `evaluation_service/evaluators/metrics/text_normalizer.py`
**Service**: evaluation_service  
**Purpose**: Unicode-safe text normalizer for NLP metric computation.

**Key Function**: `normalize(text: str) → str`

**What it preserves**: Arabic letters, French accented characters (é, à, ç), all Unicode letters
**What it removes**: ASCII punctuation, curly quotes, dashes, bullets, Arabic punctuation marks
**Does NOT do**: NFD decomposition, transliteration, stemming

**Workflow role**: Called by `normalize_pair()` and `normalize_multi()` before ROUGE/BLEU/EM/ESM computation.

---

### `evaluation_service/evaluators/metrics/rouge_score.py`
**Service**: evaluation_service  
**Purpose**: ROUGE-1, ROUGE-2, ROUGE-L computation with normalization and multi-reference support.

**Key Function**: `compute_rouge_scores(candidate, reference, extra_references) → RougeScores`

**Logic**: Normalizes candidate and all references; computes ROUGE against each reference; returns the best F1 scores across all references.

---

### `evaluation_service/evaluators/metrics/bleu_score.py`
**Service**: evaluation_service  
**Purpose**: Sentence-level BLEU computation.

**Key Function**: `compute_bleu_score(candidate, reference, extra_references) → float`

**Logic**: Uses `sacrebleu.sentence_bleu()` with all normalized references; divides by 100 to normalize to [0,1].

---

### `evaluation_service/evaluators/metrics/bert_score.py`
**Service**: evaluation_service  
**Purpose**: Semantic similarity via contextual BERT embeddings.

**Key Function**: `compute_bert_score(candidate, reference) → float`

**Model**: `bert-base-multilingual-cased`

---

### `evaluation_service/app/services/result_store.py`
**Service**: evaluation_service  
**Purpose**: MongoDB CRUD for evaluation results.

**Key Functions**:
- `save_result(result) → str`: Insert document, return MongoDB _id
- `get_result(id) → EvalResult`: Fetch and deserialize single result
- `list_results(limit, skip, filters) → list[EvalSummary]`: Paginated history query
- `get_trends(limit, scenario_id) → TrendResponse`: Aggregate trend data with averages and best/worst run computation

---

### `evaluation_service/datasets/eval_scenarios.py`
**Service**: evaluation_service  
**Purpose**: Hardcoded catalog of test scenarios.

**Content**: Scenario definitions for workflow (WFLOW-001/002/003 — EN/FR/AR), memory, recommendation, multilingual, hallucination, safety, and doctor categories.

---

## FRONTEND

---

### `frontend/app/eval/page.tsx`
**Service**: frontend  
**Purpose**: 5-tab evaluation dashboard main page component.

**Key State**: `history`, `trends`, `sessionResults`, `lastResult`, `tab`, `compareIds`, `scenarios`

**Key Computed Values**:
- `unifiedTimeline`: Map-based merge of MongoDB history + session results
- `nlpCurves`: BLEU/ROUGE-1/2/L series from unified timeline
- `agentCurves`: Workflow/Conversational/Hallucination/Groundedness series
- `judgeBarData`: Global averages for horizontal bar chart
- `stats`: KPI card values (total runs, averages)

**Interactions**:
- calls: `evalApi.ts` (all evaluation endpoints)
- renders: `ThesisCurveChart`, `RadarEvaluation`, `EvaluationHistory`, `ScoreRing`, `MetricCard`, `JudgePanel`, `TrendChart`, `LatencyChart`

---

### `frontend/components/eval/ThesisCurveChart.tsx`
**Service**: frontend  
**Purpose**: Thesis-style line chart for NLP and agent metric curves.

**Props**: `title`, `subtitle`, `data: {label, value}[]`, `color`, `height`

**Key Logic**: Filters `valid = data.filter(v != null && v > 0)`; computes avg/max/min; renders Recharts `LineChart` with `connectNulls` and `type="monotone"`; overlays red dashed `ReferenceLine` at average; empty state when no valid data.

---

### `frontend/components/eval/RadarEvaluation.tsx`
**Service**: frontend  
**Purpose**: Spider/radar chart for multi-dimensional evaluation scores.

**Props**: `result: EvalResult`, `height`

**Key Logic**: Maps 8 dimensions to radar points; filters nulls; requires ≥3 valid dimensions to render; uses Recharts `RadarChart` with violet fill.

---

### `frontend/types/eval.ts`
**Service**: frontend  
**Purpose**: TypeScript type definitions mirroring backend Pydantic schemas.

**Key exports**: `EvalResult`, `EvalSummary`, `TrendPoint`, `TrendResponse`, `EvalScenario`, `CompareResult`, `JudgeDimension`, `scoreColor()`, `scoreLabel()`, `METRIC_LABELS`, `CATEGORY_LABELS`, `SCORE_COLORS`

---

## AVAILABILITY SERVICE

---

### `availability_service/app/services/availability_service.py`
**Service**: availability_service  
**Purpose**: Core business logic for schedule and slot management.

**Key Class**: `AvailabilityService`

**Key Methods**:
- `create_availability(payload)`: Create schedule for (doctor, day); validates slots
- `get_free_slots(doctor_id, day, date)`: Compute available slots (template − exceptions − booked appointments)
- `book_slot(doctor_id, day, start)`: Mark slot as booked
- `release_slot(doctor_id, day, start)`: Release slot back to available
- `block_slot(doctor_id, day, start)`: Manually block a slot
- `_validate_slots(slots)`: Check no empty, no backwards, no overlapping slots

**Implementation notes**: `get_free_slots` calls `appointment_service` via httpx to get booked times for a specific date, then subtracts them from template slots. If appointment_service fails, candidate slots are returned as-is (fail-open, not fail-closed).

---

### `availability_service/app/core/scheduling.py`
**Service**: availability_service  
**Purpose**: Slot generation from time ranges.

**Key Functions**:
- `generate_slots_from_ranges(ranges, duration_minutes)` → `list[dict]`: Splits ranges into fixed-duration slots
- `get_consultation_duration(document)` → `int`: Extracts `consultationDurationMinutes` or defaults to 30

---

### `availability_service/app/models/slot_model.py`
**Service**: availability_service  
**Purpose**: Pydantic model for a single time slot.

```python
class SlotModel(BaseModel):
    start: str       # "HH:MM"
    end: str         # "HH:MM"
    status: SlotStatus = SlotStatus.AVAILABLE
```

---

## AUTH SERVICE

---

### `auth_service/app/core/security.py`
**Service**: auth_service  
**Purpose**: Password hashing and JWT creation/decoding.

**Key Functions**:
- `hash_password(plain)` → `str`: bcrypt hash with auto-generated salt
- `verify_password(plain, hashed)` → `bool`: constant-time bcrypt comparison
- `create_access_token(data)` → `str`: HS256 JWT with exp claim
- `decode_token(token)` → `dict`: Validates and decodes JWT

---

### `auth_service/app/services/auth_service.py`
**Service**: auth_service  
**Purpose**: Authentication business logic.

**Key Methods**:
- `signup_patient(email, password, name)`: Validates uniqueness, creates patient_profile_id slug, upserts patient_profiles document, creates user, issues JWT
- `login(email, password)`: Validates credentials, issues JWT for patient or doctor
- `get_current_user(email)`: Returns user document by email

---

### `auth_service/app/schemas/auth.py`
**Service**: auth_service  
**Purpose**: Pydantic models for auth API contracts.

**Key Classes**: `SignupRequest` (role locked to "patient"), `LoginRequest`, `TokenResponse` (includes patient_profile_id and doctor_id), `UserOut`

---

## GEO SERVICE

---

### `geo_service/api_proximity.py`
**Service**: geo_service  
**Purpose**: Flask API for proximity-based medical facility search.

**Key Routes**:
- `POST /api/nearby`: Haversine-based proximity search with category/specialty/radius filtering
- `POST /api/doctors/map`: Doctors grouped by specialty for map rendering
- `POST /api/search/manual`: Text-based search with multilingual query normalization
- `POST /api/doctors/lookup`: Batch ObjectId → name resolution
- `GET /api/specialties`: Aggregated specialty list
- `GET /api/governorates`: Aggregated governorate list
- `GET /api/categories`: All 10 categories with document counts

**Key Function**: `haversine_distance(lat1, lon1, lat2, lon2)` → float: Great-circle distance computation

---

### `geo_service/main.py` — `MedicalDataExtractor`
**Service**: geo_service  
**Purpose**: Batch data extraction pipeline.

**Key Class**: `MedicalDataExtractor`

**Key Methods**:
- `run_extraction(categories)`: Orchestrates extraction for all/specified categories across 24 governorates
- `extract_category(category_key, category_config)`: Calls Google Places API for one category
- `save_to_mongodb(data, collection_name)`: Bulk inserts into MongoDB with index creation
- `save_checkpoint(category_key, data, stats)`: Saves progress checkpoint for resume capability
- `generate_final_report()`: Outputs statistics per category and overall coverage

---

### `geo_service/scheduler.py`
**Service**: geo_service  
**Purpose**: Periodic refresh scheduler for medical data.

**Workflow role**: Runs `MedicalDataExtractor.run_extraction()` on a schedule (weekly/monthly) to keep the facility database current.
