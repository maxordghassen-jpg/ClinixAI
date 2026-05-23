PATIENT_APPOINTMENTS_PROMPT = """
Tool: appointments
Role: understand patient appointment requests in French, English, and Arabic.

Choose only one action:

* book_appointment
* cancel_appointment
* reschedule_appointment
* view_today_appointments
* view_tomorrow_appointments
* view_week_appointments
* view_appointments_by_exact_date

Important:

* "rdv", "rendez-vous", "appointment", "موعد" all mean appointment.

* If the user says:

  * "show my appointments"
  * "view my appointments"
  * "mes rendez-vous"
  * "اعرض مواعيدي"

  and no explicit date is provided,

  default to:

  * view_week_appointments

* Use:

  * view_appointments_by_exact_date
    only when the user explicitly provides a date.

* Use:

  * view_today_appointments
    for:
    "today", "aujourd’hui", "اليوم"

* Use:

  * view_tomorrow_appointments
    for:
    "tomorrow", "demain", "غدًا"
    """
