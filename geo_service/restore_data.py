"""
Script de Restauration des Données JSON vers MongoDB
Réinsère tous les fichiers JSON trouvés dans le dossier data/
"""
import os
import json
from datetime import datetime
from services.mongodb_service import MongoDBService
from utils.logger import get_logger

logger = get_logger(__name__)


# Mapping fichiers JSON → collections MongoDB
JSON_TO_COLLECTION = {
    'pharmacies.json': 'pharmacies',
    'on_call_pharmacies.json': 'on_call_pharmacies',
    'night_pharmacies.json': 'night_pharmacies',
    'parapharmacies.json': 'parapharmacies',
    'clinics.json': 'clinics',
    'analysis_labs.json': 'analysis_labs',
    'nurses.json': 'nurses',
    'physiotherapists.json': 'physiotherapists',
    'doctors.json': 'doctors',
    'hospitals.json': 'hospitals'
}


def restore_from_json():
    """
    Restaurer toutes les données depuis les fichiers JSON
    """
    print("=" * 70)
    print("🔄 RESTAURATION DES DONNÉES VERS MONGODB")
    print("=" * 70)
    
    # Connexion MongoDB
    try:
        service = MongoDBService()
        print(f"✅ Connecté à MongoDB: {service.db.name}\n")
    except Exception as e:
        print(f"❌ Erreur de connexion MongoDB: {e}")
        return
    
    # Statistiques
    stats = {
        'files_found': 0,
        'files_restored': 0,
        'total_documents': 0,
        'errors': []
    }
    
    # Parcourir les fichiers JSON
    data_dir = 'data'
    
    if not os.path.exists(data_dir):
        print(f"❌ Le dossier '{data_dir}/' n'existe pas")
        return
    
    json_files = [f for f in os.listdir(data_dir) if f.endswith('.json')]
    
    if not json_files:
        print(f"❌ Aucun fichier JSON trouvé dans '{data_dir}/'")
        return
    
    print(f"📁 Fichiers JSON trouvés: {len(json_files)}\n")
    stats['files_found'] = len(json_files)
    
    # Restaurer chaque fichier
    for json_file in sorted(json_files):
        filepath = os.path.join(data_dir, json_file)
        
        # Ignorer les fichiers qui ne sont pas des données
        if json_file in ['extraction_history.json', 'analysis_summary.json']:
            print(f"⏭️  Ignoré: {json_file} (fichier système)")
            continue
        
        # Trouver la collection correspondante
        collection_name = JSON_TO_COLLECTION.get(json_file)
        
        if not collection_name:
            # Essayer de deviner le nom de collection
            collection_name = json_file.replace('.json', '')
            print(f"⚠️  {json_file} → Collection: {collection_name} (devinée)")
        
        try:
            # Charger le JSON
            print(f"📄 Traitement: {json_file}")
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if not isinstance(data, list):
                print(f"   ❌ Format invalide (doit être une liste)")
                stats['errors'].append(f"{json_file}: Format invalide")
                continue
            
            if len(data) == 0:
                print(f"   ⚠️  Fichier vide (0 documents)")
                continue
            
            print(f"   📊 Documents à insérer: {len(data)}")
            
            # Ajouter timestamp de restauration
            for item in data:
                item['restored_at'] = datetime.now().isoformat()
                item['restored_from'] = json_file
            
            # Nettoyer la collection existante
            collection = service.db[collection_name]
            existing_count = collection.count_documents({})
            
            if existing_count > 0:
                response = input(f"   ⚠️  La collection '{collection_name}' contient déjà {existing_count} documents. Remplacer ? (o/n): ")
                if response.lower() != 'o':
                    print(f"   ⏭️  Ignoré")
                    continue
                
                collection.delete_many({})
                print(f"   🗑️  {existing_count} anciens documents supprimés")
            
            # Insérer les données
            result = collection.insert_many(data)
            inserted_count = len(result.inserted_ids)
            
            # Créer les index
            service.create_indexes(collection_name)
            
            print(f"   ✅ Inséré: {inserted_count} documents")
            print(f"   🔍 Index créés\n")
            
            stats['files_restored'] += 1
            stats['total_documents'] += inserted_count
            
        except json.JSONDecodeError as e:
            error_msg = f"{json_file}: Erreur JSON - {e}"
            print(f"   ❌ {error_msg}")
            stats['errors'].append(error_msg)
        
        except Exception as e:
            error_msg = f"{json_file}: {e}"
            print(f"   ❌ Erreur: {e}")
            stats['errors'].append(error_msg)
    
    # Résumé final
    print("\n" + "=" * 70)
    print("📊 RÉSUMÉ DE LA RESTAURATION")
    print("=" * 70)
    print(f"Fichiers trouvés:    {stats['files_found']}")
    print(f"Fichiers restaurés:  {stats['files_restored']}")
    print(f"Documents insérés:   {stats['total_documents']}")
    print(f"Erreurs:             {len(stats['errors'])}")
    
    if stats['errors']:
        print("\n❌ Erreurs rencontrées:")
        for error in stats['errors']:
            print(f"   • {error}")
    
    # Vérification finale
    print("\n" + "=" * 70)
    print("🔍 VÉRIFICATION DES COLLECTIONS")
    print("=" * 70)
    
    for collection_name in service.db.list_collection_names():
        count = service.db[collection_name].count_documents({})
        print(f"   • {collection_name}: {count} documents")
    
    print("\n✅ Restauration terminée !\n")
    
    # Fermer la connexion
    service.close()


