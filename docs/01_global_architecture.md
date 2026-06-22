# ClinixAI — Global System Architecture

## 1. Project Overview

ClinixAI is a production-grade, multi-agent AI platform designed to digitize and automate healthcare workflows in a Tunisian medical context. The system enables patients to book appointments, search for nearby doctors and pharmacies, manage existing appointments (cancel, reschedule), and receive personalized healthcare guidance — all through a conversational natural language interface.

At the same time, the platform provides a parallel AI assistant for doctors: a separate graph-based agent that helps physicians manage their practice, respond to administrative queries, and interact with patient records.

The technical foundation of ClinixAI is a **microservices architecture** composed of seven distinct services, an **AI orchestration layer** built on LangGraph, a **persistent semantic memory system** backed by Redis and MongoDB, and a **comprehensive evaluation framework** that measures both classical NLP quality metrics and modern agentic behavior dimensions.

---

## 2. Microservices Architecture

ClinixAI decomposes its functionality into seven independently deployable services, each owning a specific domain:

| Service | Port | Framework | Responsibility |
|---|---|---|---|
| `agent_service` | 8001 | FastAPI + LangGraph | Core AI agent orchestration (patient + doctor graphs) |
| `availability_service` | 8002 | FastAPI | Doctor schedule management and slot availability |
| `auth_service` | 8005 | FastAPI | User authentication, JWT issuance, role management |
| `evaluation_service` | 8006 | FastAPI | LLM-as-a-Judge + NLP metric evaluation pipeline |
| `geo_service` | 5000 | Flask | Geolocation: nearby doctor/pharmacy search via MongoDB + Haversine |
| `appointment_service` | 8003 | (separate) | Appointment persistence, retrieval by date, status transitions |
| `frontend` | 3000 | Next.js 16 | Patient and doctor chat UIs, evaluation dashboard, map, calendar |

**Why microservices?**

The decision to split into microservices rather than a monolith was driven by several concerns:

1. **Independent scaling**: The AI agent service (computationally intensive, GPU/LLM API calls) can be scaled independently from the lightweight auth service.
2. **Technology heterogeneity**: The geo_service is Flask-based (convenient for a Python data-processing pipeline), while the agent service uses FastAPI's async capabilities for concurrent LLM calls.
3. **Fault isolation**: A crash in the evaluation service does not affect patient-facing agent functionality.
4. **Clear domain boundaries**: Each service owns its data model and its API contract, reducing coupling.
5. **Team parallelism**: Different parts of the system can be developed and deployed independently.

Communication between services is exclusively **synchronous REST HTTP** — no message queue is used in the current architecture. The agent service calls the availability service, geo service, and appointment service directly via `httpx` async HTTP calls during workflow execution.

---

## 3. LangGraph Orchestration

The core AI orchestration is implemented using **LangGraph**, a framework for building stateful, graph-based AI agents built on top of LangChain.

### Why LangGraph?

Traditional chatbot frameworks (e.g., raw LangChain chains, RASA, Botpress) struggle with multi-step stateful workflows where:
- The conversation spans multiple turns (e.g., booking: specialty → doctor selection → date → time → confirmation)
- State must be tracked across turns (what doctor was selected, what date was mentioned)
- Routing must adapt dynamically based on intent AND accumulated context
- Cross-workflow transitions must reset stale state (user pivots from booking to viewing appointments)

LangGraph addresses this with a **directed acyclic graph (DAG)** of nodes where:
- Each node is a pure async function that transforms an `AgentState` object
- Edges define the order of node execution
- The graph is compiled once and invoked per turn with the current state
- State is a Pydantic model (`AgentState`) that accumulates context across turns

### Graph Structure

**Patient Graph** (primary workflow):
```
MemoryNode → IntentNode → WorkflowNode → ActionNode → StateWriterNode
```

**Doctor Graph** (physician assistant):
```
MemoryNode → IntentNode → StateWriterNode
(imperative pipeline, not a compiled StateGraph)
```

Each node has a single responsibility:
- `MemoryNode`: Load relevant memories from Redis/MongoDB into `state.memory`
- `IntentNode`: Classify the user's current intent using the LLM
- `WorkflowNode`: Set the correct `step` in `state.memory` based on intent and context
- `ActionNode` (patient only): Execute the actual business logic (call APIs, generate response)
- `StateWriterNode`: Persist the updated state back to Redis

