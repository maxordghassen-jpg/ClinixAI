# ClinixAI — Agent Service (LangGraph Multi-Agent System)

## 1. Service Overview

The agent service is the **core intelligence** of ClinixAI. It exposes a single primary endpoint (`POST /chat`) that accepts a user message and session context, runs a multi-node LangGraph pipeline, and returns the agent's response alongside updated state.

- **Framework**: FastAPI (async)
- **Port**: 8001
- **AI Backbone**: Groq API with `llama-3.3-70b-versatile` model, temperature=0.0
- **Orchestration**: LangGraph `StateGraph`
- **Memory**: Redis (session) + MongoDB (long-term)

The service handles two distinct user roles through two separate graph pipelines:
1. **Patient graph** — a fully compiled LangGraph DAG with 5 nodes
2. **Doctor graph** — a sequential imperative pipeline (not a compiled StateGraph)

---

## 2. LangGraph Framework

LangGraph is a library for building stateful, multi-step AI agents. It extends LangChain with a graph execution model where:

- **Nodes** are Python async functions that receive and return an `AgentState` object
- **Edges** define the execution order between nodes (sequential, conditional, or parallel)
- **StateGraph** compiles the node graph into an executable pipeline with the signature `graph.ainvoke(state) → state`

The key advantage over a raw chain or function call is that **state is first-class**. Every node reads from and writes to a shared state object, making it trivial to pass context between steps without threading it through function arguments manually.

### Compilation

The patient graph is compiled once at startup:

```python
builder = StateGraph(AgentState)
builder.add_node("memory",   memory_node.run)
builder.add_node("intent",   intent_node.run)
builder.add_node("workflow", workflow_node.run)
builder.add_node("action",   action_node.run)
builder.add_node("writer",   state_writer_node.run)

builder.set_entry_point("memory")
builder.add_edge("memory",   "intent")
builder.add_edge("intent",   "workflow")
builder.add_edge("workflow", "action")
builder.add_edge("action",   "writer")
builder.set_finish_point("writer")

patient_graph = builder.compile()
```

Each call to `patient_graph.ainvoke(state)` executes the full 5-node pipeline synchronously within an async event loop.

---

## 3. AgentState — The Central Data Contract

`AgentState` (defined in `graphs/shared/schemas.py`) is the Pydantic model that flows through all nodes:

```python
class AgentState(BaseModel):
    session_id: str      # Identifies the user session; used as Redis key prefix
    message:    str      # The current user message being processed
    memory:     dict     # All accumulated state (intent, step, doctor, date, etc.)
    response:   str      # The agent's response text (written by ActionNode)
    language:   str      # "english", "french", or "arabic"
    role:       str      # "patient" or "doctor"
```

The `memory` dict is the operational state. Key fields written into `memory` across turns:

| Key | Set by | Purpose |
|---|---|---|
| `step` | WorkflowNode | Current workflow step ("awaiting_date", "ready_to_book", etc.) |
| `intent` | IntentNode | Classified intent for this turn |
| `language` | IntentNode | Detected input language |
| `specialty` | IntentNode | Medical specialty mentioned by user |
| `doctor_id` | ActionNode | MongoDB ID of selected doctor |
| `doctor_name` | ActionNode | Human-readable doctor name |
| `doctor_address` | ActionNode | Doctor's address for display |
| `date` | IntentNode/ActionNode | ISO date for appointment |
| `time` | IntentNode/ActionNode | Time string for appointment |
| `appointment_list` | ActionNode | List of patient's appointments |
| `selected_appointment_id` | ActionNode | ID of appointment being managed |
| `geo_results` | ActionNode | List of nearby places from geo search |
| `profile` | MemoryNode | Patient's MongoDB profile document |
| `semantic_memories` | MemoryNode | Retrieved long-term memories |
| `workflow_started_at` | WorkflowNode | Unix timestamp of workflow start |
| `patient_id` | MemoryNode | Patient profile ID from JWT payload |
| `pending_action` | WorkflowNode | "cancel" or "reschedule" for appointment management |

