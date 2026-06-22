# ClinixAI — End-to-End Request Flows

## Flow 1: Patient Appointment Booking (Full 4-Turn Workflow)

**Scenario**: Patient sends "I urgently need a cardiologist" in a fresh session.

---

### Turn 1: Intent Detection and Doctor Search

**User**: "I urgently need a cardiologist"

```
Browser
  │  POST /api/agent { message, session_id, role:"patient", patient_id }
  ▼
Next.js API Proxy (lib/proxy.ts)
  │  Forward to http://localhost:8001/chat
  ▼
agent_routes.py — POST /chat
  │  Build AgentState { session_id:"abc123", message:"I urgently need...", role:"patient" }
  ▼
patient_graph.ainvoke(state)
  │
  ├── [MemoryNode]
  │     • Redis HGETALL session:abc123:* → {} (empty, fresh session)
  │     • MongoDB patient_profiles.find_one({patient_id:"patient-john-doe"})
  │       → { name:"John Doe", preferences:{language:"english"} }
  │     • Generate embedding for "I urgently need a cardiologist"
  │     • Redis semantic_search() → [] (no prior memories yet)
  │     • state.memory = { patient_id:"patient-john-doe", profile:{name:"John Doe"}, semantic_memories:[] }
  │
  ├── [IntentNode]
  │     • Groq API call (llama-3.3-70b, T=0)
  │     • System prompt: "Classify intent. Available intents: booking, doctor_search, ..."
  │     • Response: { intent:"booking", language:"english", specialty:"cardiologist" }
  │     • state.memory += { intent:"booking", language:"english", specialty:"cardiologist" }
  │
  ├── [WorkflowNode]
  │     • current_step = None (fresh session)
  │     • No cross-workflow reset needed
  │     • intent="booking", doctor_id=None, specialty="cardiologist"
  │     → new_step = "searching_doctors" (has specialty but no doctor_id)
  │     • state.memory["step"] = "searching_doctors"
  │     • state.memory["workflow_started_at"] = 1748390400.0
  │
  ├── [ActionNode]
  │     • step = "searching_doctors"
  │     • GET http://localhost:8002/availability/doctors?specialty=cardiologist
  │       → [{ doctor_id:"doc-ben-salah", name:"Dr. Ben Salah", address:"Tunis Centre" },
  │            { doctor_id:"doc-khelifi", name:"Dr. Khelifi", address:"Lac" },
  │            { doctor_id:"doc-mansour", name:"Dr. Mansour", address:"Carthage" }]
  │     • state.memory["doctors_list"] = [...]
  │     • Generate response: "I understand this is urgent. I found 3 cardiologists:
  │         (1) Dr. Ben Salah — Tunis Centre ⭐4.8
  │         (2) Dr. Khelifi — Lac ⭐4.6
  │         (3) Dr. Mansour — Carthage ⭐4.5
  │         Which doctor would you prefer?"
  │
  └── [StateWriterNode]
        • Redis HSET session:abc123:step "searching_doctors"
        • Redis HSET session:abc123:intent "booking"
        • Redis HSET session:abc123:specialty "cardiologist"
        • Redis HSET session:abc123:workflow_started_at "1748390400.0"
        • Redis HSET session:abc123:doctors_list "[{...}]"
        • Redis EXPIRE session:abc123 1800
        • No new memories to extract

Response → { response:"I understand this is urgent...", memory:{step:"searching_doctors",...} }
```

---

### Turn 2: Doctor Selection

**User**: "The first one"

```
[MemoryNode]
  • Redis HGETALL → { step:"searching_doctors", specialty:"cardiologist", doctors_list:"[...]", ... }
  • Merge into state.memory (restores full session context)

[IntentNode]
  • CONTEXTUAL OVERRIDE RULE 4: step="searching_doctors" + numeric input → intent="select_doctor"
  • state.memory["intent"] = "select_doctor"
  • state.memory["selected_index"] = 1

[WorkflowNode]
  • current_step = "searching_doctors" (in ACTIVE_STEPS? No, it's only step guard for ActionNode)
  • intent = "select_doctor"
  → state.memory["step"] = "doctor_selected"

[ActionNode]
  • step = "doctor_selected"
  • Resolves index 1 from doctors_list → { doctor_id:"doc-ben-salah", name:"Dr. Ben Salah", address:"Tunis Centre" }
  • state.memory["doctor_id"] = "doc-ben-salah"
  • state.memory["doctor_name"] = "Dr. Ben Salah"
  • state.memory["doctor_address"] = "Tunis Centre"
  • Response: "Dr. Ben Salah selected. 📅 What date would you like for your appointment?"

[StateWriterNode]
  • Redis HSET: doctor_id, doctor_name, doctor_address, step="awaiting_date"
  • Redis EXPIRE session 1800
```

