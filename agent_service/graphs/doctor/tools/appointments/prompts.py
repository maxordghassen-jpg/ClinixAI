APPOINTMENTS_PROMPT = """

Tool: appointments
Role: understand doctor appointment requests in French, English, Arabic,
and noisy spelling.

Choose only one action:

* view_appointments           — list appointments (unspecified short period, defaults to today)
* view_today_appointments     — today's schedule
* view_tomorrow_appointments  — tomorrow's schedule
* view_week_appointments      — this week OR "all appointments" / "all my appointments" / "tous mes rendez-vous" / "كل مواعيدي"
* view_next_week_appointments — next week
* view_appointments_by_exact_date — specific date (put date in entities.date as YYYY-MM-DD)
* daily_schedule              — compact daily schedule view (today unless date given)
* weekly_schedule             — compact weekly schedule view
* confirm_appointment         — confirm a pending appointment (put id in entities.reservation_id)
* reject_appointment          — reject a pending appointment (put id in entities.reservation_id)
* cancel_appointment          — cancel an existing appointment (put id in entities.reservation_id)
* reschedule_appointment      — move appointment to new date/time (entities: reservation_id, date, time)

Status filters (populate status field when filter is requested):

* pending
* confirmed
* active

Entities to extract:

* reservation_id — appointment ID when confirming/rejecting/cancelling/rescheduling
* date           — date string in YYYY-MM-DD format
* time           — time string in HH:MM format

Important:

* "rdv", "rendez", "rendez-vous", "appointment", "موعد" all mean appointment.
* "show schedule", "planning", "mon agenda" → daily_schedule or weekly_schedule.
* "all appointments", "all my appointments", "show all" → view_week_appointments (NOT view_all_appointments).
* "cancel" = cancel_appointment; "reschedule", "reporter", "déplacer" = reschedule_appointment.
  """
