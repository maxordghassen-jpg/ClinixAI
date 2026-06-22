# ClinixAI — Redis Semantic Memory System

## 1. Why a Memory System?

A stateless AI assistant has no notion of who it is talking to beyond the current conversation. It cannot remember that a patient previously expressed a preference for Dr. Benali, cannot recall a past allergy disclosure, and cannot proactively suggest rebooking a cancelled appointment.

ClinixAI addresses this with a **five-layer memory architecture** that combines:
1. **Redis session memory** — fast, ephemeral, within-session state
2. **MongoDB patient profiles** — structured patient data
3. **MongoDB user memories with embeddings** — semantic long-term memories
4. **MongoDB workflow snapshots** — 24-hour TTL state snapshots
5. **Conversation history** — full turn-by-turn dialogue history

This design enables the system to behave as a continuous care assistant rather than a stateless query processor.

---

## 2. Layer 1: Redis Session Memory

**File**: `app/memory/redis_memory.py`

Redis holds all **within-session state** — every field that the agent accumulates across conversation turns in a single session.

### Key Schema

```
session:{session_id}:step                  → "awaiting_date"
session:{session_id}:intent                → "booking"
session:{session_id}:specialty             → "cardiologist"
session:{session_id}:doctor_id             → "507f1f77bcf86cd799439011"
session:{session_id}:doctor_name           → "Dr. Ben Salah"
session:{session_id}:doctor_address        → "12 Rue de la République, Tunis"
session:{session_id}:date                  → "2026-06-15"
session:{session_id}:time                  → "10:30"
session:{session_id}:language              → "french"
session:{session_id}:patient_id            → "patient-john-doe"
session:{session_id}:appointment_list      → "[{...}, {...}]"  (JSON string)
session:{session_id}:selected_appointment_id → "appt-123"
session:{session_id}:geo_results           → "[{...}, {...}]"  (JSON string)
session:{session_id}:workflow_started_at   → "1748390400.0"
session:{session_id}:conversation_history  → "[{role:user,content:...}, ...]"
```

### Operations

```python
class RedisMemory:
    
    async def load_state(session_id: str) -> dict:
        # HGETALL session:{session_id}:*
        # Returns all key-value pairs; JSON strings are parsed back to dicts/lists
    
    async def save_state(session_id: str, memory: dict) -> None:
        # HSET session:{session_id}:{k} v  for each k, v in memory
        # EXPIRE session:{session_id} 1800  (30 minutes TTL)
    
    async def delete_keys(session_id: str, keys: list[str]) -> None:
        # DEL session:{session_id}:{k}  for each k in keys
        # Used by WorkflowNode during cross-workflow reset
    
    async def semantic_search(
        query_embedding: list[float],
        session_id: str,
        top_k: int = 5,
    ) -> list[str]:
        # Retrieve cached memory embeddings and compute cosine similarity
        # Returns top-k most relevant memory text strings
```

### TTL Policy

Every `save_state` call resets the TTL to 1800 seconds (30 minutes) for the entire session namespace. A session that has been inactive for 30 minutes expires automatically, freeing Redis memory. On the next message from this user, MemoryNode will find an empty Redis namespace and start fresh — though MongoDB long-term memories persist indefinitely.

---

## 3. Layer 2: MongoDB Patient Profiles

**Collection**: `patient_profiles` in database `clinixai_db`

Created automatically by `auth_service` when a patient signs up. The `patient_profile_id` is derived from the email: `patient-{email_slug}`.

**Document schema:**
```json
{
  "patient_id": "patient-john-doe",
  "name": "John Doe",
  "email": "john.doe@example.com",
  "created_at": "2026-01-15T10:00:00Z",
  "updated_at": "2026-06-01T14:30:00Z",
  "preferences": {
    "language": "french",
    "appointment_time": "morning",
    "preferred_doctor_id": "507f1f77bcf86cd799439011"
  },
  "medical_notes": []
}
```

`MemoryNode` loads this document at the start of every turn and injects it as `state.memory["profile"]`. The LLM uses the profile to personalize responses — addressing the patient by name, using their preferred language, etc.

---

## 4. Layer 3: MongoDB User Memories with Embeddings

**Collection**: `user_memories` in database `clinixai_db`

This is the core of the **semantic memory system**. Each document represents a single atomic memory fact about a patient:

**Document schema:**
```json
{
  "_id": ObjectId("..."),
  "patient_id": "patient-john-doe",
  "content": "Patient prefers cardiologist appointments in the morning. Mentioned Dr. Benali by name.",
  "embedding": [0.023, -0.154, 0.087, ...],  // 384-dimensional float array
  "source": "conversation",
  "created_at": "2026-05-15T14:22:00Z",
  "tags": ["preference", "cardiology"]
}
```

The embedding is generated using `paraphrase-multilingual-MiniLM-L12-v2` (a sentence-transformer model). This model:
- Produces 384-dimensional dense vectors
- Supports 50+ languages including Arabic, French, and English natively
- Is optimized for semantic similarity (paraphrase detection)
- Is lightweight enough to run on CPU in real-time

### Semantic Retrieval Pipeline

When `MemoryNode` runs:

