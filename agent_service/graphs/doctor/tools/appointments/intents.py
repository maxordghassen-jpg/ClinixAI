APPOINTMENT_ACTIONS = {
    "view_appointments",
    "view_today_appointments",
    "view_tomorrow_appointments",
    "view_week_appointments",
    "view_next_week_appointments",
    "view_appointments_by_exact_date",
    "daily_schedule",
    "weekly_schedule",
    "confirm_appointment",
    "reject_appointment",
    "cancel_appointment",
    "reschedule_appointment",
}

# Actions that produce a compact schedule view rather than the default list format
SCHEDULE_VIEW_ACTIONS = {"daily_schedule", "weekly_schedule"}


def is_appointment_action(action: str) -> bool:
    return action in APPOINTMENT_ACTIONS


def is_schedule_view(action: str) -> bool:
    return action in SCHEDULE_VIEW_ACTIONS