---

### Turn 3: Date Selection

**User**: "Next Monday, June 22nd"

```
[IntentNode]
  • { intent:"booking", date:"2026-06-22" }

[WorkflowNode]
  • intent="booking", doctor_id="doc-ben-salah" (exists), date=None → awaiting_time
  • Actually: date just extracted, so step="awaiting_time"

[ActionNode]
  • step = "awaiting_time"
  • GET http://localhost:8002/availability/free-slots
    ?doctor_id=doc-ben-salah&day=lundi&date=2026-06-22
    
    (availability_service internal logic):
    1. Check exceptions for doc-ben-salah on 2026-06-22 → none
    2. Load template for (doc-ben-salah, "lundi"):
       ranges:[{start:"09:00",end:"12:00"},{start:"14:00",end:"17:30"}]
       consultationDurationMinutes: 30
    3. generate_slots_from_ranges → [09:00,09:30,10:00,10:30,11:00,11:30,14:00,...,17:00]
    4. GET http://localhost:8003/appointments/date/doc-ben-salah?date=2026-06-22
       → [{ time:"09:00", status:"confirmed" }, { time:"14:30", status:"confirmed" }]
    5. Remove 09:00, 14:30 → remaining: [09:30,10:00,10:30,11:00,11:30,14:00,15:00,...]
  
  • state.memory["available_slots"] = ["09:30","10:00","10:30","11:00","11:30"]
  • Response: "Available slots with Dr. Ben Salah on June 22:
      09:30, 10:00, 10:30, 11:00, 11:30, 14:00, 15:00...
      Which time works best for you?"

[StateWriterNode]
  • Redis HSET: date="2026-06-22", available_slots="[...]", step="awaiting_time"
```

---

### Turn 4: Time Selection and Booking Confirmation

**User**: "Ten o'clock"

```
[IntentNode]
  • { intent:"booking", time:"10:00" }

[WorkflowNode]
  • doctor_id exists, date exists, time just extracted → step="ready_to_book"

[ActionNode]
  • step = "ready_to_book"
  • POST http://localhost:8003/appointments
    { patient_id:"patient-john-doe", doctor_id:"doc-ben-salah", date:"2026-06-22", time:"10:00" }
    → 201 { appointment_id:"appt-789", status:"confirmed" }
  
  • POST http://localhost:8002/availability/book
    { doctor_id:"doc-ben-salah", day:"lundi", start:"10:00" }
    → 200 (slot marked booked for legacy blocking, though template is not mutated)
  
  • state.memory["appointment_id"] = "appt-789"
  • Response: "✅ Confirmed! Your appointment with Dr. Ben Salah is booked:
      📅 Monday, June 22 | ⏰ 10:00 AM | 📍 Tunis Centre
      Your appointment ID: appt-789"

[StateWriterNode]
  • Redis HSET: appointment_id, step="idle"
  • Memory extraction:
    LLM extracts: "Patient booked cardiology appointment with Dr. Ben Salah on 2026-06-22 at 10:00"
    Embed this fact → MongoDB user_memories.insert({patient_id, content, embedding:[...]})
```

---

## Flow 2: Rebooking Flow (Memory-Driven)

**Scenario**: Patient returns after cancelling their appointment.

```
Patient returns, new session (session_id="xyz999")

User: "I need to see a doctor again"

[MemoryNode]
  • Fresh Redis session → empty
  • MongoDB patient_profiles → profile
  • Embed "I need to see a doctor again"
  • MongoDB user_memories cosine search:
    Query embedding vs stored memories:
    - "Patient booked cardiology appointment with Dr. Ben Salah on 2026-06-22" → similarity: 0.87
    - "Patient cancelled appointment with Dr. Ben Salah (2026-06-22)" → similarity: 0.82
    → top-2 returned as semantic_memories

[IntentNode]
  • Receives: user message + semantic_memories in system context
  • Classifies: intent="booking", specialty="cardiologist" (inferred from memory)
  • Note: LLM sees the past booking memory and can infer specialty

[ActionNode]
  • Proactive response: "I see you previously had a cardiology appointment with Dr. Ben Salah that was
    cancelled. Would you like to rebook with him, or search for a different cardiologist?"
```

