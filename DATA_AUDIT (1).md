# ClinixAI Data Audit

This audit describes the data model implemented in code as of 2026-06-21. It intentionally ignores the architecture docs except where the code itself confirms the behavior.

## Executive Map

```text
Browser
  localStorage: clinix-auth
  sessionStorage: clinix-map-state
  in-memory Zustand chat stores
        |
Frontend API routes / gateway
        |
agent_service
  Redis: {session_id}:memory
  Mongo clinix_agent:
    users, patient_profiles, user_memories, workflow_snapshots,
    memory_summaries, preconsultation_data, preconsultation_reports,
    reminder_jobs, chat_history
        |
appointment_service
  Mongo appointment_reservation.reservations
        |
availability_service
  Mongo disponibility.disponibilites
  Mongo disponibility.availability_exceptions
        |
geo_service
  Mongo medical_data_tunisia:
    doctors, pharmacies, on_call_pharmacies, night_pharmacies,
    parapharmacies, clinics, hospitals, analysis_labs, nurses,
    physiotherapists
        |
evaluation_service
  Mongo evaluation_results + split metric collections
  JSON fallback: evaluation_service/evaluation_results.json
```

## 1. Data Inventory

### `clinix_agent.users`

Owner: `auth_service`. Created by patient signup and doctor seeding.

Code references:
- Collection constant and CRUD: `auth_service/app/repositories/user_repository.py:8`, `:13`, `:25`.
- Patient signup creates user and patient profile stub: `auth_service/app/services/auth_service.py:20`, `:48`, `:75`.
- Login reads and may repair `patient_profile_id`: `auth_service/app/services/auth_service.py:102`, `:123`, `:135`, `:149`, `:171`.
- Doctor demo users link to real geo doctor ObjectIds: `auth_service/scripts/seed_doctors.py:7`, `:82`, `:110`.

Fields:

| Field | Meaning | Written by | Updated by | Read by | Used? |
|---|---|---|---|---|---|
| `email` | Login identity, unique key | signup, doctor seed | never normally | login, profile fallback, appointment enrichment | yes |
| `password_hash` | Hashed auth secret | signup, doctor seed | not changed in code | login | yes |
| `role` | `patient` or `doctor` | signup, doctor seed | not changed | auth, history, doctor/patient routing | yes |
| `name` | Display name | signup, doctor seed | doctor seed may update, profile fallback reads it | profile backfill, appointment enrichment, doctor report patient lookup | yes |
| `patient_profile_id` | Link from auth user to `patient_profiles.patient_id` | signup | login migration repair | frontend identity, profile service, agent routes | yes; identity-critical |
| `doctor_id` | For doctors: `medical_data_tunisia.doctors._id` string | doctor seed | doctor seed may repair | doctor chat, appointments, availability | yes |
| `created_at` | Account creation timestamp | signup/seed | no | not materially used | mostly metadata |
| `is_active` | Login enable flag | signup/seed | no update path found | login | yes |

### `clinix_agent.patient_profiles`

Owner: split between `auth_service` for identity/medical profile and `agent_service` for behavioral profile.

Code references:
- Agent repository owns behavioral writes: `agent_service/app/repositories/patient_profile_repo.py:29`, `:101`, `:150`, `:183`, `:209`, `:248`, `:344`.
- Auth profile repository owns manual profile writes: `auth_service/app/repositories/profile_repository.py:10`, `:83`, `:141`.
- Auth profile schema exposes medical + AI fields: `auth_service/app/schemas/medical_profile.py:4`, `:28`, `:38`.
- Patient memory service writes booking/language/reminders/preconsultation stats: `agent_service/app/services/patient_memory_service.py:70`, `:149`, `:202`, `:251`, `:281`.
- Patient memory node reads profile every turn: `agent_service/graphs/patient/nodes/memory_node.py:49`.

Fields:

