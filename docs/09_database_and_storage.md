# ClinixAI — Databases & Storage Architecture

## 1. Storage Technology Overview

ClinixAI uses two storage technologies:

| Technology | Role | Why Chosen |
|---|---|---|
| **MongoDB** | Persistent long-term storage | Schema flexibility, document orientation, geospatial queries, cloud Atlas |
| **Redis** | Ephemeral session state | Sub-millisecond latency, native TTL, hash data structures, pub/sub |

---

## 2. MongoDB Databases and Collections

### Database: `clinixai_db` (Core Application Data)

#### Collection: `users`
**Owner**: `auth_service`  
**Purpose**: User account storage for authentication

Schema:
```json
{
    "_id": ObjectId,
    "email": string (unique, indexed),
    "password_hash": string (bcrypt),
    "role": "patient" | "doctor",
    "name": string,
    "patient_profile_id": string | null,   // e.g. "patient-john-doe"
    "doctor_id": string | null,             // links to doctor record
    "created_at": datetime,
    "is_active": boolean
}
```
Indexes: `{ email: 1, unique: true }`

#### Collection: `patient_profiles`
**Owner**: `auth_service` (create on signup) + `agent_service` (update)  
**Purpose**: Patient demographic and preference data used by the AI agent

Schema:
```json
{
    "_id": ObjectId,
    "patient_id": string (e.g. "patient-john-doe", indexed),
    "name": string,
    "email": string,
    "created_at": datetime,
    "updated_at": datetime,
    "preferences": {
        "language": "english" | "french" | "arabic",
        "appointment_time": "morning" | "afternoon" | "evening",
        "preferred_doctor_id": string | null
    },
    "medical_notes": [string]
}
```
Indexes: `{ patient_id: 1, unique: true }`

#### Collection: `user_memories`
**Owner**: `agent_service`  
**Purpose**: Semantic long-term memories with vector embeddings for retrieval

Schema:
```json
{
    "_id": ObjectId,
    "patient_id": string (indexed),
    "content": string,                          // Human-readable memory text
    "embedding": [float × 384],                 // paraphrase-multilingual-MiniLM-L12-v2 vector
    "source": "conversation" | "profile" | "booking",
    "created_at": datetime,
    "tags": [string]
}
```
Indexes: `{ patient_id: 1 }` (compound with score for future vector index)

**Storage implication**: Each embedding is 384 floats × 4 bytes = ~1.5KB per memory. A patient with 100 memories uses ~150KB for embeddings alone. MongoDB stores these as BSON arrays.

#### Collection: `workflow_snapshots`
**Owner**: `agent_service`  
**Purpose**: 24-hour crash recovery snapshots of in-progress workflow state

Schema:
```json
{
    "_id": ObjectId,
    "session_id": string,
    "patient_id": string,
    "step": string,
    "intent": string,
    "specialty": string | null,
    "doctor_id": string | null,
    "doctor_name": string | null,
    "date": string | null,
    "time": string | null,
    "saved_at": datetime,
    "ttl": datetime (TTL index field)
}
```
Indexes: `{ ttl: 1, expireAfterSeconds: 0 }` (MongoDB TTL index for auto-expiry)

---

### Database: `disponibility` (Scheduling Data)

#### Collection: `availabilities`
**Owner**: `availability_service`  
**Purpose**: Doctor recurring weekly schedules

Schema:
```json
{
    "_id": ObjectId,
    "doctorId": string (indexed),
    "day": "lundi" | "mardi" | ... (indexed),
    "ranges": [{ "start": "HH:MM", "end": "HH:MM" }],
    "consultationDurationMinutes": integer (default 30),
    "slots": [{ "start": "HH:MM", "end": "HH:MM", "status": "available"|"blocked" }],
    "createdAt": datetime,
    "updatedAt": datetime
}
```
Indexes: `{ doctorId: 1, day: 1, unique: true }` (one schedule per doctor per day)

#### Collection: `exceptions`
**Owner**: `availability_service`  
**Purpose**: Date-specific schedule overrides

Schema:
```json
{
    "_id": ObjectId,
    "doctor_id": string,
    "date": "YYYY-MM-DD" (indexed),
    "type": "closure" | "vacation" | "override",
    "overrideRanges": [{ "start": "HH:MM", "end": "HH:MM" }]
}
```
Indexes: `{ doctor_id: 1, date: 1 }`

---

### Database: `disponibility` (or separate) — Appointments

#### Collection: `appointments`
**Owner**: `appointment_service`

Schema:
```json
{
    "_id": ObjectId,
    "patient_id": string (indexed),
    "doctor_id": string (indexed),
    "date": "YYYY-MM-DD" (indexed),
    "time": "HH:MM",
    "status": "pending" | "confirmed" | "cancelled" | "rejected",
    "created_at": datetime,
    "updated_at": datetime,
    "notes": string | null
}
```
Indexes:
- `{ patient_id: 1 }` (list by patient)
- `{ doctor_id: 1, date: 1 }` (availability check — most frequent query)

---

### Database: `eval_db` (Evaluation Data)

#### Collection: `evaluation_results`
**Owner**: `evaluation_service`  
**Purpose**: Full evaluation result documents for analytics and trend rendering