---

## Flow 3: Geo-Search / Doctor Discovery Flow

**Scenario**: Patient asks "Find a pharmacy near me".

```
User: "Find a pharmacy near me"
(Frontend sends user GPS coordinates: { lat: 36.8190, lng: 10.1658 })

[IntentNode]
  • { intent:"geo_search", specialty:null }
  • category inferred: "pharmacy" (from "pharmacie"/"pharmacy" keyword)

[WorkflowNode]
  • step = "searching_places"

[ActionNode]
  • step = "searching_places"
  • POST http://localhost:5000/api/nearby
    { latitude: 36.82, longitude: 10.17, category:"pharmacies", radius: 5, limit: 10 }
    
    (geo_service Flask app):
    1. Query MongoDB medical_data_tunisia.pharmacies collection
    2. For each doc with coordinates: haversine_distance(36.82, 10.17, doc.lat, doc.lng)
    3. Filter distance ≤ 5km → 6 results
    4. Sort by distance ascending
    5. Format with distance_text
    → [{ name:"Pharmacie Centrale", distance:0.3, coordinates:{lat:36.82,lng:10.17},
          phone:"+216 71 000 001", opening_hours:["Lundi: 08:00–20:00",...] }, ...]

  • state.memory["geo_results"] = [6 pharmacies]
  • Response: "I found 6 pharmacies near you:
      1. Pharmacie Centrale — 0.3 km · Open now
      2. Pharmacie du Lac — 0.8 km · Open now
      3. Pharmacie El Menzah — 1.2 km · Closed
      ...
      [MAP PINS UPDATED]"

[StateWriterNode]
  • Redis: step="selecting_place", geo_results="[...]"

Frontend:
  • Parses geo_results from response metadata
  • Updates mapPins state → MapLibre re-renders with 6 pharmacy markers
  • Map auto-fits to show all pins
```

---

## Flow 4: Evaluation Flow

**Scenario**: Developer clicks "Run" on scenario WFLOW-001.

```
Frontend eval/page.tsx
  │  POST /api/eval/scenarios/WFLOW-001/run
  ▼
eval_routes.py
  │  Load scenario from datasets/eval_scenarios.py:
  │  { user_message:"I urgently need a cardiologist", 
  │    reference_response:"I understand this is urgent...",
  │    category:"workflow" }
  │  Build EvalRequest { ..., include_bleu: True (has reference) }
  ▼
EvalOrchestrator.evaluate(request)
  │
  ├── asyncio.gather() — concurrent execution:
  │   ├── LLM judge: safety_prompt → Groq API → { score:0.98, explanation:"..." }
  │   ├── LLM judge: hallucination_prompt → Groq API → { score:0.08, explanation:"..." }
  │   ├── LLM judge: groundedness_prompt → Groq API → { score:0.95, explanation:"..." }
  │   ├── LLM judge: workflow_prompt → Groq API → { score:0.92, explanation:"..." }
  │   ├── LLM judge: conversational_quality_prompt → Groq API → { score:0.88, explanation:"..." }
  │   ├── compute_rouge_scores(candidate, reference) → { rouge1:0.72, rouge2:0.61, rougeL:0.69 }
  │   ├── compute_bleu_score(candidate, reference) → 0.58
  │   └── compute_bert_score(candidate, reference) → 0.84
  │
  ├── Overall score computation:
  │   = 0.20×0.98 + 0.14×(1-0.08) + 0.10×0.95 + 0.17×0.92 + 0.14×0.88 + ...
  │   = 0.196 + 0.129 + 0.095 + 0.156 + 0.123 + ...
  │   ≈ 0.87
  │
  ├── result_store.save_result(eval_result)
  │   → MongoDB eval_db.evaluation_results.insert_one({...})
  │   → Returns ObjectId string
  │
  ▼
Response: EvalResult { overall_score:0.87, safety_score:0.98, hallucination_risk:0.08, ... }

Frontend:
  • setLastResult(result) → switches to Results tab
  • setSessionResults(prev => [...prev, result])
  • fetchTrends() → GET /api/eval/trends → updated TrendResponse with new data point
  • setTrends(t) → unifiedTimeline recomputed → curve charts gain new data point
```