| Field | Meaning | Written by | Updated when | Read by | Used? |
|---|---|---|---|---|---|
| `patient_id` | Canonical patient identity | signup stub, seed, agent upserts | never except migration scripts | auth, agent, reports, appointments enrichment | yes; source of truth for patient identity |
| `name`, `email` | identity/contact | signup stub, seed, profile edit | profile edit; auth backfills from users if absent | UI profile, doctor report lookup, appointment enrichment | yes |
| `phone`, `gender` | profile/contact | seed/profile edit | manual profile edit | UI profile, report snapshot | yes |
| `preferences` | generic manual preferences blob | profile edit | manual profile edit | UI profile output only | weakly used; not used by agent decisions |
| `weight`, `height`, `blood_type`, `date_of_birth`, `address`, `city`, `smoking_status`, `alcohol_consumption`, `allergies`, `chronic_conditions`, `current_medications`, `past_surgeries`, `family_history`, `emergency_contact_*` | medical profile | profile form/API | manual profile patch/update | preconsultation summary/report, profile UI, memory context for safety | yes |
| `language` | patient preferred/current conversation language | `PatientMemoryService.update_language()` | after successful booking if session language differs from profile | patient MemoryNode seeds Redis; MemoryContextBuilder injects context | yes; operational source for session seeding |
| `appointment_history[]` | bounded list of completed/cancelled/rescheduled appointment facts | `record_booking()` | booking success; status changed on cancel/reschedule | memory context, UI/debug scripts | yes, but duplicated with `reservations` |
| `appointment_history[].appointment_id` | link to reservation id | booking success | no | context/status update | yes |
| `appointment_history[].doctor_id`, `.doctor_name`, `.specialty`, `.date`, `.time`, `.status`, `.booked_at` | denormalized history snapshot | booking success | status only on cancel/reschedule | context and UI | yes, derivative |
| `preferred_specialties[]` | specialties inferred from successful bookings | `record_booking()` via `$addToSet` | booking success | context, profile UI | yes, derivative preference signal |
| `preferred_doctors[]` | doctors inferred from successful bookings | `record_booking()` | booking success; old same doctor pulled/re-pushed | context, profile UI | yes, derivative preference signal |
| `preferred_doctors[].id`, `.name`, `.specialty`, `.last_seen` | denormalized doctor affinity | booking success | booking success for same doctor | context/UI | yes |
| `preferred_times[]` | exact appointment times inferred from successful bookings | `record_booking()` and `record_reschedule()` | booking/reschedule success | context only | yes, but not displayed by profile schema |
| `recurring_symptoms[]` | symptom keyword signal | `record_preconsultation()` | preconsultation completion | context/profile UI | yes |
| `stats.total_booked`, `.total_cancelled`, `.total_rescheduled`, `.total_preconsultations` | behavioral counters | `PatientProfileRepository.increment_stat()` | lifecycle events | not found in UI/decision code | partly dead/analytics-only |
| `reminder_preferences.advance_hours`, `.channel` | default reminder settings | `update_reminder_preference()` | reminder preference flow | booking success schedules reminder | yes if reminder preference flow is used |
| `created_at`, `updated_at` | app metadata | app upserts | most app writes | index/debug | yes metadata |
| `createdAt`, `updatedAt` | seed metadata with camelCase | seed scripts | seed replacement | not used by app code | schema drift/legacy |

### `clinix_agent.user_memories`

Owner: `agent_service` long-term memory.

Code references:
- Repository: `agent_service/app/repositories/memory_repo.py:38`, `:136`, `:174`, `:342`.
- Extractor writes memories and embeddings: `agent_service/app/services/memory_extraction_service.py:86`, `:100`, `:128`.
- Patient and doctor StateWriter fire extraction: `agent_service/graphs/patient/nodes/state_writer_node.py:79`; `agent_service/graphs/doctor/nodes/state_writer_node.py:2`.
- Semantic retrieval reads embeddings: `agent_service/app/memory/memory_manager.py:195`, `:205`.

Fields:

