"""
Extraire SEULEMENT les délégations qui ne sont pas dans la base
"""
from pymongo import MongoClient
from config.settings import MONGODB_URI, DATABASE_NAME, TUNISIA_DELEGATIONS
from services.google_places_service import GooglePlacesService
import time

def get_existing_cities():
    """Récupérer toutes les villes déjà extraites"""
    client = MongoClient(MONGODB_URI)
    db = client[DATABASE_NAME]
    
    all_cities = set()
    
    for collection_name in ['pharmacies', 'doctors', 'clinics']:
        try:
            cursor = db[collection_name].find({}, {'search_city': 1, 'address': 1})
            for doc in cursor:
                if 'search_city' in doc:
                    all_cities.add(doc['search_city'].lower())
                # Aussi extraire depuis l'adresse
                if 'address' in doc:
                    address_lower = doc['address'].lower()
                    for delegation in TUNISIA_DELEGATIONS:
                        if delegation['name'].lower() in address_lower:
                            all_cities.add(delegation['name'].lower())
        except:
            pass
    
    return all_cities

def find_missing_delegations():
    """Identifier délégations manquantes"""
    print("🔍 Analyse des délégations manquantes...\n")
    
    existing_cities = get_existing_cities()
    print(f"✅ Villes existantes: {len(existing_cities)}")
    
    missing = []
    for delegation in TUNISIA_DELEGATIONS:
        if delegation['name'].lower() not in existing_cities:
            missing.append(delegation)
    
    print(f"❌ Délégations manquantes: {len(missing)}\n")
    
    if missing:
        print("📋 Liste des délégations à extraire:")
        for d in missing:
            print(f"  • {d['name']:30s} ({d['governorate']})")
    
    return missing

def extract_delegation(delegation, service, db):
    """Extraire une délégation spécifique"""
    print(f"\n{'='*60}")
    print(f"🔍 Extraction: {delegation['name']} ({delegation['governorate']})")
    print(f"{'='*60}")
    
    results = {
        'delegation': delegation['name'],
        'governorate': delegation['governorate'],
        'categories': {}
    }
    
    # 1. Pharmacies
    print("📍 Recherche pharmacies...")
    pharmacies = service.search_nearby_places(
        lat=delegation['lat'],
        lng=delegation['lng'],
        place_type='pharmacy',
        keyword='pharmacie',
        radius=10000
    )
    
    if pharmacies:
        for pharmacy in pharmacies:
            details = service.get_place_details(pharmacy.get('place_id'))
            place_data = service.extract_place_data(pharmacy, details)
            place_data['governorate'] = delegation['governorate']
            place_data['delegation'] = delegation['name']
            place_data['search_city'] = delegation['name']
            
            db['pharmacies'].insert_one(place_data)
        
        print(f"  ✅ {len(pharmacies)} pharmacies ajoutées")
        results['categories']['pharmacies'] = len(pharmacies)
    else:
        print(f"  ⚠️  Aucune pharmacie trouvée")
        results['categories']['pharmacies'] = 0
    
    time.sleep(1)
    
    # 2. Médecins
    print("👨‍⚕️ Recherche médecins...")
    doctors = service.search_doctors_with_text_search(
        lat=delegation['lat'],
        lng=delegation['lng'],
        city_name=delegation['name'],
        radius=10000
    )
    
    if doctors:
        for doctor in doctors:
            details = service.get_place_details(doctor.get('place_id'))
            place_data = service.extract_place_data(doctor, details)
            place_data['governorate'] = delegation['governorate']
            place_data['delegation'] = delegation['name']
            place_data['search_city'] = delegation['name']
            
            db['doctors'].insert_one(place_data)
        
        print(f"  ✅ {len(doctors)} médecins ajoutés")
        results['categories']['doctors'] = len(doctors)
    else:
        print(f"  ⚠️  Aucun médecin trouvé")
        results['categories']['doctors'] = 0
    
    time.sleep(1)
    
    # 3. Cliniques
    print("🏥 Recherche cliniques...")
    clinics = service.search_nearby_places(
        lat=delegation['lat'],
        lng=delegation['lng'],
        place_type='hospital',
        keyword='clinique',
        radius=10000
    )
    
    if clinics:
        for clinic in clinics:
            details = service.get_place_details(clinic.get('place_id'))
            place_data = service.extract_place_data(clinic, details)
            place_data['governorate'] = delegation['governorate']
            place_data['delegation'] = delegation['name']
            place_data['search_city'] = delegation['name']
            
            db['clinics'].insert_one(place_data)
        
        print(f"  ✅ {len(clinics)} cliniques ajoutées")
        results['categories']['clinics'] = len(clinics)
    else:
        print(f"  ⚠️  Aucune clinique trouvée")
        results['categories']['clinics'] = 0
    
    # Résumé
    total = sum(results['categories'].values())
    print(f"\n📊 Total {delegation['name']}: {total} établissements")
    
    return results

def main():
    """Extraire délégations manquantes"""
    print("="*60)
    print("🎯 EXTRACTION DÉLÉGATIONS MANQUANTES")
    print("="*60)
    print()
    
    # 1. Identifier délégations manquantes
    missing = find_missing_delegations()
    
    if not missing:
        print("\n✅ Aucune délégation manquante!")
        print("   Votre base est complète.")
        return
    
    print(f"\n💰 Coût estimé: ${len(missing) * 2:.2f} - ${len(missing) * 3:.2f}")
    print(f"⏱️  Durée estimée: {len(missing) * 2 / 60:.0f}-{len(missing) * 3 / 60:.0f} heures")
    
    response = input(f"\nExtraire {len(missing)} délégations? (o/n): ")
    if response.lower() != 'o':
        print("❌ Extraction annulée")
        return
    
    # 2. Connexion
    client = MongoClient(MONGODB_URI)
    db = client[DATABASE_NAME]
    service = GooglePlacesService()
    
    # 3. Extraction
    all_results = []
    
    for idx, delegation in enumerate(missing, 1):
        print(f"\n[{idx}/{len(missing)}]")
        
        try:
            result = extract_delegation(delegation, service, db)
            all_results.append(result)
            
            time.sleep(2)
            
        except Exception as e:
            print(f"❌ Erreur: {e}")
    
    # 4. Rapport final
    print("\n" + "="*60)
    print("📊 RAPPORT FINAL")
    print("="*60)
    
    total_pharmacies = sum(r['categories'].get('pharmacies', 0) for r in all_results)
    total_doctors = sum(r['categories'].get('doctors', 0) for r in all_results)
    total_clinics = sum(r['categories'].get('clinics', 0) for r in all_results)
    total_all = total_pharmacies + total_doctors + total_clinics
    
    print(f"\nDélégations extraites: {len(all_results)}")
    print(f"  • Pharmacies: {total_pharmacies}")
    print(f"  • Médecins: {total_doctors}")
    print(f"  • Cliniques: {total_clinics}")
    print(f"  • TOTAL: {total_all}")
    
    print("\n✅ Extraction terminée!")

if __name__ == "__main__":
    main()