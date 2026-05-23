# Phase 2 Test Checklist — Persistence & Orchestration

All scenarios below test that state.memory survives correctly across turns via
Redis, that no workflow context is silently lost, and that the
MemoryNode → IntentNode → WorkflowNode → ActionNode → StateWriterNode
pipeline behaves deterministically.

---

## HOW TO READ EACH TEST

Each test lists:
- **Setup**: the Redis state before the turn
- **User says**: the message
- **Expected Redis after**: fields that MUST be in Redis after StateWriterNode runs
- **Expected response**: what the bot should say
- **Pass condition**: what to grep in the trace logs

---

## 1. Full Booking Workflow Continuity

### T1-1: Fresh booking request
- **Setup**: Redis empty
- **User says**: "I need a cardiologist"
- **Expected Redis after**: `intent=doctor_search`, `specialty=cardiologue`, `step=selecting_doctor`, `doctor_results=[...]`, `workflow_started_at` set
- **Expected response**: "I found these doctors: 1. ... 2. ..."
- **Pass**: `[WRITER]` logs `step='selecting_doctor'` and `intent='doctor_search'`

### T1-2: Doctor selection
- **Setup**: Redis has `step=selecting_doctor`, `doctor_results=[{id:X, name:DrX}]`, `intent=doctor_search`
- **User says**: "1"
- **Expected Redis after**: `step=awaiting_date`, `doctor_id=X`, `doctor_name=DrX`, `intent=booking`
- **Expected response**: "Great choice. What date would you like?"
- **Pass**: `[WORKFLOW]` logs `step: 'selecting_doctor' → 'doctor_selected'`; `[WRITER]` logs `step='awaiting_date'`
- **Fail**: if `[WORKFLOW]` logs "active step guard" for `selecting_doctor` — REGRESSION

### T1-3: Date input
- **Setup**: Redis has `step=awaiting_date`, `doctor_id=X`, `intent=booking`
- **User says**: "tomorrow"
- **Expected Redis after**: `step=awaiting_time`, `date=tomorrow`
- **Expected response**: "What time would you prefer?"
- **Pass**: `[WRITER]` logs `step='awaiting_time'` and `date='tomorrow'`
- **Fail**: if `date` is missing from Redis after this turn — Phase 2 regression

### T1-4: Time input
- **Setup**: Redis has `step=awaiting_time`, `date=tomorrow`, `doctor_id=X`, `intent=booking`
- **User says**: "3 pm"
- **Expected Redis after**: `step=completed` (or `awaiting_time` if slot unavailable)
- **Expected response**: "Your appointment has been booked successfully." OR slot list
- **Pass**: `[ACTION]` logs "booking attempt" and "booking SUCCESS"

### T1-5: Full one-shot booking (all details in one message)
- **Setup**: Redis empty
- **User says**: "Book with Dr X on Friday at 3 pm"
- **Expected**: workflow routes through correct steps to `ready_to_book`
- **Pass**: `[WORKFLOW]` + `[ACTION]` trace shows step progression

---

## 2. Interrupted Workflow Recovery

### T2-1: Session survives page reload (Redis persisted)
- **Setup**: User was at `step=awaiting_date`, disconnects, reconnects with same session_id
- **User says**: "tomorrow"
- **Expected**: continues from `awaiting_date` as if nothing happened
- **Pass**: `[MEMORY]` loads `step=awaiting_date` at start; `[WRITER]` saves `step=awaiting_time`

### T2-2: Intent preserved across weak reply
- **Setup**: Redis has `intent=booking`, `step=awaiting_date`, `doctor_id=X`
- **User says**: "ok" (ambiguous)
- **Expected Redis after**: `intent=booking` UNCHANGED, `step=awaiting_date` UNCHANGED
- **Expected response**: "What date would you like?" (asking again)
- **Pass**: `[INTENT]` logs "active-workflow guard: kept existing intent='booking'"
- **Fail**: if intent changes to "none" — guard regression

### T2-3: Time provided but booking service down
- **Setup**: Redis has `step=awaiting_time`, `date=tomorrow`, `doctor_id=X`
- **User says**: "4 pm" (booking service returns error)
- **Expected Redis after**: `step=awaiting_time`, `time` key DELETED from Redis
- **Expected response**: "This time slot is unavailable..." + slot list
- **Pass**: `[ACTION]` logs "booking FAILED" then "stale time deleted from Redis"
- **Fail**: if `time=16:00` remains in Redis after failure