---

## 4. Node 1: MemoryNode

**File**: `graphs/patient/nodes/memory_node.py` and `graphs/doctor/nodes/memory_node.py`

**Purpose**: Restore session state from Redis and inject relevant long-term memories before intent classification.

### Execution Steps

1. **Load Redis session**: Call `RedisMemory.load_state(session_id)` → `HGETALL` on the session namespace. The result is merged into `state.memory`.

2. **Load patient profile**: Query MongoDB `patient_profiles` collection for `patient_id` (extracted from the request JWT payload). Inject as `state.memory["profile"]`.

3. **Semantic memory retrieval**: Generate a 384-dimensional embedding of the current user message using `paraphrase-multilingual-MiniLM-L12-v2`. Perform cosine similarity search against all stored `user_memories` documents for this patient. Retrieve top-k (typically 3–5) most relevant memories and inject as `state.memory["semantic_memories"]`.

4. **Language/session defaults**: Initialize default language and patient_id if not already in memory.

### Why semantic memory is loaded here (not later)

Loading memories in MemoryNode (before IntentNode) ensures the LLM has full context when classifying intent. For example, if a patient previously expressed a preference for morning appointments, this memory is available when the LLM interprets "book for tomorrow" — allowing it to implicitly favor morning slots.

---

## 5. Node 2: IntentNode

**File**: `graphs/shared/nodes/intent_node.py`

**Purpose**: Classify the user's intent using the LLM and extract structured parameters (specialty, doctor name, date, time).

### Supported Intents

IntentNode recognizes **11 intents**:

| Intent | Trigger | Example |
|---|---|---|
| `booking` | Book/schedule appointment | "I want to see a cardiologist next Monday" |
| `doctor_search` | Search for specific doctor | "Find me a doctor named Ben Ali" |
| `select_doctor` | Select doctor from list | "I'll take the second one" |
| `view_appointments` | View appointment history | "Show my appointments" |
| `cancel_appointment` | Cancel an appointment | "Cancel my appointment tomorrow" |
| `reschedule_appointment` | Reschedule | "Can we move it to Thursday?" |
| `select_appointment` | Select from appointment list | "The first one" |
| `geo_search` | Find nearby facility | "Find a pharmacy near me" |
| `check_availability` | Check specific slot | "Is Dr. Benali free Friday at 10am?" |
| `set_reminder` | Set appointment reminder | "Remind me 2 hours before" |
| `none` | General conversation/greeting | "Hello" / "Thank you" |

### LLM Call Structure

IntentNode constructs a system prompt that:
1. Defines the classification task and all 11 intents with descriptions
2. Specifies the expected JSON output schema: `{intent, language, specialty, doctor_name, date, time}`
3. Provides contextual override rules (4 rules):
   - **Rule 1**: If session has an active step (e.g., `"awaiting_time"`), remap generic responses to workflow continuations
   - **Rule 2**: During `"awaiting_reschedule_*"` steps, interpret date/time inputs as reschedule continuations
   - **Rule 3**: Normalize Arabic/French specialty names to their English equivalents
   - **Rule 4**: Numeric responses ("1", "the second") while `step="selecting_doctor"` → `intent="select_doctor"`

The model is called at temperature=0.0 to maximize determinism in intent classification.

### Output Extraction

The LLM returns a JSON blob which IntentNode parses and merges into `state.memory`:
```python
state.memory["intent"]   = result["intent"]
state.memory["language"] = result["language"]
if result.get("specialty"):   state.memory["specialty"]    = result["specialty"]
if result.get("doctor_name"): state.memory["doctor_name"]  = result["doctor_name"]
if result.get("date"):        state.memory["date"]         = result["date"]
if result.get("time"):        state.memory["time"]         = result["time"]
```

---

## 6. Node 3: WorkflowNode

**File**: `graphs/patient/nodes/workflow_node.py`

