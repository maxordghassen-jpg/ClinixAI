# ClinixAI — Geolocation Service

## 1. Service Overview

The geolocation service (`geo_service/`) is a Flask-based microservice that:
1. **Populates** a MongoDB database with medical facility data extracted from Google Places API across all 24 Tunisian governorates (offline batch extraction job)
2. **Serves** a proximity API (`api_proximity.py`) that the agent service queries at runtime to find nearby doctors, pharmacies, clinics, and other medical facilities

- **Proximity API port**: 5000
- **Framework**: Flask + flask-cors
- **Storage**: MongoDB Atlas (`medical_data_tunisia` database)
- **Distance algorithm**: Haversine formula
- **Data source**: Google Places Text Search API

---

## 2. Data Extraction Pipeline

### `main.py` — `MedicalDataExtractor`

The `MedicalDataExtractor` class runs a batch extraction process that queries Google Places for medical facilities across all 24 Tunisian governorates and 8 medical categories.

**Supported categories:**

| Category Key | MongoDB Collection | Display Name |
|---|---|---|
| `doctors` | `doctors` | Médecins |
| `pharmacies` | `pharmacies` | Pharmacies |
| `on_call_pharmacies` | `on_call_pharmacies` | Pharmacies de Garde |
| `night_pharmacies` | `night_pharmacies` | Pharmacies de Nuit |
| `parapharmacies` | `parapharmacies` | Parapharmacies |
| `clinics` | `clinics` | Cliniques |
| `hospitals` | `hospitals` | Hôpitaux |
| `analysis_labs` | `analysis_labs` | Laboratoires d'Analyse |
| `nurses` | `nurses` | Infirmiers |
| `physiotherapists` | `physiotherapists` | Kinésithérapeutes |

**All 24 Tunisian governorates** are covered: Tunis, Ariana, Ben Arous, Manouba, Nabeul, Zaghouan, Bizerte, Béja, Jendouba, Kef, Siliana, Sousse, Monastir, Mahdia, Sfax, Kairouan, Kasserine, Sidi Bouzid, Gabès, Medenine, Tataouine, Gafsa, Tozeur, Kébili.

### Extraction Process

```python
class MedicalDataExtractor:
    def run_extraction(self, categories=None):
        for category_key, category_config in PLACE_CATEGORIES.items():
            places = self.extract_category(category_key, category_config)
            self.save_to_json(places, category_config['filename'])
            self.save_to_mongodb(places, category_config['collection'])
            self.save_checkpoint(category_key, places, stats)
```

For each category and each governorate, `GooglePlacesTextSearchService` calls:
```
POST https://places.googleapis.com/v1/places:searchText
Body: {
    "textQuery": "cardiologist Tunis",
    "locationBias": { "circle": { "center": { "latitude": 36.8, "longitude": 10.1 }, "radius": 30000 } }
}
```

Multiple queries per category are issued to improve coverage (e.g., "médecin Tunis", "docteur Tunis", "طبيب تونس" for doctors in Tunis governorate).

### Doctor Specialty Extraction

For the `doctors` collection, the extractor analyzes the name and type fields of each result to extract the medical specialty. This populates the `specialty` field which is later used for specialty-based filtering:

```python
def _analyze_doctor_specialties(self, doctors):
    specialty_count = {}
    for doctor in doctors:
        specialty = doctor.get('specialty')  # e.g., "Cardiologue", "Dentiste"
        if specialty:
            specialty_count[specialty] = specialty_count.get(specialty, 0) + 1
```

---

## 3. MongoDB Document Schema

Each extracted facility is stored as:

```json
{
  "_id": ObjectId("..."),
  "place_id": "ChIJ...",                     // Google Places unique ID
  "name": "Dr. Mohamed Ben Salah",
  "address": "12 Avenue Habib Bourguiba, Tunis 1000",
  "coordinates": { "lat": 36.8190, "lng": 10.1658 },
  "phone_number": "+216 71 000 000",
  "website": "https://...",
  "rating": 4.5,
  "user_ratings_total": 127,
  "specialty": "Cardiologue",                // doctors only
  "governorate": "Tunis",
  "collection_type": "doctor",               // for query filtering
  "types": ["doctor", "health", "establishment"],
  "opening_hours": {
    "weekday_text": ["Lundi: 09:00–17:00", ...],
    "open_now": true
  },
  "image_url": "https://...",
  "google_maps_url": "https://maps.google.com/...",
  "business_status": "OPERATIONAL",
  "search_query": "cardiologue Tunis",       // for text search fallback
  "last_updated": "2026-01-15T10:00:00"
}
```

---

## 4. Proximity API: `api_proximity.py`

This Flask application provides the runtime proximity search API consumed by the agent service.

### Haversine Distance Formula

```python
def haversine_distance(lat1, lon1, lat2, lon2) -> float:
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    r = 6371  # Earth radius in km
    return c * r
```