### AgentState

The central data contract flowing through the graph is `AgentState` (defined in `graphs/shared/schemas.py`):

```python
class AgentState(BaseModel):
    session_id: str          # Redis key prefix; identifies the user session
    message: str             # Current user message
    memory: dict             # All accumulated context (step, intent, doctor_id, date, etc.)
    response: str            # Agent's response text (set by ActionNode)
    language: str            # Detected language: "english", "french", "arabic"
    role: str                # "patient" or "doctor"
```

The `memory` dict is the working state. It contains fields like:
- `step`: current workflow step (e.g., `"awaiting_date"`, `"ready_to_book"`)
- `intent`: most recently classified intent
- `specialty`: selected medical specialty
- `doctor_id`, `doctor_name`, `doctor_address`: selected doctor
- `date`, `time`: selected appointment date/time
- `appointment_list`: list of patient's appointments
- `selected_appointment_id`: appointment being cancelled/rescheduled
- `geo_results`: list of nearby places from geo search
- `profile`: patient's persistent MongoDB profile
- `semantic_memories`: retrieved long-term memories

---

## 4. Redis Memory Architecture

Redis serves as the **session state store** for the agent service. Every user session has a key namespace `session:{session_id}:*` in Redis.

**Why Redis?**
- Sub-millisecond read/write latency: critical for real-time chat
- Native support for hash maps: each workflow field stored as a separate key
- TTL support: sessions expire automatically after 30 minutes of inactivity
- Atomic operations: prevents race conditions in concurrent requests

**What is stored in Redis:**
- All `AgentState.memory` fields (serialized as Redis hash keys)
- Workflow step and intent from the previous turn
- Partial booking context (doctor, date, time collected so far)
- Semantic memory embeddings (retrieved from MongoDB, cached per turn)
- `workflow_started_at`: timestamp for session timeout enforcement

**Memory write**: `StateWriterNode` calls `RedisMemory.save_state()` which does a bulk `HSET` on the session namespace.

**Memory read**: `MemoryNode` calls `RedisMemory.load_state()` which does an `HGETALL` to restore the full session dictionary.

**Cross-workflow reset**: `WorkflowNode` calls `RedisMemory.delete_keys()` to surgically remove stale workflow fields when the user pivots to a new workflow. This prevents the ACTIVE_STEPS guard from incorrectly continuing an abandoned flow.

---

## 5. MongoDB Persistence

MongoDB is used for long-term, cross-session data persistence:

| Database | Collection | Owner Service | Purpose |
|---|---|---|---|
| `clinixai_db` | `patient_profiles` | auth_service + agent | Patient demographic and preference data |
| `clinixai_db` | `user_memories` | agent_service | Semantic memory entries with embeddings |
| `clinixai_db` | `workflow_snapshots` | agent_service | 24h TTL snapshots of workflow state |
| `clinixai_db` | `users` | auth_service | User accounts (email, password hash, role) |
| `disponibility` | `availabilities` | availability_service | Doctor recurring schedules |
| `disponibility` | `exceptions` | availability_service | Schedule overrides/closures/vacations |
| `medical_data_tunisia` | `doctors`, `pharmacies`, `clinics`, `hospitals`, `analysis_labs`, `nurses`, `physiotherapists`, `parapharmacies` | geo_service | Medical facility data extracted from Google Places |
| `eval_db` | `evaluation_results` | evaluation_service | Full evaluation result documents |

---

## 6. End-to-End Request Lifecycle

A complete patient request travels the following path:

