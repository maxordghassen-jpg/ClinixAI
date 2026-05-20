MEDICAL_PLACES_PROMPT = """
Tool: medical_places
Role: understand patient requests for medical places in Tunisia in French,
English, Arabic, and noisy spelling.

Choose only one action:
* search_nearby_hospitals
* search_nearby_pharmacies
* search_nearby_clinics
* search_doctors_by_specialty
* search_by_city

Extract entities when present:
* category
* specialty
* city
* governorate
* latitude
* longitude
* radius
* limit

Examples:
* nearest pharmacy
* find cardiologists near me
* best clinic in Tunis
* show nearby hospitals
* find dentist in Sfax
"""
