"""
API Backend pour Recherche de Proximité - Version Complète
Avec affichage de toutes les informations détaillées
"""
from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient
from math import radians, cos, sin, asin, sqrt
from typing import List, Dict
import os

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Configuration MongoDB
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb+srv://admin:Admin3131@medical-cluster.qjwgdmm.mongodb.net/')
DATABASE_NAME = os.getenv('DATABASE_NAME', 'medical_data_tunisia')

# Connexion MongoDB
client = MongoClient(MONGODB_URI)
db = client[DATABASE_NAME]


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculer la distance entre deux points GPS en kilomètres
    Formule de Haversine (très précise)
    """
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    
    r = 6371  # Rayon de la Terre en km
    
    return c * r


def format_place_result(place: Dict, distance: float, place_lat: float, place_lng: float) -> Dict:
    """
    Formater un établissement avec toutes les informations nécessaires
    """
    # Extraire opening_hours si disponible
    opening_hours = place.get('opening_hours', {})
    weekday_text = opening_hours.get('weekday_text', []) if isinstance(opening_hours, dict) else []
    is_open_now = opening_hours.get('open_now') if isinstance(opening_hours, dict) else place.get('is_open_now')
    
    return {
        'id': str(place['_id']),
        'place_id': place.get('place_id'),
        'name': place.get('name'),
        'address': place.get('address'),
        'coordinates': {
            'lat': place_lat,
            'lng': place_lng
        },
        'distance': round(distance, 2),
        'distance_text': f"{round(distance, 1)} km" if distance >= 1 else f"{int(distance * 1000)} m",
        'phone_number': place.get('phone_number'),
        'website': place.get('website'),
        'rating': place.get('rating'),
        'user_ratings_total': place.get('user_ratings_total'),
        'is_open_now': is_open_now,
        'opening_hours': weekday_text,
        'specialty': place.get('specialty'),
        'governorate': place.get('governorate'),
        'types': place.get('types', []),
        'image_url': place.get('image_url'),
        'google_maps_url': place.get('google_maps_url'),
        'business_status': place.get('business_status')
    }


@app.route('/api/nearby', methods=['POST'])
def find_nearby():
    """
    Endpoint principal : Trouver les établissements à proximité
    Avec filtrage strict par catégorie
    """
    try:
        data = request.json
        
        if not data or 'latitude' not in data or 'longitude' not in data:
            return jsonify({'error': 'latitude et longitude requis'}), 400
        
        user_lat = float(data['latitude'])
        user_lng = float(data['longitude'])
        category = data.get('category', 'doctors')
        radius_km = float(data.get('radius', 20))
        limit = int(data.get('limit', 20))
        
        # Filtres optionnels
        specialty = data.get('specialty')  # Pour les médecins
        governorate = data.get('governorate')  # Pour filtrer par gouvernorat
        
        print(f"\n🔍 Recherche : {category}")
        print(f"📍 Position utilisateur : {user_lat}, {user_lng}")
        print(f"📏 Rayon : {radius_km} km")
        
        # IMPORTANT: Utiliser la collection correspondant EXACTEMENT à la catégorie
        collection = db[category]
        
        # Mapper les noms de collections vers leurs types
        collection_type_map = {
            'pharmacies': 'pharmacy',
            'on_call_pharmacies': 'on_call_pharmacy',
            'night_pharmacies': 'night_pharmacy',
            'parapharmacies': 'parapharmacy',
            'clinics': 'clinic',
            'hospitals': 'hospital',
            'analysis_labs': 'analysis_lab',
            'nurses': 'nurse',
            'physiotherapists': 'physiotherapist',
            'doctors': 'doctor'
        }
        
        # Construire le filtre MongoDB avec collection_type
        search_filter = {
            'collection_type': collection_type_map.get(category, category)
        }
        
        if specialty and category == 'doctors':
            search_filter['specialty'] = {'$regex': specialty, '$options': 'i'}
        
        if governorate:
            search_filter['governorate'] = {'$regex': governorate, '$options': 'i'}
        
        # Récupérer UNIQUEMENT les documents de cette collection avec le bon type
        all_places = list(collection.find(search_filter))
        print(f"📊 Documents trouvés dans {category} avec type '{collection_type_map.get(category)}': {len(all_places)}")
        
        # Filtrer par distance
        nearby_places = []
        for place in all_places:
            if 'coordinates' not in place:
                continue
            
            coords = place['coordinates']
            
            if isinstance(coords, dict):
                if 'lat' not in coords or 'lng' not in coords:
                    continue
                place_lat = coords['lat']
                place_lng = coords['lng']
            else:
                if len(coords) < 2:
                    continue
                place_lng = coords[0]
                place_lat = coords[1]
            
            distance = haversine_distance(user_lat, user_lng, place_lat, place_lng)
            
            if distance <= radius_km:
                nearby_places.append({
                    'place': place,
                    'distance': distance,
                    'place_lat': place_lat,
                    'place_lng': place_lng
                })
        
        # Trier par distance
        nearby_places.sort(key=lambda x: x['distance'])
        
        # Limiter les résultats
        nearby_places = nearby_places[:limit]
        
        print(f"✅ Trouvés : {len(nearby_places)} établissements")
        
        # Formater les résultats
        formatted_results = [
            format_place_result(item['place'], item['distance'], item['place_lat'], item['place_lng'])
            for item in nearby_places
        ]
        
        return jsonify({
            'success': True,
            'user_location': {
                'latitude': user_lat,
                'longitude': user_lng
            },
            'radius_km': radius_km,
            'results_count': len(formatted_results),
            'results': formatted_results
        })
    
    except Exception as e:
        print(f"❌ Erreur : {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/doctors/map', methods=['POST'])
def find_doctors_for_map():
    """
    Endpoint spécial pour les médecins : Retourne tous les médecins par spécialité
    pour affichage sur carte (pas de liste ordonnée)
    """
    try:
        data = request.json
        
        user_lat = float(data['latitude'])
        user_lng = float(data['longitude'])
        radius_km = float(data.get('radius', 10))
        specialty = data.get('specialty')
        governorate = data.get('governorate')
        
        collection = db['doctors']
        
        # Construire le filtre avec collection_type
        search_filter = {
            'collection_type': 'doctor'
        }
        
        if specialty:
            search_filter['specialty'] = {'$regex': specialty, '$options': 'i'}
        
        if governorate:
            search_filter['governorate'] = {'$regex': governorate, '$options': 'i'}
        
        # Récupérer tous les médecins
        all_doctors = list(collection.find(search_filter))
        
        # Filtrer par distance et grouper par spécialité
        doctors_by_specialty = {}
        
        for doctor in all_doctors:
            if 'coordinates' not in doctor:
                continue
            
            coords = doctor['coordinates']
            
            if isinstance(coords, dict):
                if 'lat' not in coords or 'lng' not in coords:
                    continue
                doc_lat = coords['lat']
                doc_lng = coords['lng']
            else:
                if len(coords) < 2:
                    continue
                doc_lng = coords[0]
                doc_lat = coords[1]
            
            distance = haversine_distance(user_lat, user_lng, doc_lat, doc_lng)
            
            if distance <= radius_km:
                spec = doctor.get('specialty', 'Autre')
                
                if spec not in doctors_by_specialty:
                    doctors_by_specialty[spec] = []
                
                doctors_by_specialty[spec].append(
                    format_place_result(doctor, distance, doc_lat, doc_lng)
                )
        
        # Compter le total
        total_doctors = sum(len(docs) for docs in doctors_by_specialty.values())
        
        return jsonify({
            'success': True,
            'user_location': {
                'latitude': user_lat,
                'longitude': user_lng
            },
            'radius_km': radius_km,
            'total_doctors': total_doctors,
            'specialties_count': len(doctors_by_specialty),
            'doctors_by_specialty': doctors_by_specialty
        })
    
    except Exception as e:
        print(f"❌ Erreur : {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/search/manual', methods=['POST'])
def manual_search():
    """
    Recherche manuelle par nom ou lieu (sans géolocalisation)
    """
    try:
        data = request.json
        
        query = data.get('query', '').strip()
        category = data.get('category', 'doctors')
        governorate = data.get('governorate')
        specialty = data.get('specialty')
        limit = int(data.get('limit', 50))
        
        if not query and not governorate and not specialty:
            return jsonify({'error': 'Au moins un critère de recherche requis'}), 400
        
        print(f"\n🔍 Recherche manuelle : {category}")
        print(f"📝 Query : {query}")
        
        collection = db[category]
        
        # Mapper les noms de collections vers leurs types
        collection_type_map = {
            'pharmacies': 'pharmacy',
            'on_call_pharmacies': 'on_call_pharmacy',
            'night_pharmacies': 'night_pharmacy',
            'parapharmacies': 'parapharmacy',
            'clinics': 'clinic',
            'hospitals': 'hospital',
            'analysis_labs': 'analysis_lab',
            'nurses': 'nurse',
            'physiotherapists': 'physiotherapist',
            'doctors': 'doctor'
        }
        
        # Construire le filtre de recherche avec collection_type
        search_filter = {
            'collection_type': collection_type_map.get(category, category)
        }
        
        # Recherche par nom ou adresse
        if query:
            search_filter['$or'] = [
                {'name': {'$regex': query, '$options': 'i'}},
                {'address': {'$regex': query, '$options': 'i'}}
            ]
        
        # Filtres additionnels
        if specialty and category == 'doctors':
            search_filter['specialty'] = {'$regex': specialty, '$options': 'i'}
        
        if governorate:
            search_filter['governorate'] = {'$regex': governorate, '$options': 'i'}
        
        # Rechercher dans la base
        results = list(collection.find(search_filter).limit(limit))
        
        print(f"✅ Trouvés : {len(results)} établissements")
        
        # Formater les résultats (sans calcul de distance)
        formatted_results = []
        for place in results:
            coords = place.get('coordinates', {})
            
            if isinstance(coords, dict):
                place_lat = coords.get('lat')
                place_lng = coords.get('lng')
            else:
                place_lat = coords[1] if len(coords) > 1 else None
                place_lng = coords[0] if len(coords) > 0 else None
            
            # Extraire opening_hours
            opening_hours = place.get('opening_hours', {})
            weekday_text = opening_hours.get('weekday_text', []) if isinstance(opening_hours, dict) else []
            is_open_now = opening_hours.get('open_now') if isinstance(opening_hours, dict) else place.get('is_open_now')
            
            formatted_results.append({
                'id': str(place['_id']),
                'place_id': place.get('place_id'),
                'name': place.get('name'),
                'address': place.get('address'),
                'coordinates': {
                    'lat': place_lat,
                    'lng': place_lng
                } if place_lat and place_lng else None,
                'phone_number': place.get('phone_number'),
                'website': place.get('website'),
                'rating': place.get('rating'),
                'user_ratings_total': place.get('user_ratings_total'),
                'is_open_now': is_open_now,
                'opening_hours': weekday_text,
                'specialty': place.get('specialty'),
                'governorate': place.get('governorate'),
                'types': place.get('types', []),
                'image_url': place.get('image_url'),
                'google_maps_url': place.get('google_maps_url'),
                'business_status': place.get('business_status')
            })
        
        return jsonify({
            'success': True,
            'search_type': 'manual',
            'query': query,
            'results_count': len(formatted_results),
            'results': formatted_results
        })
    
    except Exception as e:
        print(f"❌ Erreur : {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/specialties', methods=['GET'])
def get_specialties():
    """
    Obtenir toutes les spécialités médicales disponibles
    """
    try:
        pipeline = [
            {'$match': {'specialty': {'$ne': None, '$ne': ''}}},
            {'$group': {'_id': '$specialty', 'count': {'$sum': 1}}},
            {'$sort': {'count': -1}}
        ]
        
        results = db['doctors'].aggregate(pipeline)
        
        specialties = [
            {'name': doc['_id'], 'count': doc['count']}
            for doc in results
        ]
        
        return jsonify({'success': True, 'specialties': specialties})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/governorates', methods=['GET'])
def get_governorates():
    """
    Obtenir tous les gouvernorats disponibles
    """
    try:
        category = request.args.get('category', 'doctors')
        
        pipeline = [
            {'$match': {'governorate': {'$ne': None, '$ne': ''}}},
            {'$group': {'_id': '$governorate', 'count': {'$sum': 1}}},
            {'$sort': {'_id': 1}}
        ]
        
        results = db[category].aggregate(pipeline)
        
        governorates = [
            {'name': doc['_id'], 'count': doc['count']}
            for doc in results
        ]
        
        return jsonify({'success': True, 'governorates': governorates})
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/categories', methods=['GET'])
def get_categories():
    """
    Obtenir la liste de toutes les catégories disponibles
    """
    categories = [
        {'id': 'pharmacies', 'name': 'Pharmacies', 'icon': '💊'},
        {'id': 'on_call_pharmacies', 'name': 'Pharmacies de Garde', 'icon': '🚑'},
        {'id': 'night_pharmacies', 'name': 'Pharmacies de Nuit', 'icon': '🌙'},
        {'id': 'parapharmacies', 'name': 'Parapharmacies', 'icon': '🧴'},
        {'id': 'clinics', 'name': 'Cliniques', 'icon': '🏥'},
        {'id': 'hospitals', 'name': 'Hôpitaux', 'icon': '🏨'},
        {'id': 'analysis_labs', 'name': 'Laboratoires', 'icon': '🔬'},
        {'id': 'nurses', 'name': 'Infirmiers', 'icon': '👨‍⚕️'},
        {'id': 'physiotherapists', 'name': 'Kinésithérapeutes', 'icon': '💆'},
        {'id': 'doctors', 'name': 'Médecins', 'icon': '👨‍⚕️'}
    ]
    
    for cat in categories:
        try:
            count = db[cat['id']].count_documents({})
            cat['count'] = count
        except:
            cat['count'] = 0
    
    return jsonify({'success': True, 'categories': categories})


@app.route('/api/test', methods=['GET'])
def test_connection():
    """
    Tester la connexion MongoDB
    """
    try:
        db.command('ping')
        
        examples = {}
        collections = ['analysis_labs', 'doctors', 'pharmacies', 'clinics']
        
        for coll_name in collections:
            doc = db[coll_name].find_one()
            if doc:
                doc.pop('_id', None)
                examples[coll_name] = doc
        
        return jsonify({
            'success': True,
            'message': 'Connexion MongoDB OK',
            'database': DATABASE_NAME,
            'examples': examples
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


if __name__ == '__main__':
    print("🚀 API de proximité démarrée - Version Complète")
    print("\nEndpoints disponibles:")
    print("  POST /api/nearby - Trouver à proximité (géolocalisation)")
    print("  POST /api/search/manual - Recherche manuelle (nom/lieu)")
    print("  POST /api/doctors/map - Médecins groupés par spécialité pour carte")
    print("  GET  /api/specialties - Liste des spécialités médicales")
    print("  GET  /api/governorates - Liste des gouvernorats")
    print("  GET  /api/categories - Liste des catégories")
    print("  GET  /api/test - Tester la connexion MongoDB")
    print(f"\n🌐 API démarrée sur http://localhost:5000\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