| Field | Meaning | Written by | Updated when | Read by | Used? |
|---|---|---|---|---|---|
| `user_id` | patient_id or doctor_id | memory upsert | insert only | all memory reads | yes |
| `key` | unique fact key per user | extractor | insert only; unique with user_id | context builder/recommender | yes |
| `value` | structured fact value | extractor | every re-observation | context/recommender/semantic text | yes |
| `memory_type` | `profile` or `episodic`; comments say workflow not stored here | extractor | every re-observation | filtered reads | yes |
| `role` | patient/doctor | extractor | every re-observation | display/debug | yes |
| `confidence` | rule confidence score | extractor | every re-observation | ranking/filtering | yes |
| `source` | `chat`, `booking`, `geo_search` | extractor | every re-observation | display/debug | weakly used |
| `frequency` | observation count | `$inc` in upsert | every upsert | ranking/recommendation | yes |
| `created_at`, `updated_at` | lifecycle timestamps | repository | update on upsert | ranking | yes |
| `embedding` | float vector stored in Mongo document | async embedding phase | after memory upsert | semantic retrieval | yes |
| `embedding_updated_at` | vector timestamp | embedding update | embedding update | excluded from normal reads | metadata |

Known keys written:
- `language`
- `specialty_interest:{specialty}`
- `preferred_time`
- `preferred_time_of_day`
- `preferred_location`
- `preferred_place_type:{place_type}`
- `doctor_affinity:{doctor_id}`
- `last_booked_doctor`
- doctor role: `frequent_intent:{intent}`

### `clinix_agent.workflow_snapshots`

Owner: `agent_service` medium-term workflow resume.

Code references:
- Upsert and completion: `agent_service/app/repositories/memory_repo.py:249`, `:287`.
- Snapshot policy: `agent_service/app/memory/memory_manager.py:241`.
- Patient writer saves/completes snapshots: `agent_service/graphs/patient/nodes/state_writer_node.py:92`, `:100`.
- Patient memory node loads pending workflow: `agent_service/graphs/patient/nodes/memory_node.py:48`, `:55`, `:125`.

Fields:

| Field | Meaning | Written by | Updated when | Read by | Used? |
|---|---|---|---|---|---|
| `user_id` | patient id | snapshot upsert | insert only | pending workflow read | yes |
| `role` | usually `patient` | snapshot upsert | each snapshot | not heavily used | metadata |
| `workflow_type` | `state.memory.intent` | snapshot upsert | each snapshot | resume hint/intent guard | yes |
| `state` | full Redis session memory at snapshot time | snapshot upsert | snapshotable steps only | resume logic | yes |
| `step` | current workflow step | snapshot upsert | snapshotable steps only | resume hint | yes |
| `context` | small subset: specialty, doctor, date, time, new date/time, place_type, intent | snapshot upsert | snapshotable steps only | resume hint | yes |
| `status` | `pending`/`completed` | snapshot save/complete | terminal step | pending query | yes |
| `created_at`, `updated_at`, `completed_at` | timestamps | repository | save/complete | TTL/debug | yes |
| `expires_at` | TTL delete time, 24h | save | save | Mongo TTL index | yes |

### `clinix_agent.memory_summaries`

Owner: intended `agent_service`, but no active caller found.

Code references:
- Read/write methods: `agent_service/app/repositories/memory_repo.py:308`, `:317`.
- Index: `agent_service/app/repositories/memory_repo.py:365`.

Fields: `user_id`, `role`, `summary_text`, `memory_count`, `created_at`.

Status: dead/unused in current runtime. The repository can write/read it, but no code path calls `save_summary()` or `get_latest_summary()`.

### Redis `{session_id}:memory`

Owner: `agent_service` short-term workflow state.

Code references:
- Redis key and TTL: `agent_service/app/memory/redis_memory.py:29`, `:51`, `:78`.
- Patient load/write: `agent_service/graphs/patient/nodes/memory_node.py:48`, `agent_service/graphs/patient/nodes/state_writer_node.py:54`.
- Doctor load/write: `agent_service/graphs/doctor/nodes/memory_node.py:6`, `agent_service/graphs/doctor/nodes/state_writer_node.py:1`.

Key format:
- Patient routes namespace sessions by role; Redis stores `f"{session_id}:memory"`.
- TTL is 1800 seconds.

