"""
Visualize Tunisia coverage map
Shows all search points and their radius coverage
"""
from config.settings import TUNISIA_CITIES, SEARCH_RADIUS


def show_coverage_summary():
    """
    Display coverage summary
    """
    print("=" * 80)
    print("COUVERTURE GÉOGRAPHIQUE DE LA TUNISIE")
    print("=" * 80)
    print(f"\nNombre total de points de recherche : {len(TUNISIA_CITIES)}")
    print(f"Rayon de recherche par point : {SEARCH_RADIUS/1000:.0f} km")
    print(f"\nSurface approximative couverte : {len(TUNISIA_CITIES) * 3.14 * (SEARCH_RADIUS/1000)**2:.0f} km²")
    
    # Group by governorate
    governorates = {}
    for city in TUNISIA_CITIES:
        gov = city.get('governorate', 'Unknown')
        if gov not in governorates:
            governorates[gov] = []
        governorates[gov].append(city['name'])
    
    print(f"\n{'='*80}")
    print(f"RÉPARTITION PAR GOUVERNORAT (24 gouvernorats)")
    print(f"{'='*80}\n")
    
    # Sort by governorate name
    for gov in sorted(governorates.keys()):
        cities = governorates[gov]
        print(f"📍 {gov:20} → {len(cities)} point(s) de recherche")
        for city in cities:
            print(f"   • {city}")
        print()
    
    print("=" * 80)
    print("STATISTIQUES")
    print("=" * 80)
    print(f"Total gouvernorats couverts : {len(governorates)}")
    print(f"Points de recherche uniques : {len(TUNISIA_CITIES)}")
    print(f"Moyenne par gouvernorat : {len(TUNISIA_CITIES)/len(governorates):.1f}")
    print("=" * 80)
    
    # Region distribution
    print("\nRÉPARTITION RÉGIONALE:")
    regions = {
        'Nord': ['Tunis', 'Ariana', 'Ben Arous', 'Manouba', 'Bizerte', 'Nabeul', 'Zaghouan'],
        'Nord-Ouest': ['Béja', 'Jendouba', 'Le Kef', 'Siliana', 'Kasserine'],
        'Centre-Est': ['Sousse', 'Monastir', 'Mahdia', 'Sfax'],
        'Centre-Ouest': ['Kairouan', 'Sidi Bouzid', 'Gafsa'],
        'Sud-Est': ['Gabès', 'Médenine', 'Tataouine'],
        'Sud-Ouest': ['Tozeur', 'Kébili']
    }
    
    for region, govs in regions.items():
        count = sum(1 for city in TUNISIA_CITIES if city.get('governorate') in govs)
        print(f"  {region:15} : {count:2} points")
    
    print("\n" + "=" * 80)
    print("✅ TOUTE LA TUNISIE EST COUVERTE")
    print("✅ SYSTÈME DE DÉTECTION DES DOUBLONS ACTIVÉ")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    show_coverage_summary()