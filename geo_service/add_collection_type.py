"""
Script pour ajouter le champ 'collection_type' à tous les documents MongoDB
Cela permet de filtrer correctement chaque type d'établissement
"""
from pymongo import MongoClient
import os

# Configuration MongoDB
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb+srv://medilink:enDZ48oOrstAMj7Q@medilink.yhf2g.mongodb.net')
DATABASE_NAME = 'medical_data_tunisia'

# Connexion MongoDB
client = MongoClient(MONGODB_URI)
db = client[DATABASE_NAME]

# Définir toutes les collections et leurs types
COLLECTIONS_CONFIG = {
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


def add_collection_type_field():
    """
    Ajoute le champ 'collection_type' à tous les documents de toutes les collections
    """
    print("🚀 Début de l'ajout du champ 'collection_type'\n")
    
    total_updated = 0
    
    for collection_name, collection_type in COLLECTIONS_CONFIG.items():
        print(f"📁 Traitement de la collection : {collection_name}")
        
        try:
            collection = db[collection_name]
            
            # Compter les documents dans la collection
            total_docs = collection.count_documents({})
            print(f"   📊 Total de documents : {total_docs}")
            
            if total_docs == 0:
                print(f"   ⚠️  Collection vide, passage à la suivante\n")
                continue
            
            # Mettre à jour tous les documents avec le champ collection_type
            result = collection.update_many(
                {},  # Tous les documents
                {
                    '$set': {
                        'collection_type': collection_type
                    }
                }
            )
            
            updated_count = result.modified_count
            total_updated += updated_count
            
            print(f"   ✅ {updated_count} documents mis à jour")
            print(f"   🏷️  Type ajouté : {collection_type}\n")
            
        except Exception as e:
            print(f"   ❌ Erreur : {e}\n")
            continue
    
    print(f"\n🎉 Terminé ! Total de documents mis à jour : {total_updated}")


def verify_collection_types():
    """
    Vérifier que le champ collection_type a bien été ajouté
    """
    print("\n\n🔍 Vérification des champs 'collection_type'\n")
    
    for collection_name, expected_type in COLLECTIONS_CONFIG.items():
        try:
            collection = db[collection_name]
            
            # Compter les documents avec collection_type
            with_type = collection.count_documents({'collection_type': {'$exists': True}})
            total = collection.count_documents({})
            
            # Récupérer un exemple
            sample = collection.find_one({'collection_type': {'$exists': True}})
            
            status = "✅" if with_type == total else "⚠️"
            print(f"{status} {collection_name}: {with_type}/{total} documents avec collection_type")
            
            if sample:
                print(f"   Exemple : {sample.get('name')} → collection_type = {sample.get('collection_type')}\n")
            
        except Exception as e:
            print(f"❌ {collection_name}: Erreur - {e}\n")


def show_stats():
    """
    Afficher les statistiques de chaque collection
    """
    print("\n\n📊 STATISTIQUES DES COLLECTIONS\n")
    print(f"{'Collection':<25} {'Total':<10} {'Avec Type':<15} {'Type'}")
    print("=" * 70)
    
    for collection_name, collection_type in COLLECTIONS_CONFIG.items():
        try:
            collection = db[collection_name]
            total = collection.count_documents({})
            with_type = collection.count_documents({'collection_type': collection_type})
            
            print(f"{collection_name:<25} {total:<10} {with_type:<15} {collection_type}")
            
        except Exception as e:
            print(f"{collection_name:<25} Erreur: {e}")
    
    print("=" * 70)


if __name__ == '__main__':
    print("=" * 70)
    print("AJOUT DU CHAMP 'collection_type' DANS TOUTES LES COLLECTIONS")
    print("=" * 70)
    
    # 1. Ajouter le champ collection_type
    add_collection_type_field()
    
    # 2. Vérifier que tout s'est bien passé
    verify_collection_types()
    
    # 3. Afficher les statistiques
    show_stats()
    
    print("\n✅ Script terminé avec succès!")