Common fields:
- Identity/session: `patient_id`, `doctor_id`, `language`
- Workflow control: `intent`, `step`, `workflow_started_at`
- Booking: `specialty`, `query`, `doctor_name`, `doctor_id`, `doctor_results`, `selected_doctor_index`, `date`, `time`, `suggested_slots`, `recovery_context`, `selected_appointment_index`
- Reschedule/cancel/reminder: `appointments`, `appointment_period`, `appointment_id`, `new_date`, `new_time`, `reminder_hours`
- Preconsultation: `preconsultation_done`, `symptom_chief_complaint`, `symptom_duration`, `symptom_severity`, `symptom_associated`, `recommended_specialty`, `preconsultation_summary`
- Geo: `place_type`, `location`, `governorate`, `geo_results`
- Caches: `normalized_date`, `normalized_time`, `availability_cache`

Purpose: active mutable state for the current conversation and workflow. It is not authoritative long-term storage.

### `clinix_agent.preconsultation_data`

Owner: `agent_service`.

Code references:
- Collection and upsert: `agent_service/app/repositories/preconsultation_repo.py:28`, `:39`.
- Read by session/latest: `agent_service/app/repositories/preconsultation_repo.py:70`, `:90`.
- Summary generation writes payload: `agent_service/graphs/patient/services/preconsultation_service.py:1`.
- Report generation snapshots it: `agent_service/app/services/report_generation_service.py:107`, `:117`.

Fields:

| Field | Meaning | Written by | Updated when | Read by | Used? |
|---|---|---|---|---|---|
| `patient_id` | patient identity | repository insert | insert only | reports/latest lookup | yes |
| `session_id` | Redis/session source | repository insert | insert only | report exact-session lookup | yes |
| `appointment_id` | intended appointment link | `link_appointment()` exists | no active caller found | report lookup by appointment not using this | mostly unused |
| `chief_complaint`, `duration`, `severity`, `associated_symptoms`, `urgency`, `summary_text` | previsit questionnaire result | summary service | upsert same session | report generation/doctor view | yes |
| `created_at`, `updated_at` | timestamps | repository | every upsert | latest sort/debug | yes |

### `clinix_agent.preconsultation_reports`

Owner: `agent_service`. Immutable by design.

Code references:
- Repository: `agent_service/app/repositories/preconsultation_report_repo.py:26`, `:31`, `:47`, `:62`.
- Generated after booking: `agent_service/graphs/patient/handlers/booking_handler.py:741`.
- Snapshot construction: `agent_service/app/services/report_generation_service.py:107`, `:116`, `:117`.
- Doctor chat report lookup: `agent_service/graphs/doctor/handlers/report_handler.py:65`, `:116`.

Fields:

| Field | Meaning | Written by | Updated when | Read by | Used? |
|---|---|---|---|---|---|
| `appointment_id` | FK to `reservations` id | report generation | never | report API/doctor chat | yes, unique |
| `doctor_id` | doctor identity | report generation | never | report authorization/display | yes |
| `patient_id` | patient identity | report generation | never | report listing | yes |
| `patient_snapshot` | frozen profile fields at booking | report generation | never | doctor report panel/chat | yes |
| `preconsultation_snapshot` | frozen preconsult data | report generation | never | doctor report panel/chat | yes |
| `ai_summary` | frozen summary text | report generation | never | doctor report panel/chat | yes |
| `created_at`, `generated_by` | metadata | report generation | never | display/debug | yes |

### `clinix_agent.reminder_jobs`

Owner: `agent_service`; worker is planned but not present.

Code references:
- Create/cancel in repository: `agent_service/app/repositories/patient_profile_repo.py:305`, `:321`.
- Scheduled after booking: `agent_service/graphs/patient/handlers/booking_handler.py:722`.

Fields: `appointment_id`, `patient_id`, `doctor_name`, `appointment_date`, `appointment_time`, `remind_at`, `advance_hours`, `channel`, `status`, `created_at`, `cancelled_at`.

