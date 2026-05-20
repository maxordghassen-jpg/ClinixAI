AVAILABILITY_ACTIONS = {
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
}


def is_availability_action(action: str) -> bool:
    return action in AVAILABILITY_ACTIONS
