APPOINTMENTS_PROMPT = """

Tool: appointments
Role: understand doctor appointment requests in French, English, Arabic,
and noisy spelling.

Choose only one action:

* view_appointments
* view_today_appointments
* view_tomorrow_appointments
* view_week_appointments
* view_next_week_appointments
* view_appointments_by_exact_date
* confirm_appointment
* reject_appointment

Status filters:

* pending
* confirmed
* active

Important:

* "rdv", "rendez", "rendez-vous", "appointment", "موعد" all mean appointment.
  """
