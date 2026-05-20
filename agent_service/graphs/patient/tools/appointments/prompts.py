PATIENT_APPOINTMENTS_PROMPT = """
Tool: appointments
Role: understand patient appointment requests in French, English, Arabic,
and noisy spelling.

Choose only one action:
* book_appointment
* cancel_appointment
* reschedule_appointment
* view_today_appointments
* view_tomorrow_appointments
* view_week_appointments
* view_appointments_by_exact_date

Important:
* "rdv", "rendez", "rendez-vous", "appointment", "موعد" all mean appointment.
"""
