APPOINTMENT_ACTIONS = {
    "view_appointments",
    "view_today_appointments",
    "view_tomorrow_appointments",
    "view_week_appointments",
    "view_next_week_appointments",
    "view_appointments_by_exact_date",
    "confirm_appointment",
    "reject_appointment",
    "cancel_appointment",
}


def is_appointment_action(action: str) -> bool:
    return action in APPOINTMENT_ACTIONS
