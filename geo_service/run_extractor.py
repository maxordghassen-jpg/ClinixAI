"""
Script de démarrage interactif pour l'extraction
100% Text Search API - ADAPTÉ À LA STRUCTURE EXISTANTE
"""
import sys
from datetime import datetime

# Imports adaptés à ta structure
from config.settings import (
    PLACE_CATEGORIES,
    ALL_GOVERNORATES,
    EXTRACTION_CONFIG,
    get_category_display_name
)
from main import main


def print_banner():
    """Afficher la bannière"""
    print("\n" + "=" * 80)
    print("🏥 MEDICAL DATA EXTRACTOR - TUNISIA")
    print("=" * 80)
    print("Version: 2.0.0 (100% Text Search API)")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80 + "\n")


def estimate_cost(categories: list = None):
    """Estimer le coût de l'extraction"""
    if categories is None:
        categories = list(PLACE_CATEGORIES.keys())
    
    # Calculer le nombre de requêtes
    total_queries = 0
    for cat in categories:
        if cat in PLACE_CATEGORIES:
            total_queries += len(PLACE_CATEGORIES[cat]['queries'])
    
    # Nombre de gouvernorats
    gov_count = len(ALL_GOVERNORATES)
    
    # Requêtes de base
    base_requests = total_queries * gov_count
    
    # Avec pagination (moyenne 2 pages)
    with_pagination = base_requests * 2
    
    # Estimation d'établissements (pour details API)
    avg_places_per_query = 15
    estimated_places = total_queries * gov_count * avg_places_per_query
    
    # Total avec détails
    if EXTRACTION_CONFIG['fetch_place_details']:
        total_requests = with_pagination + estimated_places
    else:
        total_requests = with_pagination
    
    # Coût
    cost = total_requests * 0.032
    
    return {
        'categories': len(categories),
        'queries': total_queries,
        'governorates': gov_count,
        'base_requests': base_requests,
        'with_pagination': with_pagination,
        'estimated_places': estimated_places,
        'total_requests': total_requests,
        'cost': cost
    }


def show_menu():
    """Afficher le menu"""
    print("\n📋 OPTIONS D'EXTRACTION")
    print("=" * 80)
    print("\n1. 🚀 Extraction COMPLÈTE (toutes catégories)")
    print("2. 📁 Extraction SÉLECTIVE (choisir les catégories)")
    print("3. 💊 Pharmacies uniquement")
    print("4. 👨‍⚕️  Médecins uniquement")
    print("5. 🏥 Cliniques + Hôpitaux")
    print("6. 💰 Estimer les coûts")
    print("7. ⚙️  Modifier la configuration")
    print("8. ❌ Quitter")
    print("\n" + "=" * 80)


def show_categories():
    """Afficher les catégories disponibles"""
    print("\n📁 CATÉGORIES DISPONIBLES")
    print("=" * 80)
    
    for idx, (key, config) in enumerate(PLACE_CATEGORIES.items(), 1):
        queries_count = len(config['queries'])
        print(
            f"{idx:2}. {config['icon']} {get_category_display_name(key)}"
            f" ({queries_count} requêtes)"
        )
    
    print("=" * 80)


def select_categories():
    """Sélectionner les catégories à extraire"""
    show_categories()
    
    print("\n💡 Entrez les numéros des catégories (séparés par des virgules)")
    print("   Exemple : 1,2,5  ou  all  pour toutes")
    
    choice = input("\nVotre choix : ").strip()
    
    if choice.lower() == 'all':
        return list(PLACE_CATEGORIES.keys())
    
    try:
        indices = [int(x.strip()) for x in choice.split(',')]
        categories = list(PLACE_CATEGORIES.keys())
        
        selected = [categories[i-1] for i in indices if 1 <= i <= len(categories)]
        
        if not selected:
            print("❌ Aucune catégorie valide sélectionnée")
            return None
        
        print(f"\n✅ Catégories sélectionnées : {', '.join(selected)}")
        return selected
    
    except (ValueError, IndexError):
        print("❌ Format invalide")
        return None


def show_config():
    """Afficher la configuration actuelle"""
    print("\n⚙️  CONFIGURATION ACTUELLE")
    print("=" * 80)
    
    config = EXTRACTION_CONFIG
    
    print(f"\nDélais :")
    print(f"  • Entre recherches : {config['delay_between_searches']}s")
    print(f"  • Entre gouvernorats : {config['delay_between_governorates']}s")
    print(f"  • Entre catégories : {config['delay_between_categories']}s")
    
    print(f"\nPagination :")
    print(f"  • Activée : {'Oui' if config['enable_pagination'] else 'Non'}")
    print(f"  • Pages max : {config['max_pages_per_query']}")
    
    print(f"\nDétails :")
    print(f"  • Récupérer détails : {'Oui' if config['fetch_place_details'] else 'Non'}")
    
    print("=" * 80)


