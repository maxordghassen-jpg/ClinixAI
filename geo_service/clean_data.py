"""
Clean old data before starting fresh extraction
Nettoie les anciennes données avant une nouvelle extraction
"""
import os
import shutil
from pymongo import MongoClient
from config.settings import DATA_DIR, MONGODB_URI, DATABASE_NAME, PLACE_CATEGORIES
from utils.logger import get_logger

logger = get_logger(__name__)


def clean_json_files():
    """
    Delete all JSON files in data directory
    """
    print("\n" + "=" * 60)
    print("NETTOYAGE DES FICHIERS JSON")
    print("=" * 60)
    
    if not os.path.exists(DATA_DIR):
        print(f"✓ Dossier '{DATA_DIR}' n'existe pas encore")
        return
    
    json_files = [f for f in os.listdir(DATA_DIR) if f.endswith('.json')]
    
    if not json_files:
        print("✓ Aucun fichier JSON à supprimer")
        return
    
    print(f"\nFichiers JSON trouvés : {len(json_files)}")
    
    for filename in json_files:
        filepath = os.path.join(DATA_DIR, filename)
        try:
            os.remove(filepath)
            print(f"  ✓ Supprimé : {filename}")
        except Exception as e:
            print(f"  ✗ Erreur lors de la suppression de {filename}: {e}")
    
    print(f"\n✅ {len(json_files)} fichier(s) JSON supprimé(s)")


def clean_mongodb_collections():
    """
    Drop all collections in MongoDB
    """
    print("\n" + "=" * 60)
    print("NETTOYAGE DES COLLECTIONS MONGODB")
    print("=" * 60)
    
    try:
        client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
        db = client[DATABASE_NAME]
        
        print(f"\nConnecté à la base de données : {DATABASE_NAME}")
        
        # Get existing collections
        existing_collections = db.list_collection_names()
        
        if not existing_collections:
            print("✓ Aucune collection à supprimer")
            client.close()
            return
        
        print(f"\nCollections trouvées : {len(existing_collections)}")
        
        # Drop each collection related to our categories
        dropped = 0
        for category_key, category_config in PLACE_CATEGORIES.items():
            collection_name = category_config['collection']
            
            if collection_name in existing_collections:
                # Get document count before dropping
                count = db[collection_name].count_documents({})
                
                # Drop collection
                db[collection_name].drop()
                print(f"  ✓ Collection '{collection_name}' supprimée ({count} documents)")
                dropped += 1
        
        # Also check for any other collections that might exist
        remaining = db.list_collection_names()
        for coll in remaining:
            if coll not in ['system.indexes']:  # Don't drop system collections
                count = db[coll].count_documents({})
                db[coll].drop()
                print(f"  ✓ Collection '{coll}' supprimée ({count} documents)")
                dropped += 1
        
        client.close()
        print(f"\n✅ {dropped} collection(s) supprimée(s)")
        
    except Exception as e:
        print(f"\n❌ Erreur lors du nettoyage MongoDB: {e}")
        print("Vérifiez votre connexion MongoDB")


def clean_logs():
    """
    Archive old logs
    """
    print("\n" + "=" * 60)
    print("ARCHIVAGE DES LOGS")
    print("=" * 60)
    
    from config.settings import LOG_DIR, LOG_FILE
    
    if not os.path.exists(LOG_DIR):
        print(f"✓ Dossier '{LOG_DIR}' n'existe pas encore")
        return
    
    log_path = os.path.join(LOG_DIR, LOG_FILE)
    
    if os.path.exists(log_path):
        # Create archive folder
        archive_dir = os.path.join(LOG_DIR, 'archive')
        os.makedirs(archive_dir, exist_ok=True)
        
        # Move current log to archive with timestamp
        from datetime import datetime
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        archive_path = os.path.join(archive_dir, f'medical_extractor_{timestamp}.log')
        
        try:
            shutil.move(log_path, archive_path)
            print(f"✓ Log archivé : {archive_path}")
        except Exception as e:
            print(f"✗ Erreur lors de l'archivage : {e}")
    else:
        print("✓ Aucun log à archiver")


def main():
    """
    Main cleaning function
    """
    print("=" * 60)
    print("NETTOYAGE COMPLET DES DONNÉES")
    print("=" * 60)
    print("\nCe script va supprimer :")
    print("  • Tous les fichiers JSON dans le dossier 'data/'")
    print("  • Toutes les collections MongoDB")
    print("  • Archiver les logs actuels")
    print("\n" + "=" * 60)
    
    # Ask for confirmation
    response = input("\n⚠️  Êtes-vous sûr de vouloir continuer ? (oui/non) : ").strip().lower()
    
    if response not in ['oui', 'yes', 'o', 'y']:
        print("\n❌ Nettoyage annulé")
        return
    
    print("\n🔄 Démarrage du nettoyage...\n")
    
    # Clean JSON files
    clean_json_files()
    
    # Clean MongoDB collections
    clean_mongodb_collections()
    
    # Archive logs
    clean_logs()
    
    print("\n" + "=" * 60)
    print("✅ NETTOYAGE TERMINÉ")
    print("=" * 60)
    print("\nVous pouvez maintenant lancer l'extraction :")
    print("  python scheduler.py")
    print("\nOu pour une extraction manuelle :")
    print("  python main.py")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()