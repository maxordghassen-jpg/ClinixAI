"""
Google Places API Service
Version optimisée avec Text Search pour médecins
"""
import time
import requests
from typing import List, Dict, Optional
from config.settings import GOOGLE_MAPS_API_KEY, SEARCH_RADIUS
from utils.logger import get_logger

logger = get_logger(__name__)


class GooglePlacesService:
    BASE_URL = "https://maps.googleapis.com/maps/api/place"

    def __init__(self, api_key: str = GOOGLE_MAPS_API_KEY):
        self.api_key = api_key
        self.request_count = 0

    # ============================================================
    # 🔹 Core Google Places API Methods
    # ============================================================

    def search_nearby_places(
        self,
        lat: float,
        lng: float,
        place_type: str,
        keyword: str,
        radius: int = SEARCH_RADIUS
    ) -> List[Dict]:
        """Search for places using Google Places Nearby Search API"""
        all_results = []
        url = f"{self.BASE_URL}/nearbysearch/json"

        params = {
            'location': f"{lat},{lng}",
            'radius': radius,
            'type': place_type,
            'keyword': keyword,
            'language': 'fr',
            'key': self.api_key
        }

        try:
            while True:
                response = requests.get(url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()
                self.request_count += 1

                if data.get('status') not in ['OK', 'ZERO_RESULTS']:
                    logger.error(
                        f"API Error: {data.get('status')} - {data.get('error_message', '')}"
                    )
                    break

                results = data.get('results', [])
                all_results.extend(results)
                logger.debug(f"Found {len(results)} places. Total: {len(all_results)}")

                # Next page
                next_page_token = data.get('next_page_token')
                if not next_page_token:
                    break

                time.sleep(2)
                params = {'pagetoken': next_page_token, 'key': self.api_key}

            return all_results

        except requests.exceptions.RequestException as e:
            logger.error(f"Request error: {e}")
            return []

    def text_search_places(
        self,
        query: str,
        lat: float,
        lng: float,
        radius: int = SEARCH_RADIUS
    ) -> List[Dict]:
        """
        Search using Text Search API (pour médecins avec spécialité)
        Plus précis pour trouver des spécialités médicales
        """
        all_results = []
        url = f"{self.BASE_URL}/textsearch/json"

        params = {
            'query': query,
            'location': f"{lat},{lng}",
            'radius': radius,
            'language': 'fr',
            'key': self.api_key
        }

        try:
            while True:
                response = requests.get(url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()
                self.request_count += 1

                if data.get('status') not in ['OK', 'ZERO_RESULTS']:
                    logger.error(
                        f"Text Search API Error: {data.get('status')} - "
                        f"{data.get('error_message', '')}"
                    )
                    break

                results = data.get('results', [])
                all_results.extend(results)
                logger.debug(f"Text Search found {len(results)} places. Total: {len(all_results)}")

                # Next page
                next_page_token = data.get('next_page_token')
                if not next_page_token:
                    break

                time.sleep(2)
                params = {'pagetoken': next_page_token, 'key': self.api_key}

            return all_results

        except requests.exceptions.RequestException as e:
            logger.error(f"Text Search request error: {e}")
            return []

    def get_place_details(self, place_id: str) -> Optional[Dict]:
        """Get detailed information about a place"""
        url = f"{self.BASE_URL}/details/json"
        params = {
            'place_id': place_id,
            'fields': (
                'name,formatted_address,formatted_phone_number,opening_hours,geometry,'
                'photos,website,rating,user_ratings_total,types,url,editorial_summary'
            ),
            'language': 'fr',
            'key': self.api_key
        }

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            self.request_count += 1

            if data.get('status') == 'OK':
                return data.get('result')
            else:
                logger.error(f"Details API Error: {data.get('status')}")
                return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting place details: {e}")
            return None

    def get_photo_url(self, photo_reference: str, max_width: int = 400) -> str:
        """Get photo URL from photo reference"""
        return f"{self.BASE_URL}/photo?maxwidth={max_width}&photoreference={photo_reference}&key={self.api_key}"

    # ============================================================
    # 🔹 Advanced Doctor Search with Text Search API
    # ============================================================

    def search_doctors_with_text_search(
        self,
        lat: float,
        lng: float,
        city_name: str,
        radius: int = SEARCH_RADIUS
    ) -> List[Dict]:
        """
        🎯 NOUVELLE MÉTHODE : Recherche des médecins avec Text Search API
        Utilise les COORDONNÉES GPS pour une recherche précise par délégation
        """
        all_doctors = []
        seen_place_ids = set()

        # Liste des spécialités à rechercher
        specialties_to_search = [
            # Spécialités principales
            {'query': 'pédiatre', 'specialty': 'Pédiatre'},
            {'query': 'cardiologue', 'specialty': 'Cardiologue'},
            {'query': 'gynécologue', 'specialty': 'Gynécologue'},
            {'query': 'dermatologue', 'specialty': 'Dermatologue'},
            {'query': 'dentiste', 'specialty': 'Dentiste'},
            {'query': 'ophtalmologue', 'specialty': 'Ophtalmologue'},
            {'query': 'ORL', 'specialty': 'ORL'},
            {'query': 'orthopédiste', 'specialty': 'Orthopédiste'},
            {'query': 'neurologue', 'specialty': 'Neurologue'},
            {'query': 'psychiatre', 'specialty': 'Psychiatre'},
            
            # Spécialités secondaires
            {'query': 'radiologue', 'specialty': 'Radiologue'},
            {'query': 'pneumologue', 'specialty': 'Pneumologue'},
            {'query': 'gastro-entérologue', 'specialty': 'Gastro-entérologue'},
            {'query': 'endocrinologue', 'specialty': 'Endocrinologue'},
            {'query': 'rhumatologue', 'specialty': 'Rhumatologue'},
            {'query': 'urologue', 'specialty': 'Urologue'},
            {'query': 'chirurgien', 'specialty': 'Chirurgien'},
            {'query': 'anesthésiste', 'specialty': 'Anesthésiste'},
            
            # Recherche générique (pour les généralistes)
            {'query': 'médecin généraliste', 'specialty': 'Généraliste'},
            {'query': 'docteur', 'specialty': None}  # Fallback
        ]

        logger.info(f"🔍 Text Search for doctors in {city_name}")
        logger.info(f"   📍 GPS: {lat}, {lng} (radius: {radius}m)")
        logger.info(f"   Searching {len(specialties_to_search)} specialty types...")

        for idx, spec_config in enumerate(specialties_to_search, 1):
            # ✅ CHANGEMENT CLÉ : Utiliser juste la spécialité sans nom de ville
            # Google utilisera les coordonnées GPS pour localiser
            query = f"{spec_config['query']} Tunisia"  # Juste spécialité + pays
            specialty = spec_config['specialty']
            
            logger.debug(f"  [{idx}/{len(specialties_to_search)}] Searching: {query} near {city_name}")

            try:
                # Utiliser Text Search API avec coordonnées GPS
                doctors = self.text_search_places(
                    query=query,
                    lat=lat,
                    lng=lng,
                    radius=radius  # Rayon en mètres autour des coordonnées
                )

                new_count = 0
                for doctor in doctors:
                    place_id = doctor.get('place_id')
                    
                    # Éviter les doublons
                    if place_id in seen_place_ids:
                        continue
                    
                    seen_place_ids.add(place_id)
                    
                    # Marquer la spécialité détectée
                    if specialty:
                        doctor['detected_specialty'] = specialty
                    
                    all_doctors.append(doctor)
                    new_count += 1

                if new_count > 0:
                    logger.debug(f"      → Found {new_count} new {specialty or 'doctors'}")

                # Respecter les limites de l'API
                time.sleep(0.3)

            except Exception as e:
                logger.error(f"Error searching {query}: {e}")

        logger.info(f"✅ Total doctors found in {city_name}: {len(all_doctors)}")
        
        return all_doctors

    # ============================================================
    # 🔹 Data Extraction & Formatting
    # ============================================================

    def extract_place_data(self, place: Dict, details: Optional[Dict] = None) -> Dict:
        """Extract and structure place data"""
        place_data = {
            'place_id': place.get('place_id'),
            'name': place.get('name'),
            'address': place.get('vicinity') or place.get('formatted_address', ''),
            'coordinates': {
                'lat': place.get('geometry', {}).get('location', {}).get('lat'),
                'lng': place.get('geometry', {}).get('location', {}).get('lng')
            },
            'rating': place.get('rating'),
            'user_ratings_total': place.get('user_ratings_total', 0),
            'types': place.get('types', []),
            'image_url': None,
            'phone_number': None,
            'website': None,
            'opening_hours': None,
            'is_open_now': place.get('opening_hours', {}).get('open_now'),
            'google_maps_url': None,
            'specialty': None
        }

        # 🎯 PRIORITÉ 1 : Spécialité détectée par Text Search
        if 'detected_specialty' in place:
            place_data['specialty'] = place['detected_specialty']
        
        # 🎯 PRIORITÉ 2 : Extraction depuis le nom
        elif 'doctor' in place.get('types', []):
            extracted = self._extract_specialty_from_name(place.get('name', ''))
            if extracted:
                place_data['specialty'] = extracted
        
        # 🎯 PRIORITÉ 3 : Extraction depuis les détails
        if not place_data['specialty'] and details:
            extracted = self._extract_specialty_from_details(details)
            if extracted:
                place_data['specialty'] = extracted

        # Photo
        photos = place.get('photos', [])
        if photos:
            photo_reference = photos[0].get('photo_reference')
            if photo_reference:
                place_data['image_url'] = self.get_photo_url(photo_reference)

        # Détails supplémentaires
        if details:
            place_data['address'] = details.get('formatted_address', place_data['address'])
            place_data['phone_number'] = details.get('formatted_phone_number')
            place_data['website'] = details.get('website')
            place_data['google_maps_url'] = details.get('url')

            # Editorial summary (peut contenir la spécialité)
            editorial = details.get('editorial_summary', {}).get('overview', '')
            if editorial and not place_data['specialty']:
                extracted = self._extract_specialty_from_text(editorial)
                if extracted:
                    place_data['specialty'] = extracted

            # Horaires
            opening_hours = details.get('opening_hours', {})
            if opening_hours:
                place_data['opening_hours'] = {
                    'weekday_text': opening_hours.get('weekday_text', []),
                    'periods': self._format_periods(opening_hours.get('periods', []))
                }
                place_data['is_open_now'] = opening_hours.get('open_now')

        return place_data

    # ============================================================
    # 🔹 Specialty Extraction Methods
    # ============================================================

    def _extract_specialty_from_name(self, name: str) -> Optional[str]:
        """Extraire la spécialité depuis le nom"""
        specialty_keywords = {
            'Pédiatre': ['pédiatre', 'pediatre', 'pédiatrie', 'pediatrie'],
            'Cardiologue': ['cardiologue', 'cardiologie', 'coeur', 'cardiaque'],
            'Dentiste': ['dentiste', 'dentaire', 'dent', 'dental'],
            'Dermatologue': ['dermatologue', 'dermatologie', 'dermatolog', 'peau'],
            'Gynécologue': ['gynécologue', 'gynécologie', 'gynecolog', 'femme'],
            'Ophtalmologue': ['ophtalmologue', 'ophtalmologie', 'ophtalmo', 'oeil', 'yeux'],
            'ORL': ['orl', 'oto-rhino', 'otorhinolaryngolog', 'nez', 'gorge', 'oreille'],
            'Orthopédiste': ['orthopédiste', 'orthopédie', 'orthoped'],
            'Urologue': ['urologue', 'urologie', 'urolog'],
            'Neurologue': ['neurologue', 'neurologie', 'neurolog', 'neuro'],
            'Psychiatre': ['psychiatre', 'psychiatrie', 'psychiatr'],
            'Radiologue': ['radiologue', 'radiologie', 'radiolog', 'imagerie'],
            'Généraliste': ['généraliste', 'médecine générale', 'generaliste'],
            'Pneumologue': ['pneumologue', 'pneumologie', 'pneumolog', 'poumon'],
            'Gastro-entérologue': ['gastro', 'entérologue', 'gastroenterolog', 'digestif'],
            'Endocrinologue': ['endocrinologue', 'endocrinologie', 'endocrinolog', 'diabète'],
            'Rhumatologue': ['rhumatologue', 'rhumatologie', 'rhumatolog'],
            'Anesthésiste': ['anesthésiste', 'anesthésie', 'anesthes'],
            'Chirurgien': ['chirurgien', 'chirurgie', 'chirurg']
        }

        name_lower = name.lower()
        
        # Recherche par ordre de priorité (plus spécifique d'abord)
        for specialty, keywords in specialty_keywords.items():
            for keyword in keywords:
                if keyword in name_lower:
                    return specialty
        
        return None

    def _extract_specialty_from_details(self, details: Dict) -> Optional[str]:
        """Extraire la spécialité depuis les détails"""
        # Types Google
        types = details.get('types', [])
        
        type_mapping = {
            'dentist': 'Dentiste',
            'physiotherapist': 'Kinésithérapeute'
        }
        
        for gtype, specialty in type_mapping.items():
            if gtype in types:
                return specialty
        
        return None

    def _extract_specialty_from_text(self, text: str) -> Optional[str]:
        """Extraire la spécialité depuis un texte quelconque"""
        return self._extract_specialty_from_name(text)

    # ============================================================
    # 🔹 Formatting Utilities
    # ============================================================

    def _format_periods(self, periods: List[Dict]) -> List[Dict]:
        """Format opening hours periods"""
        formatted_periods = []
        days_map = {
            0: 'Lundi', 1: 'Mardi', 2: 'Mercredi', 3: 'Jeudi',
            4: 'Vendredi', 5: 'Samedi', 6: 'Dimanche'
        }

        for period in periods:
            formatted_period = {}

            if 'open' in period:
                open_info = period['open']
                day = open_info.get('day')
                time_val = open_info.get('time', '0000')
                formatted_period['open'] = {
                    'day': day,
                    'day_name': days_map.get(day, 'Unknown'),
                    'time': self._format_time(time_val)
                }

            if 'close' in period:
                close_info = period['close']
                day = close_info.get('day')
                time_val = close_info.get('time', '0000')
                formatted_period['close'] = {
                    'day': day,
                    'day_name': days_map.get(day, 'Unknown'),
                    'time': self._format_time(time_val)
                }

            formatted_periods.append(formatted_period)

        return formatted_periods

    def _format_time(self, time_str: str) -> str:
        """Convert time from HHMM to HH:MM"""
        if not time_str or len(time_str) != 4:
            return time_str
        return f"{time_str[:2]}:{time_str[2:]}"

    # ============================================================
    # 🔹 Utility
    # ============================================================

    def get_request_count(self) -> int:
        """Get total API requests made"""
        return self.request_count