```python
# 1. Embed the current user message
query_embedding = embed(state.message)  # 384-dim vector

# 2. Fetch all user_memories for this patient from MongoDB
all_memories = await mongo.user_memories.find({"patient_id": patient_id})

# 3. Compute cosine similarity between query embedding and each memory
def cosine_similarity(a, b):
    return dot(a, b) / (norm(a) * norm(b))

scored = [(mem, cosine_similarity(query_embedding, mem["embedding"])) 
          for mem in all_memories]

# 4. Sort by similarity, return top-k content strings
top_k = sorted(scored, key=lambda x: -x[1])[:5]
return [mem["content"] for mem, _ in top_k]
```

The retrieved memory strings are then injected into `state.memory["semantic_memories"]` and passed to the LLM in the system prompt of ActionNode:

```
RELEVANT MEMORIES ABOUT THIS PATIENT:
- Patient prefers cardiologist appointments in the morning.
- Patient mentioned allergy to penicillin in previous session.
- Patient previously saw Dr. Ben Salah for cardiac checkup in March 2026.
```

### Memory Writing

`StateWriterNode` is responsible for **extracting and writing new memories**. After each turn, if the agent response or user message contains new medical facts, the system:

1. Uses the LLM to extract atomic facts from the conversation (e.g., "User mentioned morning preference", "User disclosed diabetes diagnosis")
2. Embeds each extracted fact using `paraphrase-multilingual-MiniLM-L12-v2`
3. Inserts a new `user_memories` document with the fact text and its embedding
4. Avoids duplicate storage by checking semantic similarity with existing memories (dedup threshold ~0.95)

---

## 5. Layer 4: MongoDB Workflow Snapshots

**Collection**: `workflow_snapshots` in database `clinixai_db`

Workflow snapshots provide **crash recovery** for in-progress workflows. If the Redis session expires during a multi-turn booking flow (e.g., the patient stepped away for 45 minutes), the workflow snapshot allows MemoryNode to restore the partial state.

**Document schema:**
```json
{
  "session_id": "abc123",
  "patient_id": "patient-john-doe",
  "step": "awaiting_date",
  "intent": "booking",
  "specialty": "cardiologist",
  "doctor_id": "507f1f77bcf86cd799439011",
  "doctor_name": "Dr. Ben Salah",
  "saved_at": "2026-06-01T14:35:00Z",
  "ttl": "2026-06-02T14:35:00Z"
}
```

TTL: 24 hours. Snapshots older than 24 hours are automatically cleaned up by a MongoDB TTL index.

---

## 6. Layer 5: Conversation History

The full conversation history is stored in Redis as a JSON-serialized list under key `session:{session_id}:conversation_history`.

Each entry:
```json
{"role": "user", "content": "I want to book an appointment with a cardiologist"}
{"role": "assistant", "content": "I found 3 cardiologists available. Which one would you prefer?"}
```

The conversation history is injected into the LLM context on every turn, allowing the model to reference earlier parts of the dialogue (e.g., "the second option you showed me").

The history is **bounded** — only the last N turns (typically 10) are kept in the prompt to avoid token limit overflow.

---

## 7. Rebooking Flow: Memory-Driven Proactivity

A key demonstration of the semantic memory system's value is the **rebooking flow**:

1. Patient books appointment with Dr. Ben Salah for cardiac checkup
2. StateWriterNode stores: "Patient booked cardiac checkup with Dr. Ben Salah (ID: 507f...) on 2026-06-15"
3. Patient cancels the appointment
4. StateWriterNode stores: "Patient cancelled cardiac checkup (2026-06-15)"
5. **Two weeks later**, patient returns and says "I need to see a doctor"
6. MemoryNode retrieves the memory about the previous booking
7. IntentNode receives context: "Patient previously booked cardiology, cancelled"
8. ActionNode proactively suggests: "I see you previously had an appointment with Dr. Ben Salah for a cardiac checkup. Would you like to rebook with him?"

This behavior is only possible because of the persistent semantic memory system.

---

## 8. Memory Relevance Scoring in Evaluation

The evaluation system measures **memory relevance** as one of its 9 LLM judge dimensions. The judge prompt asks:

> "Does the agent response demonstrate awareness of relevant user history and preferences? Did it leverage known facts about this patient appropriately?"

Score interpretation:
- **0.9–1.0**: Agent explicitly references a relevant memory and uses it to personalize the response
- **0.7–0.9**: Agent's response is consistent with known preferences but doesn't explicitly reference them
- **0.5–0.7**: Agent ignores available memories but still gives a correct generic response
- **<0.5**: Agent's response contradicts known patient preferences or facts

---

## 9. Embedding Model: `paraphrase-multilingual-MiniLM-L12-v2`

| Property | Value |
|---|---|
| Dimensions | 384 |
| Languages | 50+ (including Arabic, French, English) |
| Model size | ~120MB |
| Inference speed | ~10ms per sentence on CPU |
| Training objective | Paraphrase similarity via contrastive learning |
| Architecture | 12-layer MiniLM transformer |

This model was chosen over alternatives because:
- **Multilingual out of the box**: No separate models needed for Arabic/French/English
- **Lightweight**: Runs on CPU without GPU infrastructure
- **Paraphrase-optimized**: Sentences with the same meaning (in different languages) map to nearby embeddings — critical for cross-lingual memory retrieval
- **384 dimensions**: Small enough for fast cosine similarity computation without PCA/quantization
