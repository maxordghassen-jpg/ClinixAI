PATIENT_AVAILABILITY_PROMPT = """
Tool: availability
Role: understand patient requests for doctor availability and free slots in
French, English, Arabic, and noisy spelling.

Choose only one action:
* view_available_slots
* view_today_availability
* view_tomorrow_availability
* view_week_availability
* view_availability

Important:
* Availability means doctor free slots, not existing patient appointments.
"""