Status: write/cancel exists. No worker that marks jobs `sent` was found, so delivery is dead/incomplete.

### `clinix_agent.chat_history`

Owner: `agent_service`; frontend calls the API.

Code references:
- Collection and indexes: `agent_service/app/repositories/chat_history_repo.py:21`, `:32`.
- Write/read/delete: `agent_service/app/repositories/chat_history_repo.py:46`, `:113`, `:139`, `:165`.

Fields:
- `user_id`, `user_role`, `session_id`: unique conversation key.
- `messages[]`: full message list, with frontend `role`/`content` shape.
- `language`: frontend-supplied chat language.
- `title`: first user message truncated.
- `created_at`, `updated_at`.

Used by sidebars/history pages; not used as agent memory.

### `appointment_reservation.reservations`

Owner: `appointment_service`; source of truth for appointments.

Code references:
- Collection and CRUD: `appointment_service/app/repositories/appointment_repository.py:15`, `:24`, `:55`, `:67`, `:85`, `:106`.
- Appointment creation books availability slot first: `appointment_service/app/services/appointment_service.py:33`, `:240`.
- Enrichment reads `patient_profiles`, `users`, and `medical_data_tunisia.doctors`: `appointment_service/app/services/appointment_service.py:288`, `:300`, `:317`, `:336`.

Fields:

| Field | Meaning | Written by | Updated when | Read by | Used? |
|---|---|---|---|---|---|
| `doctorId` | doctor ObjectId string | appointment create/seed | never | doctor queries, availability conflict check | yes |
| `patientId` | patient profile id | appointment create/seed | never | patient queries, doctor patient access | yes |
| `date` | UTC datetime day | appointment create/seed | reschedule | date range queries | yes |
| `time` | HH:MM start | appointment create/seed | reschedule | conflict queries/display | yes |
| `status` | `pending`, `confirmed`, `cancelled`, `rejected` | create/seed | confirm/reject/cancel | filtering/display | yes |
| `createdAt`, `updatedAt` | timestamps | repository | every update | response | yes |
| `doctorName`, `patientName`, `specialty`, `endTime`, `source`, `notes` | denormalized display/metadata | optional create/seed | not generally updated | UI response | yes but optional |

### `disponibility.disponibilites`

Owner: `availability_service`; source of truth for recurring doctor availability templates.

Code references:
- Repository: `availability_service/app/repositories/availability_repository.py:10`, `:21`, `:40`, `:66`.
- Free-slot logic: `availability_service/app/services/availability_service.py:225`, `:284`, `:345`, `:364`.

Fields:
- `_id`: Mongo id.
- `doctorId`: doctor ObjectId string.
- `day`: French weekday.
- `slots[]`: legacy explicit slots with `start`, `end`, `status`.
- `ranges[]`: newer dynamic schedule ranges; used preferentially when present.
- `consultationDurationMinutes`: duration used for generated slots.
- `createdAt`, `updatedAt`.

Important behavior: `get_free_slots()` no longer treats legacy `status="booked"` as globally blocking; it filters real booked times from `reservations`.

### `disponibility.availability_exceptions`

Owner: `availability_service`.

Code references:
- Repository: `availability_service/app/repositories/exception_repository.py:10`, `:29`, `:37`.
- Applied before template lookup: `availability_service/app/services/availability_service.py:256`.

Fields:
- `doctorId`, `date`, `endDate`, `type` (`closure`, `vacation`, `override`), `reason`, `overrideRanges[]`, `createdAt`, `updatedAt`.

Purpose: closures/vacations remove availability; overrides replace normal ranges for specific dates.

### `medical_data_tunisia.*` geo collections

Owner: `geo_service`; doctor records also act as the master doctor directory.

Collections used:
- `doctors`
- `pharmacies`
- `on_call_pharmacies`
- `night_pharmacies`
- `parapharmacies`
- `clinics`
- `hospitals`
- `analysis_labs`
- `nurses`
- `physiotherapists`

