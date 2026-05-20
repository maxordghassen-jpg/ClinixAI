PATIENT_AVAILABILITY_ACTIONS = {
    "view_available_slots",
    "view_today_availability",
    "view_tomorrow_availability",
    "view_week_availability",
    "view_availability",
}


def is_patient_availability_action(action: str) -> bool:
    return action in PATIENT_AVAILABILITY_ACTIONS