**Purpose**: Translate the classified intent and current context into the correct workflow step. This node does NOT generate any text — it only sets `state.memory["step"]`.

### Step Transition Logic

WorkflowNode implements a finite state machine with 6 workflow flows:

**Booking flow steps:**
```
awaiting_specialty → searching_doctors → selecting_doctor →
doctor_selected → awaiting_date → awaiting_time →
(awaiting_slot_selection | awaiting_recovery_choice) → ready_to_book
```

**Appointment management flow steps:**
```
fetching_appointments → selecting_appointment →
(confirming_cancel | confirming_reschedule) →
(done | awaiting_reschedule_date → awaiting_reschedule_time → ready_to_reschedule)
```

**Geo search flow steps:**
```
searching_places → selecting_place
```

**Availability check flow steps:**
```
checking_availability_doctor → (awaiting_availability_date)
```

**Set reminder:**
```
saving_reminder_preference
```

### Cross-Workflow Reset

The most sophisticated part of WorkflowNode is its **cross-workflow reset logic**. When a user starts a new workflow while an old one is still in progress, WorkflowNode must:
1. Detect the incompatibility (e.g., `step="awaiting_time"` + `intent="geo_search"`)
2. Call `WorkflowStateCleaner` to wipe stale fields from `state.memory`
3. Call `RedisMemory.delete_keys()` to sync the deletion to Redis immediately
4. Set `current_step = None` to skip the ACTIVE_STEPS guard

**Four reset scenarios:**
- `booking → new`: Any intent incompatible with booking (geo_search, view_appointments, etc.) while a booking step is active
- `appointment → new`: Any intent incompatible with appointment management (booking, geo_search) while appointment steps are active
- `geo → new`: New geo_search or booking intent while place selection is pending
- `avail → new`: New intent incompatible with availability check flow

### ACTIVE_STEPS Guard

Once a workflow is in flight, WorkflowNode must NOT re-route based on the latest intent. Example: user typed "yes" while `step="awaiting_time"` — IntentNode might classify this as `intent="none"`, but WorkflowNode must leave the step unchanged so ActionNode continues waiting for the time.

The guard:
```python
if current_step in ACTIVE_STEPS:
    return state  # do nothing — ActionNode handles mid-flight steps
```

`ACTIVE_STEPS` is a hardcoded frozenset of 20+ step names that are "owned" by ActionNode.

---

## 7. Node 4: ActionNode (Patient)

**File**: `graphs/patient/nodes/action_node.py` (inferred from workflow)

**Purpose**: The executor. Reads `state.memory["step"]` and performs the corresponding action: API call, response generation, or state update.

### Actions by Step

| Step | Action |
|---|---|
| `searching_doctors` | Call availability_service to list doctors by specialty; present numbered list |
| `doctor_selected` | Confirm doctor selection; ask for date |
| `awaiting_date` | Ask patient to provide a date |
| `awaiting_time` | Query availability_service for free slots on selected date; present slots |
| `awaiting_slot_selection` | User chose an alternative slot after 409 conflict |
| `ready_to_book` | Call appointment_service to create appointment; call availability_service to book slot |
| `fetching_appointments` | Call appointment_service to list patient's appointments |
| `selecting_appointment` | Resolve index from user input to appointment ID |
| `confirming_cancel` | Present cancel confirmation |
| `confirming_reschedule` | Present reschedule confirmation |
| `awaiting_reschedule_date` | Ask for new date |
| `awaiting_reschedule_time` | Query free slots for new date |
| `ready_to_reschedule` | Update appointment via appointment_service |
| `searching_places` | Call geo_service `/api/nearby` with user coordinates and category |
| `selecting_place` | User selected a place from the list |
| `checking_availability_doctor` | Call availability_service for free slots on specified date |
| `saving_reminder_preference` | Store reminder preference in user_memories |
| `idle` | General LLM response (no workflow active) |

### LLM Response Generation