Code references:
- Upsert by `place_id`: `geo_service/services/mongodb_service.py:27`.
- Proximity/manual search reads category collections: `geo_service/api_proximity.py:106`, `:301`.
- Doctor lookup/specialties read `doctors`: `geo_service/api_proximity.py:479`, `:505`.

Common fields:
- `_id`, `place_id`, `name`, `address`, `coordinates.lat/lng`, `phone_number`, `website`, `rating`, `user_ratings_total`, `opening_hours`, `is_open_now`, `specialty` for doctors, `governorate`, `types`, `image_url`, `google_maps_url`, `business_status`, `collection_type`, `last_updated`.

### Evaluation collections

Owner: `evaluation_service`.

Code references:
- Main and split metric collections: `evaluation_service/app/services/result_store.py:22`, `:24`.
- Save to Mongo or JSON fallback: `evaluation_service/app/services/result_store.py:209`, `:214`, `:217`.
- Read/list/trend/delete: `evaluation_service/app/services/result_store.py:234`, `:245`, `:288`, `:325`.

Collections:
- `evaluation_results`
- `workflow_metrics`
- `intent_metrics`
- `memory_metrics`
- `llm_judge_metrics`
- `multilingual_metrics`
- `performance_metrics`

Fields:
- `evaluation_results`: full `EvalResult` model fields, including scenario, scores, metrics, language, role, model, latency, timestamps.
- Split metric collections: `result_id`, `scenario_id`, `evaluated_at`, `metrics`.
- JSON fallback file mirrors full result docs at `evaluation_service/evaluation_results.json`.

## 2. Data Lineage

### Patient identity

```text
Signup/seed
  -> users.email/name/role/patient_profile_id
  -> patient_profiles.patient_id/name/email
Login
  -> may repair users.patient_profile_id by matching patient_profiles.email
Agent/profile/appointment services
  -> read patient_id as canonical identity
```

Source of truth: `patient_profiles.patient_id` for patient profile identity; `users.email` for authentication.

### Preferences

```text
Conversation language detected in Redis memory
  -> user_memories key=language via MemoryExtractionService
  -> patient_profiles.language only after successful booking when different
  -> next patient turn seeds Redis from patient_profiles.language if Redis has no language
```

```text
Successful booking
  -> reservations inserted
  -> patient_profiles.appointment_history appended
  -> patient_profiles.preferred_doctors/specialties/times updated
  -> user_memories may also store doctor_affinity, preferred_time, last_booked_doctor
```

Source of truth:
- Operational language seed: `patient_profiles.language`.
- Semantic personalization: `user_memories.language` plus `patient_profiles.language`.
- Booking-derived preferences: `patient_profiles.*` for profile/UI, `user_memories.*` for semantic/ranking.

### Appointments

```text
Patient booking handler
  -> appointment_service POST /appointments
  -> availability_service marks template slot booked/released where applicable
  -> appointment_reservation.reservations inserted
  -> patient_profiles derivative history/preferences updated
  -> preconsultation_reports generated
```

Source of truth: `appointment_reservation.reservations`. `patient_profiles.appointment_history` is derivative and can drift.

### Availability

```text
Doctor/API create/update
  -> disponibility.disponibilites template
Exception API
  -> disponibility.availability_exceptions
Free slot query
  -> template + exception + reservations active statuses
```

Source of truth: templates/exceptions for schedule; reservations for booked occupancy.

### Reports

```text
Preconsultation completion
  -> preconsultation_data upserted
Booking success
  -> preconsultation_reports inserted with frozen snapshots
Doctor query/API
  -> reads preconsultation_reports
```

Source of truth: `preconsultation_reports` for the report shown to doctors; source inputs remain `patient_profiles` and `preconsultation_data`.

## 3. Memory Architecture

```text
Turn start:
  Redis {session_id}:memory
  + patient_profiles
  + user_memories ranked
  + workflow_snapshots pending
  + semantic user_memories query
    -> AgentState.memory/profile/long_term_memories/memory_context

Turn end:
  AgentState.memory -> Redis
  AgentState.memory -> user_memories extraction
  AgentState.memory -> workflow_snapshots if step is snapshotable
```

