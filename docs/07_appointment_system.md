# ClinixAI — Appointment & Availability System

## 1. System Overview

The appointment system is split across two services:

| Service | Port | Responsibility |
|---|---|---|
| `availability_service` | 8002 | Doctor weekly schedules, slot generation, slot status (available/booked/blocked) |
| `appointment_service` | 8003 | Appointment records (create, cancel, reschedule, list by patient/date/doctor) |

These two services are deliberately separated:
- **Availability** = the template schedule (recurring weekly pattern)
- **Appointments** = actual bookings against that template

This separation prevents a common bug where booking an appointment permanently marks the template slot as "booked" for all future weeks. Instead, the template is never mutated — bookings are recorded separately, and free slots are computed by subtracting confirmed appointments from the generated template slots.

---

## 2. Availability Service Architecture

### Data Model

**Collection**: `availabilities` in database `disponibility`

A doctor's schedule is stored as a recurring weekly template:

```json
{
    "_id": ObjectId("..."),
    "doctorId": "doc-ben-salah-123",
    "day": "lundi",
    "ranges": [
        { "start": "09:00", "end": "12:00" },
        { "start": "14:00", "end": "17:30" }
    ],
    "consultationDurationMinutes": 30,
    "slots": [
        { "start": "09:00", "end": "09:30", "status": "available" },
        ...
    ],
    "createdAt": "2026-01-01T08:00:00Z",
    "updatedAt": "2026-05-01T12:00:00Z"
}
```

Key design choices:
- Days are stored in **French** (`lundi`, `mardi`, `mercredi`, `jeudi`, `vendredi`, `samedi`, `dimanche`) — reflecting the Tunisian professional calendar context
- The `ranges` field defines work periods; `slots` are dynamically generated from ranges + consultation duration
- `consultationDurationMinutes` defaults to 30 minutes if unspecified

### `scheduling.py` — Slot Generation

```python
def generate_slots_from_ranges(ranges: list[dict], duration_minutes: int) -> list[dict]:
    """
    Given work ranges and consultation duration, generate all possible slots.
    Example: ranges=[{start:"09:00",end:"12:00"}], duration=30
    → [{"start":"09:00","end":"09:30","status":"available"},
       {"start":"09:30","end":"10:00","status":"available"}, ...]
    """
    slots = []
    for range_ in ranges:
        current = parse_time(range_["start"])
        end = parse_time(range_["end"])
        while current + timedelta(minutes=duration_minutes) <= end:
            slots.append({
                "start": format_time(current),
                "end":   format_time(current + timedelta(minutes=duration_minutes)),
                "status": "available"
            })
            current += timedelta(minutes=duration_minutes)
    return slots
```

### Exception System

**Collection**: `exceptions` in database `disponibility`

The exception system allows doctors to override their regular schedule for specific dates:

```json
{
    "doctor_id": "doc-ben-salah-123",
    "date": "2026-06-20",
    "type": "closure",         // "closure" | "vacation" | "override"
    "overrideRanges": []       // only for type="override"
}
```

Exception types:
- **`closure`**: Doctor is unavailable this specific date → return `[]` (no slots)
- **`vacation`**: Same as closure but for multi-day absences
- **`override`**: Doctor has a non-standard schedule on this date → use `overrideRanges` instead of template

The exception check is performed **before** template lookup (short-circuit optimization):
```python
exception = await self.exception_repository.find_for_date(doctor_id, date)
if exception:
    exc_type = exception.get("type")
    if exc_type in ("closure", "vacation"):
        return []
    if exc_type == "override":
        candidate_slots = generate_slots_from_ranges(exception["overrideRanges"], duration)
```

### `AvailabilityService` — Core Business Logic

**`get_free_slots(doctor_id, day, date)`**:

The key algorithm for computing available appointment slots:

1. Load template availability document for (doctor_id, day)
2. Check for date-specific exception → short-circuit if closure/vacation
3. If `ranges` present: dynamically generate all slots; filter out `status="blocked"` ones
4. If no `ranges` (legacy format): use `slots` array directly, filtering out `status ∈ {"blocked"}`
5. Fetch confirmed appointments from `appointment_service` for (doctor_id, date)
6. Remove slots whose `start` time appears in confirmed appointments (status ≠ cancelled/rejected)
7. Return remaining free slots

**The legacy bug fix**: Original code filtered `status != "booked"` from the template, which permanently removed booked slots even in future weeks. The fix: template slots are never marked "booked" — instead, appointments are subtracted at query time.

### CRUD Operations

| Method | Endpoint | Description |
|---|---|---|
| POST | `/availability` | Create recurring schedule for a (doctor, day) pair |
| PUT | `/availability/{id}` | Update slot ranges for existing schedule |
| DELETE | `/availability/{id}` | Remove a day's schedule |
| POST | `/availability/block` | Mark a specific slot as blocked (doctor unavailable) |
| POST | `/availability/unblock` | Remove block from a slot |
| POST | `/availability/book` | Mark slot as booked (called after appointment creation) |
| POST | `/availability/release` | Release a booked slot (called after cancellation) |
| GET | `/availability/free-slots` | Get available slots for a specific date |
| GET | `/availability/doctor/{id}` | Get all schedules for a doctor |

### Slot Validation