### T2-4: Redis key missing mid-workflow (rare: Redis restart)
- **Setup**: Redis empty but user sends follow-up message without session context
- **User says**: "friday" (no prior context)
- **Expected**: MemoryNode loads empty state; IntentNode sees no context; WorkflowNode routes to idle or awaiting_specialty
- **Pass**: no crash, graceful "How can I help you today?" or equivalent
- **Fail**: KeyError / AttributeError anywhere in the pipeline

---

## 3. Multilingual Booking

### T3-1: French full booking
- **Setup**: Redis empty
- **User says**: "Je veux prendre un rendez-vous avec un cardiologue vendredi à 15h"
- **Expected**: `language=french`, `specialty=cardiologue`, `date` and `time` extracted
- **Pass**: `[INTENT]` shows correct French extraction

### T3-2: Arabic doctor search
- **Setup**: Redis empty
- **User says**: "أحتاج إلى طبيب قلب"
- **Expected**: `language=arabic`, `specialty=cardiologue`, `intent=doctor_search`
- **Pass**: `[INTENT]` shows Arabic extraction; specialty normalized to `cardiologue`

### T3-3: Arabic date mid-workflow
- **Setup**: Redis has `step=awaiting_date`, `intent=booking`, `doctor_id=X`
- **User says**: "الجمعة" (Friday in Arabic)
- **Expected**: `date=الجمعة` (or normalized), `step→awaiting_time`
- **Pass**: workflow continues without resetting
- **Note**: Full normalization of Arabic dates to ISO is Phase 3 (DateNormalizer)

### T3-4: Language consistency across turns
- **Setup**: Turn 1 in French sets `language=french`; Turn 2 user writes in Arabic
- **Expected**: `language` updated to `arabic` by IntentNode on Turn 2
- **Pass**: `[WRITER]` logs `language=arabic` in final write

---

## 4. Booking Retries (Unavailable Slots)

### T4-1: First slot unavailable, retry with new time
- **Turn 1 setup**: `step=awaiting_time`, `date=tomorrow`, `doctor_id=X`
- **Turn 1 user**: "3 pm" → booking fails → response offers alternatives
- **Expected Redis after Turn 1**: `time` DELETED, `step=awaiting_time`
- **Turn 2 user**: "4 pm"
- **Expected**: booking retried with new time
- **Pass**: `[WRITER]` for Turn 1 shows NO `time` field in persisted keys

### T4-2: All slots on a date unavailable
- **Setup**: `step=awaiting_time`, `date=tomorrow`, `doctor_id=X`
- **User says**: "3 pm" (booking fails, no free slots)
- **Expected response**: "No available slots were found for that date."
- **Expected Redis after**: `step=awaiting_time`, no `time`
- **Pass**: `[ACTION]` logs "no free slots available"

---

## 5. Workflow Expiry

### T5-1: Expired workflow clears and restarts correctly
- **Setup**: Redis has `workflow_started_at` set 2 hours ago (> 1800s), `step=awaiting_date`, `intent=booking`
- **User says**: "I need a dentist"
- **Expected**: MemoryNode detects expiry → `clear_workflow` runs → fresh state; new workflow starts
- **Pass**: `[MEMORY]` logs "WORKFLOW EXPIRED"; `[CLEANUP]` logs keys cleared; `[WORKFLOW]` logs timer re-initialised
- **Fail**: expired state leaks into new workflow

### T5-2: Timer initialised only once per workflow
- **Setup**: Fresh workflow (Turn 1 sets `workflow_started_at=T1`)
- **User says**: multiple messages continuing the workflow
- **Expected**: `workflow_started_at` stays at T1, never incremented
- **Pass**: `[WORKFLOW]` logs "active step guard" on subsequent turns (timer block not reached)

### T5-3: Timer correctly cleared after cleanup
- **Setup**: `workflow_started_at` present in Redis, workflow expires
- After cleanup: `workflow_started_at` DELETED from Redis
- New message starts: `workflow_started_at` re-initialised to NOW
- **Pass**: `[CLEANUP]` logs `workflow_started_at` in cleared keys