Redis session memory:
- Mutable workflow state, 30-minute TTL.
- Drives response language, workflow step, selected doctor/date/time.

Long-term memory:
- `user_memories`, permanent per user and key.
- Rule-extracted from completed turns.

Semantic memory:
- `embedding` arrays stored in `user_memories`.
- Query embedding is generated each turn, candidates are loaded by user id, ranked in Python.
- No separate vector database exists.

RAG memory:
- `MemoryContextBuilder` produces a compact text context for the LLM.
- Priority: semantic memories, patient profile safety/behavioral fields, remaining structured memories.

Caches:
- Process LRU embedding cache in `agent_service/app/embeddings/cache.py`, max 2000 entries; refs `:19`, `:22`, `:73`.
- SentenceTransformer model singleton via `@lru_cache(maxsize=1)`; ref `agent_service/app/embeddings/sentence_transformer_provider.py:25`.
- Redis is not a cache here; it is the active session state store.
- `availability_cache`, `normalized_date`, `normalized_time` are transient Redis workflow fields cleaned by workflow cleaners.

## 4. Patient Booking Data Flow

```text
1. Patient sends message
2. Patient MemoryNode loads Redis + profile + user_memories + workflow snapshot + semantic memory
3. IntentNode extracts intent/entities/language into state.memory
4. BookingHandler searches doctors in geo_service medical_data_tunisia.doctors
5. Availability checked through availability_service:
   disponibilites + availability_exceptions + reservations
6. Preconsultation flow may write preconsultation_data
7. BookingHandler._ready_to_book posts appointment
8. appointment_service:
   book slot -> insert reservations
9. BookingHandler fire-and-forget:
   patient_profiles history/preferences/stats
   reminder_jobs
   patient_profiles.language if changed
   preconsultation_reports
10. StateWriter persists Redis, user_memories, workflow_snapshots completion
```

Documents created/updated:
- Redis `{session_id}:memory`: many workflow fields.
- `workflow_snapshots`: pending while step is snapshotable, completed after terminal.
- `preconsultation_data`: if questionnaire completed.
- `reservations`: one appointment document.
- `patient_profiles`: history/preferences/language/stats.
- `reminder_jobs`: one pending reminder if appointment id exists.
- `preconsultation_reports`: one immutable report per appointment.
- `user_memories`: extracted language/specialty/time/doctor/episodic facts.
- `chat_history`: only if frontend history save endpoint is called.

## 5. Doctor Query Data Flow

```text
Doctor message
  -> Doctor MemoryNode loads Redis + doctor user_memories + semantic memories
  -> Doctor intent detector selects tool/action
  -> Action handler:
       appointments -> appointment_service reservations
       availability -> availability_service disponibilites/exceptions
       report -> preconsultation_reports, sometimes patient_profiles/users for name resolution
  -> response generator formats result
  -> Doctor StateWriter saves Redis + doctor user_memories
```

Read/update examples:
- View schedule reads `reservations`, enriched from `clinix_agent.users`, `patient_profiles`, and `medical_data_tunisia.doctors`.
- Confirm/reject/cancel/reschedule updates `reservations`; cancel/reject releases availability slot.
- Report lookup reads `preconsultation_reports`; patient-name lookup reads `patient_profiles` then `users`.
- Doctor availability edits update `disponibilites` or `availability_exceptions`.

## 6. Dead Data and Risk Analysis

Unused/dead:
- `memory_summaries`: repository methods exist, no active caller found.
- `preconsultation_data.appointment_id`: `link_appointment()` exists, but no active runtime caller was found.
- `reminder_jobs`: jobs are created/cancelled, but no worker that sends reminders or marks `sent` was found.
- `patient_profiles.stats.*`: written but not used in frontend/agent decisions found.
- `patient_profiles.preferences`: manual blob exposed by profile API, not used by agent workflow.