Schema (abbreviated):
```json
{
    "_id": ObjectId,
    "scenario_id": string | null,
    "hallucination_risk": float,
    "groundedness_score": float,
    "safety_score": float,
    "workflow_score": float,
    "conversational_quality": float,
    "memory_relevance": float,
    "personalization_quality": float,
    "dimensions": { "safety": { "score": float, "explanation": string }, ... },
    "bert_score": float,
    "rouge1": float,
    "rouge2": float,
    "rougeL": float,
    "bleu_score": float,
    "exact_match": float,
    "overall_score": float,
    "judge_explanation": string,
    "latency_ms": float,
    "evaluated_at": string (ISO datetime),
    "model_used": string,
    "user_message": string,
    "agent_response": string,
    "reference_response": string | null,
    "language": string,
    "role": string,
    "tags": [string]
}
```
Indexes: `{ evaluated_at: -1 }` (most recent first for history queries)

**Query patterns:**
- History list: `find({}, projection).sort(evaluated_at, -1).limit(N)`
- Trends: `find({scenario_id: X}, small_projection).sort(evaluated_at, 1).limit(200)`
- Single result: `find_one({_id: ObjectId(id)})`
- Compare: Two individual `find_one` queries

---

### Database: `medical_data_tunisia` (Geo Data)

**Owner**: `geo_service`

Collections (one per medical category):
- `doctors` — medical practitioners with specialty
- `pharmacies` — pharmacies
- `on_call_pharmacies` — on-call/garde pharmacies
- `night_pharmacies` — night pharmacies
- `parapharmacies` — parapharmacies
- `clinics` — private clinics
- `hospitals` — public/private hospitals
- `analysis_labs` — medical analysis laboratories
- `nurses` — nursing professionals
- `physiotherapists` — physiotherapy professionals

Common document schema:
```json
{
    "_id": ObjectId,
    "place_id": string (Google Places ID, unique),
    "name": string,
    "address": string,
    "coordinates": { "lat": float, "lng": float },
    "phone_number": string | null,
    "website": string | null,
    "rating": float | null,
    "user_ratings_total": integer | null,
    "specialty": string | null,             // doctors only
    "governorate": string,
    "collection_type": string,              // "doctor", "pharmacy", etc.
    "types": [string],                      // Google Places types
    "opening_hours": { "weekday_text": [...], "open_now": boolean },
    "image_url": string | null,
    "google_maps_url": string | null,
    "business_status": "OPERATIONAL" | "CLOSED_TEMPORARILY" | "CLOSED_PERMANENTLY",
    "search_query": string,                 // query that found this record
    "last_updated": string
}
```
Indexes:
- `{ "coordinates.lat": 1, "coordinates.lng": 1 }` (geospatial)
- `{ "specialty": 1 }` (doctor specialty filter)
- `{ "governorate": 1 }` (regional filter)
- `{ "place_id": 1, unique: true }` (deduplication)

---

## 3. Redis Key Architecture

Redis is used exclusively by the `agent_service` for session state management.

### Key Namespace

```
session:{session_id}:{field}
```

Where `session_id` is a UUID generated by the frontend for each browser session.

### Stored Fields

| Redis Key | Type | Example Value | TTL |
|---|---|---|---|
| `session:{id}:step` | String | `"awaiting_date"` | 30min |
| `session:{id}:intent` | String | `"booking"` | 30min |
| `session:{id}:language` | String | `"french"` | 30min |
| `session:{id}:patient_id` | String | `"patient-john-doe"` | 30min |
| `session:{id}:specialty` | String | `"cardiologist"` | 30min |
| `session:{id}:doctor_id` | String | `"507f..."` | 30min |
| `session:{id}:doctor_name` | String | `"Dr. Ben Salah"` | 30min |
| `session:{id}:date` | String | `"2026-06-22"` | 30min |
| `session:{id}:time` | String | `"10:30"` | 30min |
| `session:{id}:appointment_list` | String (JSON) | `"[{...}]"` | 30min |
| `session:{id}:geo_results` | String (JSON) | `"[{...}]"` | 30min |
| `session:{id}:workflow_started_at` | String | `"1748390400.0"` | 30min |
| `session:{id}:conversation_history` | String (JSON) | `"[{role:user,...}]"` | 30min |
| `session:{id}:pending_action` | String | `"cancel"` | 30min |

### TTL Management

Every `save_state()` call resets the TTL on all session keys to 1800 seconds (30 minutes). If a session is inactive for 30 minutes, all keys expire automatically. This:
- Prevents Redis memory exhaustion from abandoned sessions
- Forces fresh context loading after extended gaps
- Aligns with reasonable healthcare consultation session lengths

### Cross-Workflow Reset

During `WorkflowNode` cross-workflow reset, `delete_keys()` is called:
```python
await redis.delete(f"session:{session_id}:step")
await redis.delete(f"session:{session_id}:specialty")
await redis.delete(f"session:{session_id}:doctor_id")
await redis.delete(f"session:{session_id}:date")
await redis.delete(f"session:{session_id}:time")
# etc.
```

This surgical deletion prevents stale booking context from contaminating a new workflow.

---

## 4. Data Flow Between Storage Layers

```
User sends message
    │
    ├── Redis: load_state() → session context (workflow step, partial booking, etc.)
    ├── MongoDB patient_profiles → patient name, preferences
    ├── MongoDB user_memories → embed message → cosine search → top-k memories
    │
Agent processes message (LangGraph pipeline)
    │
    ├── If booking: MongoDB availabilities + appointment_service
    ├── If geo_search: MongoDB medical_data_tunisia (via geo_service)
    │
Agent writes response
    │
    ├── Redis: save_state() → persist updated workflow state
    ├── MongoDB user_memories: extract + embed new facts → upsert
    ├── MongoDB workflow_snapshots: save crash recovery snapshot
    │
Evaluation (optional)
    │
    └── MongoDB eval_db.evaluation_results: persist full EvalResult document
```