def restore_specific_file(json_file: str, collection_name: str = None):
    """
    Restaurer un fichier JSON spécifique
    
    Args:
        json_file: Nom du fichier (ex: 'pharmacies.json')
        collection_name: Nom de la collection (optionnel, déduit du fichier)
    """
    if not collection_name:
        collection_name = JSON_TO_COLLECTION.get(json_file, json_file.replace('.json', ''))
    
    filepath = os.path.join('data', json_file)
    
    if not os.path.exists(filepath):
        print(f"❌ Fichier non trouvé: {filepath}")
        return
    
    try:
        service = MongoDBService()
        
        # Charger le JSON
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        print(f"📄 Fichier: {json_file}")
        print(f"📊 Documents: {len(data)}")
        print(f"🗄️  Collection: {collection_name}")
        
        # Confirmer
        response = input(f"\n⚠️  Insérer dans '{collection_name}' ? (o/n): ")
        if response.lower() != 'o':
            print("❌ Annulé")
            return
        
        # Ajouter timestamp
        for item in data:
            item['restored_at'] = datetime.now().isoformat()
        
        # Insérer
        collection = service.db[collection_name]
        collection.delete_many({})  # Nettoyer d'abord
        result = collection.insert_many(data)
        
        # Créer index
        service.create_indexes(collection_name)
        
        print(f"✅ Inséré: {len(result.inserted_ids)} documents")
        
        service.close()
        
    except Exception as e:
        print(f"❌ Erreur: {e}")


def show_menu():
    """Afficher le menu interactif"""
    print("\n" + "=" * 70)
    print("🔄 RESTAURATION MONGODB")
    print("=" * 70)
    print("\n1. 🚀 Restaurer TOUS les fichiers JSON")
    print("2. 📁 Restaurer UN fichier spécifique")
    print("3. 🔍 Voir les fichiers JSON disponibles")
    print("4. 📊 Voir l'état actuel de MongoDB")
    print("5. ❌ Quitter")
    print("\n" + "=" * 70)


def list_json_files():
    """Lister les fichiers JSON disponibles"""
    data_dir = 'data'
    
    if not os.path.exists(data_dir):
        print(f"❌ Le dossier '{data_dir}/' n'existe pas")
        return []
    
    json_files = [f for f in os.listdir(data_dir) if f.endswith('.json')]
    
    print("\n📁 Fichiers JSON disponibles:")
    print("=" * 70)
    
    for i, json_file in enumerate(sorted(json_files), 1):
        filepath = os.path.join(data_dir, json_file)
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                count = len(data) if isinstance(data, list) else "?"
        except:
            count = "Erreur"
        
        collection = JSON_TO_COLLECTION.get(json_file, "?")
        print(f"{i:2}. {json_file:30} → {collection:25} ({count} docs)")
    
    print("=" * 70)
    
    return json_files


def show_mongodb_status():
    """Afficher l'état actuel de MongoDB"""
    try:
        service = MongoDBService()
        
        print("\n📊 État actuel de MongoDB:")
        print("=" * 70)
        print(f"Base de données: {service.db.name}")
        print(f"Collections: {len(service.db.list_collection_names())}\n")
        
        for collection_name in sorted(service.db.list_collection_names()):
            count = service.db[collection_name].count_documents({})
            print(f"   • {collection_name:30} {count:6} documents")
        
        print("=" * 70)
        
        service.close()
        
    except Exception as e:
        print(f"❌ Erreur: {e}")


def interactive_mode():
    """Mode interactif"""
    while True:
        show_menu()
        choice = input("\nVotre choix : ").strip()
        
        if choice == '1':
            print("\n⚠️  Restaurer TOUS les fichiers JSON vers MongoDB")
            confirm = input("Confirmer ? (oui/non) : ")
            if confirm.lower() == 'oui':
                restore_from_json()
        
        elif choice == '2':
            json_files = list_json_files()
            if json_files:
                file_num = input("\nNuméro du fichier à restaurer : ").strip()
                try:
                    idx = int(file_num) - 1
                    if 0 <= idx < len(json_files):
                        json_file = sorted(json_files)[idx]
                        restore_specific_file(json_file)
                    else:
                        print("❌ Numéro invalide")
                except ValueError:
                    print("❌ Entrez un numéro valide")
        
        elif choice == '3':
            list_json_files()
            input("\nAppuyez sur Entrée pour continuer...")
        
        elif choice == '4':
            show_mongodb_status()
            input("\nAppuyez sur Entrée pour continuer...")
        
        elif choice == '5':
            print("\n👋 Au revoir !\n")
            break
        
        else:
            print("❌ Choix invalide")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # Mode ligne de commande
        if sys.argv[1] == '--all':
            restore_from_json()
        elif sys.argv[1] == '--file' and len(sys.argv) > 2:
            restore_specific_file(sys.argv[2])
        else:
            print("Usage:")
            print("  python restore_data.py              # Mode interactif")
            print("  python restore_data.py --all        # Restaurer tout")
            print("  python restore_data.py --file pharmacies.json  # Fichier spécifique")
    else:
        # Mode interactif
        interactive_mode()