---

## Flow 5: Memory Retrieval Flow

**Scenario**: Patient starts a new session, asks "What was I doing last time?"

```
User: "What was I doing last time?"

[MemoryNode]
  1. Embed "What was I doing last time?" using paraphrase-multilingual-MiniLM-L12-v2
     → vector = [0.023, -0.154, ..., 0.087]  (384 dimensions)
  
  2. MongoDB user_memories.find({ patient_id: "patient-john-doe" })
     → 8 memory documents with embeddings
  
  3. Cosine similarity computation:
     Memory A: "Patient booked cardiology appointment with Dr. Ben Salah on 2026-06-22 at 10:00"
     similarity = dot(query, A) / (|query| × |A|) = 0.87
     
     Memory B: "Patient mentioned preference for morning appointments"
     similarity = 0.61
     
     Memory C: "Patient cancelled appointment 2026-06-22 due to schedule conflict"
     similarity = 0.84
     
     [sorted: A(0.87), C(0.84), B(0.61), ...]
  
  4. top_k = 3 → inject into state.memory["semantic_memories"]

[ActionNode — idle step]
  • LLM receives system prompt:
    "RELEVANT MEMORIES ABOUT THIS PATIENT:
     - Patient booked cardiology appointment with Dr. Ben Salah on 2026-06-22 at 10:00
     - Patient cancelled appointment 2026-06-22 due to schedule conflict
     - Patient mentioned preference for morning appointments"
  
  • LLM generates: "Based on your history, you had booked an appointment with Dr. Ben Salah
    (cardiologist) for June 22nd at 10:00 AM, but you later cancelled it. Would you like 
    to rebook with him?"
```

---

## Flow 6: Doctor Assistant Flow

**Scenario**: Doctor asks "How many appointments do I have tomorrow?"

```
User (doctor): "How many appointments do I have tomorrow?"
(role = "doctor", doctor_id = "doc-ben-salah-123")

agent_routes.py
  • role = "doctor" → run_doctor_pipeline(state)

[Doctor MemoryNode]
  • Redis: load doctor session state
  • MongoDB: load doctor profile (from doctors collection, not patient_profiles)
  • No semantic memory search for doctor sessions

[IntentNode (shared)]
  • intent = "view_appointments" (doctor variant)
  • date = "2026-06-15" (computed from "tomorrow")

[Doctor ActionNode (implicit)]
  • GET http://localhost:8003/appointments/doctor/doc-ben-salah-123?date=2026-06-15
    → 4 appointments
  • LLM generates: "You have 4 appointments tomorrow:
      09:00 — Ahmed Ben Ali (cardiology checkup)
      10:00 — Fatima Khelifi (follow-up)
      14:30 — Mohamed Trabelsi (new patient)
      16:00 — Leila Bouzid (echocardiogram)"

[Doctor StateWriterNode]
  • Redis: save doctor session state
  • No memory extraction for doctor sessions
```

---

## Flow 7: Multilingual Flow (Arabic Input)

**Scenario**: Arabic-speaking patient asks for an appointment.

```
User: "أريد موعد مع طبيب قلب"
(Translation: "I want an appointment with a cardiologist")

[IntentNode]
  • llama-3.3-70b-versatile understands Arabic natively
  • Specialty normalization rule: "طبيب قلب" → "cardiologist"
  • Response: { intent:"booking", language:"arabic", specialty:"cardiologist" }
  • state.memory["language"] = "arabic"

[ActionNode]
  • All subsequent responses in Arabic
  • Doctor list presented in Arabic format
  • Confirmation messages in Arabic

[Evaluation — if run]
  • text_normalizer.normalize() preserves Arabic characters
  • LLM judge evaluates multilingual_consistency dimension:
    "Does the agent maintain consistent Arabic throughout the response?"
  • BERTScore uses bert-base-multilingual-cased (supports Arabic)
  • ROUGE with use_stemmer=True handles Arabic stemming
```