Duplicated:
- `language`: Redis current session, `patient_profiles.language`, `user_memories.key=language`, chat_history language, frontend voice session language.
- `preferred_specialties`: `patient_profiles.preferred_specialties` and `user_memories.specialty_interest:*`.
- `preferred_doctors`: `patient_profiles.preferred_doctors` and `user_memories.doctor_affinity:*` / `last_booked_doctor`.
- `preferred_times`: `patient_profiles.preferred_times`, `user_memories.preferred_time`, `user_memories.preferred_time_of_day`.
- Appointment facts: `reservations` vs `patient_profiles.appointment_history` vs `preconsultation_reports` snapshots.

Legacy/schema drift:
- `patient_profiles.createdAt/updatedAt` from seed scripts vs `created_at/updated_at` from app code.
- Seed appointments use `patientId = str(patient["_id"])` in `scripts/seed_appointments.py`, while app booking uses `patient_id`; this can create appointments that do not resolve cleanly to `patient_profiles.patient_id`.
- Availability supports both legacy `slots[]` and newer `ranges[]`.
- `disponibilites` spelling is real collection name; do not rename casually.

## 7. Source of Truth Analysis

| Business concept | Authoritative source | Secondary/derived stores | Notes |
|---|---|---|---|
| Patient auth identity | `users` | JWT/frontend `clinix-auth` | email/password/role live here |
| Patient profile/medical data | `patient_profiles` | report snapshots | profile edits write here |
| Patient id | `patient_profiles.patient_id` | `users.patient_profile_id`, JWT | code repairs slug/UUID mismatches |
| Doctor directory | `medical_data_tunisia.doctors` | `users.doctor_id` | doctor id is doctor `_id` string |
| Preferences | split: `patient_profiles` for profile/UI and deterministic booking-derived signals; `user_memories` for semantic personalization | Redis current turn | no single unified preference source |
| Current language | Redis during active session; `patient_profiles.language` for next-session seed | `user_memories.language`, frontend voice state | source of truth depends on time horizon |
| Appointments | `appointment_reservation.reservations` | `patient_profiles.appointment_history`, reports | never treat profile history as authoritative schedule |
| Availability templates | `disponibility.disponibilites` | none | recurring schedule |
| Availability exceptions | `disponibility.availability_exceptions` | none | overrides closures/vacations |
| Booked occupancy | `reservations` active statuses | legacy slot status | free slot code cross-checks reservations |
| Preconsultation latest data | `preconsultation_data` | Redis preconsult fields | per-session upsert |
| Doctor-facing report | `preconsultation_reports` | source snapshots | immutable |
| Session workflow | Redis `{session_id}:memory` | `workflow_snapshots` | Redis current, snapshots resume |
| Long-term memory | `user_memories` | embeddings in same docs | semantic and structured memory |
| Chat history | `chat_history` | frontend in-memory stores | not used as memory |
| Evaluation results | `evaluation_results` | metric split collections, JSON fallback | evaluation-only |

## Preference Duplication Answer

`patient_profiles.language`, `preferred_specialties`, `preferred_doctors`, and `preferred_times` exist because the code treats `patient_profiles` as a durable patient intelligence/profile document, not only as a manual medical profile. They are mostly inferred from successful lifecycle events:

- `language`: inferred from session memory and persisted after successful booking if it differs from profile.
- `preferred_specialties`: inferred from successful bookings.
- `preferred_doctors`: inferred from successful bookings.
- `preferred_times`: inferred from successful bookings and reschedules.

They are not manually entered by the current profile UI. They are not synchronized from `user_memories`; both stores are written independently from the same or related session signals.

The same concepts also exist in `user_memories`:

- `language`
- `specialty_interest:{specialty}`
- `doctor_affinity:{doctor_id}`
- `last_booked_doctor`
- `preferred_time`
- `preferred_time_of_day`

The practical source-of-truth rules are:

1. For active workflow decisions, Redis wins.
2. For patient profile and UI, `patient_profiles` wins.
3. For semantic personalization and doctor recommendation boosting, `user_memories` wins.
4. For real appointments, `reservations` wins over all profile/memory copies.
5. There is no current synchronizer that guarantees `patient_profiles` preferences and `user_memories` preferences agree.