The Haversine formula computes the great-circle distance between two GPS coordinates on Earth's surface. It is accurate to within ~0.5% for typical distances (up to ~100km).

### Endpoints

#### `POST /api/nearby`
Find medical facilities within a radius.

**Request:**
```json
{
    "latitude": 36.8190,
    "longitude": 10.1658,
    "category": "doctors",
    "radius": 20,
    "limit": 20,
    "specialty": "Cardiologue",      // optional
    "governorate": "Tunis"            // optional
}
```

**Pipeline:**
1. Query MongoDB collection `{category}` with specialty/governorate filters
2. For each document with valid coordinates: compute Haversine distance
3. Filter to those within `radius_km`
4. Sort by distance (ascending)
5. Limit to first N results
6. Format each result with distance_text ("2.3 km" or "450 m")

**Response:**
```json
{
    "success": true,
    "user_location": { "latitude": 36.82, "longitude": 10.17 },
    "radius_km": 20,
    "results_count": 5,
    "results": [
        {
            "id": "...",
            "name": "Dr. Ben Salah",
            "address": "...",
            "coordinates": { "lat": 36.83, "lng": 10.18 },
            "distance": 1.2,
            "distance_text": "1.2 km",
            "phone_number": "+216...",
            "rating": 4.5,
            "specialty": "Cardiologue",
            "is_open_now": true,
            "opening_hours": ["Lundi: 09:00–17:00", ...],
            "google_maps_url": "https://..."
        }
    ]
}
```

#### `POST /api/doctors/map`
Returns doctors grouped by specialty for map display.

**Pipeline:** Same as `/api/nearby` but groups results into `{ specialty → [doctors] }` map structure for frontend map rendering.

#### `POST /api/search/manual`
Text-based search without geolocation (name, address, type).

**Multilingual normalization** is applied to search queries before hitting MongoDB:
```python
normalization_map = {
    "pharmacies":   "pharmacie",
    "pharmacy":     "pharmacie",
    "صيدلية":       "pharmacie",   # Arabic → French
    "hospitals":    "hopital",
    "hospital":     "hopital",
    "مستشفى":       "hopital",     # Arabic → French
    "clinics":      "clinique",
    "clinic":       "clinique",
    "عيادة":        "clinique",    # Arabic → French
}
```

MongoDB query uses `$or` with regex on `name`, `address`, `search_query`, `types` fields.

#### `POST /api/doctors/lookup`
Batch resolve doctor names by MongoDB ObjectId. Used by the frontend to display doctor names from appointment records.

```json
Request:  { "ids": ["507f...", "508a..."] }
Response: { "507f...": "Dr. Ben Salah", "508a...": "Dr. Khelifi" }
```

#### `GET /api/specialties`
Returns all distinct medical specialties with counts using MongoDB aggregation:
```json
[{ "name": "Cardiologue", "count": 47 }, { "name": "Dentiste", "count": 92 }, ...]
```

#### `GET /api/governorates`
Returns all available governorates in a given category.

#### `GET /api/categories`
Returns all 10 categories with document counts.

---

## 5. Integration with Agent Service

The `GeoHandler` in the patient graph (`graphs/patient/handlers/geo_handler.py`) calls the geo service when `state.memory["step"] == "searching_places"`:

```python
class GeoHandler:
    async def find_nearby_places(
        self,
        latitude: float,
        longitude: float,
        category: str,
        specialty: str | None = None,
        radius: float = 10.0,
    ) -> list[dict]:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{GEO_SERVICE_URL}/api/nearby",
                json={
                    "latitude": latitude,
                    "longitude": longitude,
                    "category": category,
                    "radius": radius,
                    "specialty": specialty,
                    "limit": 10,
                },
                timeout=10.0,
            )
        return response.json().get("results", [])
```

The results are stored in `state.memory["geo_results"]` and:
1. Formatted into a numbered list in the agent's text response
2. Returned to the frontend as structured data for map pin rendering
3. Stored in `StateWriterNode` for the selecting_place step (patient can say "tell me more about #2")

---

## 6. Frontend Map Integration

The patient page uses **MapLibre GL** (open-source fork of Mapbox GL) via `react-map-gl` to render an interactive map.

When the agent returns geo_results:
1. Frontend extracts `place.coordinates.{lat, lng}` for each result
2. Creates a GeoJSON FeatureCollection with a Point for each facility
3. Adds a Layer to the MapLibre map with circle markers
4. Each circle is clickable — shows a Popup with name, address, phone, rating, opening hours
5. Map automatically fits bounds to show all returned results (`fitBounds`)

Map tile provider: OpenStreetMap via a public tile URL (no API key required for the base map).

---

## 7. Scheduler: `scheduler.py`

A background scheduler (`APScheduler` or similar) periodically re-runs the data extraction pipeline to keep the medical facility database fresh. The extraction is resource-intensive (thousands of API calls) so it's designed to run weekly or monthly, not per-request.

Checkpoints are saved per category so that interrupted extractions can resume without re-processing already-completed categories.