---

## 6. Partial Extraction Failures

### T6-1: LLM returns malformed JSON
- **Setup**: Redis has `step=awaiting_date`, `intent=booking`, `doctor_id=X`
- **Simulate**: LLM returns `"I cannot process that"` (non-JSON)
- **Expected**: IntentNode catches exception, preserves memory unchanged
- **Expected Redis after**: `step=awaiting_date`, `intent=booking` — NO CHANGE
- **Pass**: `[INTENT]` logs "PARSE ERROR — memory preserved"
- **Fail**: `intent=none` appears in Redis

### T6-2: LLM returns intent="none" mid-workflow
- **Setup**: Redis has `intent=booking`, `step=awaiting_time`
- **User says**: "yes sure" (vague)
- **LLM returns**: `{intent: "none"}`
- **Expected**: active-workflow guard preserves `intent=booking`
- **Pass**: `[INTENT]` logs "active-workflow guard: kept existing intent='booking'"

### T6-3: LLM API timeout / network error
- **Setup**: Active booking workflow, network goes down briefly
- **Expected**: IntentNode exception caught; workflow continues from existing step
- **Pass**: No unhandled exception; `[INTENT]` logs error; `[ACTION]` continues from step in Redis

---

## 7. Edge Cases

### T7-1: Two sequential bookings (workflow cleanup between)
- **Booking 1**: completes → `step=completed`
- **New message**: "Book another appointment with a dermatologist"
- **Expected**: NEW workflow starts fresh; `step=completed` from old booking does not interfere
- **Note**: WorkflowNode sees `step=completed` which is NOT in ACTIVE_STEPS, processes new intent ✓

### T7-2: User provides all booking details in one message
- **User says**: "Book with Dr. Smith tomorrow at 2pm"
- **Expected**: IntentNode extracts specialty/doctor (if named), date, time; WorkflowNode correctly routes; no unnecessary prompts
- **Pass**: If all fields present, `step=ready_to_book` reached without intermediate prompts

### T7-3: Doctor selection index out of range
- **Setup**: `doctor_results` has 3 doctors, `step=selecting_doctor`
- **User says**: "5"
- **Expected**: "Invalid doctor selection." response; workflow stays at `selecting_doctor`
- **Pass**: `[ACTION]` logs "invalid selection: position=4 out of range"

### T7-4: patient_id always injected regardless of Redis state
- **Setup**: Redis key exists but has no `patient_id` (e.g., after redis restart)
- **Request**: includes `patient_id=P123`
- **Expected**: `patient_id=P123` present in Redis after turn
- **Pass**: `[MEMORY]` logs "patient_id injected: P123"; `[WRITER]` logs `patient_id` in written keys

---

## 8. Graph Path Verification

### T8-1: StateWriterNode always reached
- **Verify**: for EVERY scenario above, `[WRITER]` log appears at the END of each turn
- **Method**: grep logs for `[WRITER  ] session=X | Redis write complete` — must appear once per turn
- **Fail**: any turn where `[WRITER]` does NOT appear (indicates unhandled exception in upstream node)

### T8-2: No split-brain between ActionNode checkpoint and StateWriterNode
- **Scenario**: doctor search finds 3 doctors (checkpoint written by ActionNode mid-turn)
- **Expected**: `[WRITER]` final write includes `step=selecting_doctor` and `doctor_results`
- **Verify**: ActionNode writes checkpoint FIRST, StateWriterNode writes same data again — both writes converge to same Redis state via ContextMerger

---

## REMAINING KNOWN GAPS (Phase 3)

These are NOT Phase 2 failures — they are pre-existing issues to fix in Phase 3:

| Gap | Impact |
|-----|--------|
| `DateNormalizer` only handles "today"/"tomorrow" | "friday", "vendredi", Arabic dates fail at BookingService |
| `TimeNormalizer` only handles 8 formats | "3:00 pm", "3h30" etc. fail at BookingService |
| `AvailabilityService` sends day name not ISO date to free-slots URL | Free slot lookup always fails |
| `awaiting_specialty` step has no ActionNode handler | Booking without specialty gives "How can I help you?" |
| No multilingual response templates for mid-booking prompts | Responses always in English regardless of `language` |
