MEDICAL_PLACES_PROMPT = """
Tool: medical_places

Role:
Understand patient requests for medical places in Tunisia
in English, French, and Arabic.

The system must normalize multilingual medical terms
to the same internal medical categories.

Examples:
- pharmacy
- pharmacie
- صيدلية
→ pharmacies

- hospital
- hopital
- hôpital
- مستشفى
→ hospitals

- clinic
- clinique
- عيادة
→ clinics

- doctor
- médecin
- طبيب
→ doctors

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
* nearest pharmacie
* أقرب صيدلية
* find cardiologists near me
* best clinic in Tunis
* show nearby hospitals
* find dentist in Sfax
"""