For non-structured steps (idle, general queries), ActionNode calls the Groq LLM with:
- The full conversation history (from Redis)
- Injected semantic memories from MemoryNode
- The patient's profile (name, medical preferences)
- Language instruction (respond in the same language as the user)

For structured steps (searching_doctors, booking confirmation, etc.), ActionNode generates **template-based responses** (formatted lists with numbered items, confirmation strings) rather than free-form LLM text.

---

## 8. Node 5: StateWriterNode

**File**: `graphs/patient/nodes/state_writer_node.py`

**Purpose**: Persist the updated `state.memory` back to Redis and optionally extract new long-term memories.

### Execution Steps

1. **Redis write**: Call `RedisMemory.save_state(session_id, memory)` → `HSET` all memory fields with the 30-minute TTL.

2. **Conversation history append**: Add the current turn (user message + assistant response) to the conversation history list in Redis.

3. **Memory extraction**: If the agent's response or user message contains new medical facts (e.g., "I'm allergic to penicillin", "I prefer afternoon appointments"), extract these as `user_memories` documents in MongoDB with embeddings for future semantic retrieval.

4. **Profile update**: If the patient shared new demographic information, update `patient_profiles` in MongoDB.

---

## 9. Doctor Graph

The doctor graph is simpler — it does not use a compiled StateGraph. Instead, it's an imperative async pipeline:

```python
state = await doctor_memory_node.run(state)
state = await shared_intent_node.run(state)
state = await doctor_state_writer_node.run(state)
```

The doctor graph reuses `IntentNode` (shared) but has its own `MemoryNode` and `StateWriterNode` with doctor-specific prompts and MongoDB queries (queries `doctors` collection instead of `patient_profiles`).

The doctor's ActionNode is currently integrated directly into the response generation step rather than being a separate node — reflecting the more general-purpose nature of the physician assistant compared to the patient's structured booking workflows.

---

## 10. API Routes

**File**: `app/api/routes/agent_routes.py`

### `POST /chat`

Primary endpoint. Receives a chat request and runs the appropriate graph.

```python
class ChatRequest(BaseModel):
    message: str
    session_id: str
    role: str = "patient"
    patient_id: str | None = None
    doctor_id: str | None = None
    language: str = "english"

class ChatResponse(BaseModel):
    response: str
    session_id: str
    memory: dict
    language: str
```

**Routing logic:**
```python
if request.role == "doctor":
    state = await run_doctor_pipeline(state)
else:
    state = await patient_graph.ainvoke(state)
return ChatResponse(response=state.response, memory=state.memory, ...)
```

**Error handling**: A top-level `try/except` catches any graph execution error and returns a graceful 200 response with an error message — preventing 502 errors from propagating to the frontend.

---

## 11. Redis Memory Interface

**File**: `app/memory/redis_memory.py`

The `RedisMemory` class wraps `aioredis` for async Redis operations:

```python
class RedisMemory:
    async def load_state(session_id) → dict
    async def save_state(session_id, memory: dict) → None
    async def delete_keys(session_id, keys: list[str]) → None
    async def semantic_search(query_embedding, session_id, top_k=5) → list[str]
```

**Key schema**: `session:{session_id}:{field_name}` for individual state fields.

**TTL**: 30 minutes (1800 seconds) on all session keys, refreshed on every save.

---

## 12. Settings and Configuration

**File**: `app/config/settings.py`

Uses Pydantic `BaseSettings` with `extra='ignore'` to tolerate unknown env vars:

```python
class Settings(BaseSettings):
    GROQ_API_KEY: str
    REDIS_URL: str = "redis://localhost:6379"
    MONGODB_URI: str
    MONGODB_DB: str = "clinixai_db"
    AVAILABILITY_SERVICE_URL: str = "http://localhost:8002"
    APPOINTMENT_SERVICE_URL: str = "http://localhost:8003"
    GEO_SERVICE_URL: str = "http://localhost:5000"
    
    class Config:
        env_file = ".env"
        extra = "ignore"
```
