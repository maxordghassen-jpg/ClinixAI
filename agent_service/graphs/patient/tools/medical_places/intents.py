MEDICAL_PLACE_ACTIONS = {
    "search_nearby_hospitals",
    "search_nearby_pharmacies",
    "search_nearby_clinics",
    "search_doctors_by_specialty",
    "search_by_city",
}


def is_medical_place_action(action: str) -> bool:
    return action in MEDICAL_PLACE_ACTIONS
