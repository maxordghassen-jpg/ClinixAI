AVAILABILITY_PROMPT = """

Tool: availability
Role: understand doctor availability, schedule, and exception management requests
in French, English, Arabic, and noisy spelling.

Choose one action:

Schedule template actions:
* view_available_slots       — free slots for a specific date
* view_today_availability    — today's free slots
* view_tomorrow_availability — tomorrow's free slots
* view_week_availability     — this week's template
* view_next_week_availability
* view_availability          — full weekly template
* create_availability        — create a recurring weekly slot template
* update_availability        — update a recurring weekly slot template
* block_availability         — permanently block a recurring slot (entities: day, time)
* unblock_availability       — unblock a recurring slot (entities: day, time)
* delete_availability        — delete a weekly template (entities: availability_id)

Exception actions (one-time overrides, do not affect recurring templates):
* block_day      — mark a specific date as unavailable (entities: date, reason)
* vacation_mode  — mark a date range as vacation (entities: start_date, end_date, reason)
* override_hours — set custom hours for a specific date (entities: date, slots: [{start, end}])
* view_exceptions   — list all exceptions for the doctor
* delete_exception  — remove an exception (entities: exception_id)

Entities to extract:

* day          — French weekday name (lundi, mardi, ...)
* date         — YYYY-MM-DD
* start_date   — YYYY-MM-DD (vacation start)
* end_date     — YYYY-MM-DD (vacation end)
* time         — HH:MM (for block/unblock single slot)
* reason       — optional reason string
* slots        — list of {"start": "HH:MM", "end": "HH:MM"} for override_hours
* exception_id — MongoDB _id of the exception to delete
* availability_id — MongoDB _id of the template to update/delete

Important:

* Availability is not an appointment.
* "I'm unavailable Friday", "block Friday" → block_day
* "vacation June 10–20", "congé du 10 au 20 juin" → vacation_mode
* "Next Monday only 10am–2pm" → override_hours
* "show my exceptions", "liste des blocages" → view_exceptions
  """