def modify_config():
    """Modifier la configuration"""
    print("\n⚙️  MODIFIER LA CONFIGURATION")
    print("=" * 80)
    
    print("\n1. Désactiver pagination (économiser API calls)")
    print("2. Désactiver Place Details (économiser API calls)")
    print("3. Augmenter les délais (éviter rate limiting)")
    print("4. Mode rapide (délais minimums)")
    print("5. Retour")
    
    choice = input("\nVotre choix : ").strip()
    
    if choice == '1':
        EXTRACTION_CONFIG['enable_pagination'] = False
        print("✅ Pagination désactivée (1 page = 20 résultats max)")
    
    elif choice == '2':
        EXTRACTION_CONFIG['fetch_place_details'] = False
        print("✅ Place Details désactivés (moins d'infos, moins cher)")
    
    elif choice == '3':
        EXTRACTION_CONFIG['delay_between_searches'] = 1.0
        EXTRACTION_CONFIG['delay_between_governorates'] = 2.0
        print("✅ Délais augmentés (plus sûr)")
    
    elif choice == '4':
        EXTRACTION_CONFIG['delay_between_searches'] = 0.2
        EXTRACTION_CONFIG['delay_between_governorates'] = 0.5
        print("✅ Mode rapide activé (risque de rate limiting)")
    
    show_config()


def confirm_extraction(estimation: dict):
    """Confirmer l'extraction"""
    print("\n💰 ESTIMATION")
    print("=" * 80)
    print(f"Catégories : {estimation['categories']}")
    print(f"Requêtes uniques : {estimation['queries']}")
    print(f"Gouvernorats : {estimation['governorates']}")
    print(f"\nRequêtes API estimées : {estimation['total_requests']:,}")
    print(f"Coût estimé : ${estimation['cost']:.2f}")
    print("=" * 80)
    
    response = input("\n⚠️  Confirmer l'extraction ? (oui/non) : ").strip().lower()
    
    return response in ['oui', 'o', 'yes', 'y']


def run():
    """Fonction principale"""
    print_banner()
    
    while True:
        show_menu()
        choice = input("\nVotre choix : ").strip()
        
        # Option 1 : Extraction complète
        if choice == '1':
            estimation = estimate_cost()
            
            if confirm_extraction(estimation):
                print("\n🚀 Démarrage de l'extraction complète...\n")
                main()
                break
            else:
                print("\n❌ Extraction annulée")
        
        # Option 2 : Extraction sélective
        elif choice == '2':
            categories = select_categories()
            
            if categories:
                estimation = estimate_cost(categories)
                
                if confirm_extraction(estimation):
                    print("\n🚀 Démarrage de l'extraction sélective...\n")
                    main(categories=categories)
                    break
                else:
                    print("\n❌ Extraction annulée")
        
        # Option 3 : Pharmacies uniquement
        elif choice == '3':
            cats = ['pharmacies', 'on_call_pharmacies', 'night_pharmacies', 'parapharmacies']
            estimation = estimate_cost(cats)
            
            if confirm_extraction(estimation):
                print("\n🚀 Extraction des pharmacies...\n")
                main(categories=cats)
                break
        
        # Option 4 : Médecins uniquement
        elif choice == '4':
            estimation = estimate_cost(['doctors'])
            
            if confirm_extraction(estimation):
                print("\n🚀 Extraction des médecins...\n")
                main(categories=['doctors'])
                break
        
        # Option 5 : Cliniques + Hôpitaux
        elif choice == '5':
            cats = ['clinics', 'hospitals']
            estimation = estimate_cost(cats)
            
            if confirm_extraction(estimation):
                print("\n🚀 Extraction cliniques/hôpitaux...\n")
                main(categories=cats)
                break
        
        # Option 6 : Estimer les coûts
        elif choice == '6':
            print("\n1. Toutes les catégories")
            print("2. Catégories personnalisées")
            
            sub_choice = input("\nVotre choix : ").strip()
            
            if sub_choice == '1':
                estimation = estimate_cost()
            elif sub_choice == '2':
                categories = select_categories()
                if categories:
                    estimation = estimate_cost(categories)
                else:
                    continue
            else:
                continue
            
            print("\n💰 ESTIMATION DÉTAILLÉE")
            print("=" * 80)
            print(f"Catégories : {estimation['categories']}")
            print(f"Requêtes : {estimation['queries']}")
            print(f"Gouvernorats : {estimation['governorates']}")
            print(f"\nRequêtes de base : {estimation['base_requests']:,}")
            print(f"Avec pagination : {estimation['with_pagination']:,}")
            print(f"Établissements estimés : {estimation['estimated_places']:,}")
            print(f"\nTotal requêtes : {estimation['total_requests']:,}")
            print(f"Coût total : ${estimation['cost']:.2f}")
            print("=" * 80)
            
            input("\nAppuyez sur Entrée pour continuer...")
        
        # Option 7 : Modifier config
        elif choice == '7':
            show_config()
            modify_config()
        
        # Option 8 : Quitter
        elif choice == '8':
            print("\n👋 Au revoir !\n")
            sys.exit(0)
        
        else:
            print("\n❌ Choix invalide\n")


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("\n\n⚠️  Interruption par l'utilisateur")
        print("👋 Au revoir !\n")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Erreur : {e}")
        sys.exit(1)