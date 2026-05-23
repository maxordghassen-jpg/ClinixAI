AVAILABILITY_ACTIONS = {
    # Template management
    "view_available_slots",
    "view_today_availability",
    "view_tomorrow_availability",
    "view_week_availability",
    "view_next_week_availability",
    "view_availability",
    "create_availability",
    "update_availability",
    "block_availability",
    "unblock_availability",
    "delete_availability",
    # Exception management
    "block_day",
    "vacation_mode",
    "override_hours",
    "view_exceptions",
    "delete_exception",
}

# Actions that create or manage availability exceptions
EXCEPTION_ACTIONS = {"block_day", "vacation_mode", "override_hours", "view_exceptions", "delete_exception"}


def is_availability_action(action: str) -> bool:
    return action in AVAILABILITY_ACTIONS


def is_exception_action(action: str) -> bool:
    return action in EXCEPTION_ACTIONS