```
Browser (Next.js)
    │
    ▼ POST /api/agent (Next.js API route proxy)
    │
    ▼ POST http://localhost:8001/chat (agent_service FastAPI)
    │
    ▼ patient_graph.ainvoke(AgentState)
    │
    ├── MemoryNode.run(state)
    │     └── RedisMemory.load_state(session_id)     → Redis HGETALL
    │     └── MongoDB patient_profiles lookup         → patient profile
    │     └── semantic_search(message, session_id)    → top-k memories
    │
    ├── IntentNode.run(state)
    │     └── Groq LLM API call (llama-3.3-70b-versatile, T=0)
    │     └── Classifies: intent, language, specialty, doctor_name, date, time
    │
    ├── WorkflowNode.run(state)
    │     ├── Cross-workflow reset (if user pivots)  → RedisMemory.delete_keys()
    │     └── Sets state.memory["step"] based on intent + context
    │
    ├── ActionNode.run(state)
    │     ├── Reads state.memory["step"]
    │     ├── If "searching_doctors" → availability_service HTTP call
    │     ├── If "searching_places"  → geo_service HTTP call
    │     ├── If "ready_to_book"     → appointment_service + availability_service
    │     ├── If "fetching_appointments" → appointment_service HTTP call
    │     └── Generates response text using LLM or template
    │
    └── StateWriterNode.run(state)
          └── RedisMemory.save_state(session_id, memory) → Redis HSET
          └── MongoDB user_memories update (if new facts extracted)
    │
    ▼ JSON response { response: "...", memory: {...} }
    │
    ▼ Frontend renders message in chat UI
```

Total latency: typically 1–4 seconds (dominated by Groq LLM API call in IntentNode + ActionNode).

---

## 7. Evaluation Pipeline Integration

The evaluation service operates as an independent microservice that assesses agent response quality. It is not in the critical path of patient-facing requests. Evaluation is triggered:
1. **Manually** by developers via the Evaluation dashboard's "Scenarios" tab
2. **Automatically** after each scenario run in the test suite
3. **Via API** (`POST /evaluate`) for integration testing

The evaluation pipeline:
1. Receives an `EvalRequest` (user_message, agent_response, reference_response, context)
2. Runs up to 9 LLM judge dimensions concurrently (using `asyncio.gather`)
3. Runs NLP metric computation (ROUGE, BLEU, BERTScore, EM, ESM) in parallel
4. Computes a weighted overall_score
5. Persists the `EvalResult` document to MongoDB
6. Returns the full result to the frontend dashboard

---

## 8. Multilingual Support

ClinixAI supports three languages: **English**, **French**, and **Arabic**. Multilingual support is implemented at multiple levels:

- **IntentNode**: The LLM prompt instructs the model to classify intent regardless of input language and to detect the language. The model handles code-switching (mixed French/Arabic).
- **ActionNode**: All response templates include language-conditional formatting.
- **Geo search**: The manual search normalizes multilingual terms (e.g., `"صيدلية"` → `"pharmacie"`, `"مستشفى"` → `"hopital"`) before querying MongoDB.
- **Evaluation**: The LLM judge evaluates multilingual consistency as a dedicated dimension. The text normalizer preserves Arabic and French characters.
- **Embeddings**: `paraphrase-multilingual-MiniLM-L12-v2` supports 50+ languages including Arabic and French for semantic memory retrieval.

---

## 9. Architecture Diagram (Textual)

```
┌──────────────────────────────────────────────────────────────┐
│                    NEXT.JS FRONTEND (3000)                    │
│   /patient    /doctor    /eval    API proxy routes            │
└────────┬──────────────┬────────────────┬─────────────────────┘
         │              │                │
         ▼              ▼                ▼
┌─────────────┐ ┌─────────────┐ ┌──────────────────┐
│ AGENT SVC   │ │  AUTH SVC   │ │  EVALUATION SVC  │
│   (8001)    │ │   (8005)    │ │     (8006)       │
│  LangGraph  │ │  JWT/bcrypt │ │  LLM Judge +     │
│  Patient +  │ │  MongoDB    │ │  NLP Metrics     │
│  Doctor     │ └─────────────┘ └────────┬─────────┘
│  Graphs     │                          │
└──┬──────────┘                   MongoDB eval_db
   │
   ├──► AVAILABILITY SVC (8002)  ◄──► appointment_service (8003)
   │         FastAPI, MongoDB
   │         Schedule management
   │
   ├──► GEO SERVICE (5000)
   │         Flask, MongoDB
   │         medical_data_tunisia
   │         Haversine proximity search
   │
   └──► REDIS (6379)
             Session memory
             Embeddings cache
             30-min TTL

         MongoDB (Atlas / Local)
         ├── clinixai_db
         │   ├── users
         │   ├── patient_profiles
         │   ├── user_memories
         │   └── workflow_snapshots
         ├── disponibility
         │   ├── availabilities
         │   └── exceptions
         └── medical_data_tunisia
             ├── doctors
             ├── pharmacies
             ├── clinics
             └── hospitals (+ 6 more)
```
