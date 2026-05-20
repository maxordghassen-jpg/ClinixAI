PATIENT_APPOINTMENT_ACTIONS = {
    "book_appointment",
    "cancel_appointment",
    "reschedule_appointment",
    "view_today_appointments",
    "view_tomorrow_appointments",
    "view_week_appointments",
    "view_appointments_by_exact_date",
}


def is_patient_appointment_action(action: str) -> bool:
    return action in PATIENT_APPOINTMENT_ACTIONS