The `_validate_slots()` method enforces:
1. Slots cannot be empty
2. `start` must be before `end` for each slot
3. Slots cannot overlap (checked after sorting by start time)

Time comparison uses minutes-since-midnight:
```python
def _to_minutes(time_str: str) -> int:
    parsed = datetime.strptime(time_str, "%H:%M")
    return parsed.hour * 60 + parsed.minute
```

---

## 3. Appointment Service Architecture

The appointment service manages the actual appointment records — the concrete instances of scheduled consultations.

### Data Model

```json
{
    "_id": ObjectId("..."),
    "patient_id": "patient-john-doe",
    "doctor_id": "doc-ben-salah-123",
    "date": "2026-06-20",
    "time": "10:30",
    "status": "confirmed",       // "pending" | "confirmed" | "cancelled" | "rejected"
    "created_at": "2026-06-15T14:00:00Z",
    "updated_at": "2026-06-15T14:00:00Z",
    "notes": "First cardiac checkup"
}
```

### Key Endpoints

| Endpoint | Purpose |
|---|---|
| `POST /appointments` | Create new appointment |
| `GET /appointments/patient/{id}` | List all appointments for a patient |
| `GET /appointments/date/{doctor_id}?date=YYYY-MM-DD` | Appointments for a doctor on a date |
| `PATCH /appointments/{id}/cancel` | Cancel appointment |
| `PATCH /appointments/{id}/reschedule` | Reschedule (update date/time) |
| `GET /appointments/{id}` | Get single appointment |

The `/appointments/date/{doctor_id}` endpoint is called by the availability service during free slot computation to determine which slots are already booked.

---

## 4. Booking Flow: End-to-End

The complete booking workflow as executed by the patient agent:

**Turn 1**: "I want to see a cardiologist"
- IntentNode: `{intent: "booking", specialty: "cardiologist"}`
- WorkflowNode: `step = "searching_doctors"` (no doctor_id yet)
- ActionNode: `GET /availability/doctors?specialty=cardiologist` → list of available doctors
- Response: "I found 3 cardiologists: (1) Dr. Ben Salah — Tunis Centre, (2) Dr. Khelifi — Lac, (3) Dr. Mansour — Carthage. Which one would you prefer?"

**Turn 2**: "The first one"
- IntentNode: `{intent: "select_doctor"}`
- WorkflowNode: `step = "doctor_selected"`
- ActionNode: Resolves selection #1 → `doctor_id = "doc-ben-salah-123"`
- Response: "Dr. Ben Salah selected. What date works for you?"

**Turn 3**: "Monday June 22nd"
- IntentNode: `{intent: "booking", date: "2026-06-22"}`
- WorkflowNode: `step = "awaiting_time"`
- ActionNode: `GET /availability/free-slots?doctor_id=doc-ben-salah-123&day=lundi&date=2026-06-22`
  → [{"start":"09:00"}, {"start":"09:30"}, {"start":"10:00"}, {"start":"14:30"}]
- Response: "Available slots for June 22: 09:00, 09:30, 10:00, 14:30. Which time?"

**Turn 4**: "Ten o'clock"
- IntentNode: `{intent: "booking", time: "10:00"}`
- WorkflowNode: `step = "ready_to_book"`
- ActionNode:
  1. `POST /appointments {patient_id, doctor_id, date:"2026-06-22", time:"10:00"}`
  2. `POST /availability/book {doctor_id, day:"lundi", start:"10:00"}`
  - If step 1 returns 409 (slot taken): `step = "awaiting_slot_selection"`, present alternatives
- Response: "Confirmed! Your appointment with Dr. Ben Salah is on June 22 at 10:00 AM. You'll receive a reminder."

---

## 5. Appointment Management: Cancel and Reschedule

### Cancel Flow

1. Patient says "Cancel my appointment"
2. `step = "fetching_appointments"` → list all patient appointments
3. Patient selects one → `step = "confirming_cancel"` → confirmation prompt
4. Patient confirms → ActionNode:
   - `PATCH /appointments/{id}/cancel {status: "cancelled"}`
   - `POST /availability/release {doctor_id, day, start}` → slot becomes available again
5. StateWriterNode stores cancellation memory for rebooking detection

### Reschedule Flow

1. Patient says "Reschedule my appointment"
2. `step = "fetching_appointments"` → list appointments
3. Patient selects → `step = "confirming_reschedule"` → confirm which appointment
4. Patient confirms → `step = "awaiting_reschedule_date"` → ask for new date
5. Patient provides date → `step = "awaiting_reschedule_time"` → show free slots
6. Patient picks time → `step = "ready_to_reschedule"` → ActionNode:
   - Release old slot: `POST /availability/release {old doctor, old day, old start}`
   - Update appointment: `PATCH /appointments/{id}/reschedule {date, time}`
   - Book new slot: `POST /availability/book {doctor_id, new_day, new_start}`
7. Confirmation response

---

## 6. Doctor Dashboard Integration

The doctor's `page.tsx` frontend:
1. Loads all doctor appointments: `GET /appointments/doctor/{doctor_id}`
2. Renders appointments as FullCalendar events with color-coded status badges
3. Allows inline status updates (confirm, reject) without leaving the calendar
4. Sidebar shows patient profile when clicking an appointment event
5. Schedule manager panel lets doctor create/update availability: `POST /availability`, `PUT /availability/{id}`
