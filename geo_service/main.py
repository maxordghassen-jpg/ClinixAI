"""
Main Script - Medical Data Extractor
Version 100% Text Search API pour toutes les catégories
"""
import os
import json
import time
from datetime import datetime
from typing import Dict, List
from config.settings import (
    PLACE_CATEGORIES,
    ALL_GOVERNORATES,
    DATA_DIR,
    CHECKPOINT_DIR,
    EXTRACTION_CONFIG,
    get_category_display_name
)
from services.google_places_service import GooglePlacesTextSearchService
from services.mongodb_service import MongoDBService
from utils.logger import get_logger

logger = get_logger(__name__)


class MedicalDataExtractor:
    """
    Extracteur de données médicales - 100% Text Search API
    """
    
    def __init__(self):
        self.places_service = GooglePlacesTextSearchService()
        self.mongodb_service = MongoDBService()
        
        # Créer les dossiers nécessaires
        for directory in [DATA_DIR, CHECKPOINT_DIR]:
            os.makedirs(directory, exist_ok=True)
        
        # Statistiques globales
        self.stats = {
            'start_time': None,
            'end_time': None,
            'duration': None,
            'categories': {},
            'total_api_calls': 0,
            'total_places': 0,
            'governorates_covered': set()
        }
    
    def extract_category(
        self,
        category_key: str,
        category_config: Dict
    ) -> List[Dict]:
        """
        Extraire toutes les données pour une catégorie
        """
        logger.info("=" * 70)
        logger.info(
            f"📁 CATÉGORIE: {get_category_display_name(category_key)} "
            f"{category_config['icon']}"
        )
        logger.info("=" * 70)
        
        # Statistiques pour cette catégorie
        cat_stats = {
            'start_time': datetime.now(),
            'queries_count': len(category_config['queries']),
            'governorates_processed': 0,
            'places_found': 0,
            'duplicates_removed': 0,
            'errors': 0,
            'api_calls_start': self.places_service.get_request_count()
        }
        
        # Afficher les requêtes
        logger.info(f"\n🔍 Requêtes ({cat_stats['queries_count']}):")
        for query in category_config['queries']:
            logger.info(f"   • {query}")
        
        logger.info(f"\n📍 Extraction dans {len(ALL_GOVERNORATES)} gouvernorats...")
        logger.info("")
        
        # Rechercher dans tous les gouvernorats
        all_places = self.places_service.search_all_governorates(
            queries=category_config['queries'],
            governorates=ALL_GOVERNORATES,
            extract_specialty=category_config.get('extract_specialty', False),
            fetch_details=EXTRACTION_CONFIG['fetch_place_details']
        )
        
        # Mise à jour des statistiques
        cat_stats['places_found'] = len(all_places)
        cat_stats['governorates_processed'] = len(ALL_GOVERNORATES)
        cat_stats['api_calls_end'] = self.places_service.get_request_count()
        cat_stats['api_calls_used'] = (
            cat_stats['api_calls_end'] - cat_stats['api_calls_start']
        )
        cat_stats['end_time'] = datetime.now()
        cat_stats['duration'] = (
            cat_stats['end_time'] - cat_stats['start_time']
        )
        
        # Gouvernorats couverts
        governorates_found = set(
            place.get('governorate') for place in all_places
            if place.get('governorate')
        )
        cat_stats['governorates_found'] = list(governorates_found)
        cat_stats['coverage'] = len(governorates_found)
        
        # Statistiques spéciales pour les médecins
        if category_key == 'doctors':
            specialty_stats = self._analyze_doctor_specialties(all_places)
            cat_stats['specialties'] = specialty_stats
        
        # Sauvegarder les statistiques
        self.stats['categories'][category_key] = cat_stats
        self.stats['governorates_covered'].update(governorates_found)
        
        # Afficher le résumé
        self._print_category_summary(category_key, cat_stats)
        
        return all_places
    
    def _analyze_doctor_specialties(self, doctors: List[Dict]) -> Dict:
        """
        Analyser les spécialités médicales
        """
        specialty_count = {}
        without_specialty = 0
        
        for doctor in doctors:
            specialty = doctor.get('specialty')
            if specialty:
                specialty_count[specialty] = specialty_count.get(specialty, 0) + 1
            else:
                without_specialty += 1
        
        total = len(doctors)
        with_specialty = sum(specialty_count.values())
        coverage = (with_specialty / total * 100) if total > 0 else 0
        
        return {
            'total_doctors': total,
            'with_specialty': with_specialty,
            'without_specialty': without_specialty,
            'coverage_percent': round(coverage, 1),
            'by_specialty': specialty_count
        }
    
    def _print_category_summary(self, category_key: str, stats: Dict):
        """
        Afficher le résumé d'une catégorie
        """
        logger.info("\n" + "=" * 70)
        logger.info("📊 RÉSUMÉ")
        logger.info("=" * 70)
        logger.info(f"Établissements trouvés: {stats['places_found']}")
        logger.info(f"Gouvernorats couverts: {stats['coverage']}/24")
        logger.info(f"Requêtes API: {stats['api_calls_used']}")
        logger.info(f"Durée: {stats['duration']}")
        
        # Statistiques spécialités (pour médecins)
        if 'specialties' in stats:
            spec_stats = stats['specialties']
            logger.info(f"\n🎯 Spécialités médicales:")
            logger.info(
                f"   • Avec spécialité: {spec_stats['with_specialty']} "
                f"({spec_stats['coverage_percent']}%)"
            )
            logger.info(f"   • Sans spécialité: {spec_stats['without_specialty']}")
            
            if spec_stats['by_specialty']:
                logger.info(f"\n   Top 10 spécialités:")
                sorted_specs = sorted(
                    spec_stats['by_specialty'].items(),
                    key=lambda x: x[1],
                    reverse=True
                )
                for specialty, count in sorted_specs[:10]:
                    logger.info(f"      - {specialty}: {count}")
        
        logger.info("=" * 70 + "\n")
    
    def save_to_json(self, data: List[Dict], filename: str):
        """
        Sauvegarder en JSON
        """
        filepath = os.path.join(DATA_DIR, filename)
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            file_size = os.path.getsize(filepath) / (1024 * 1024)  # MB
            logger.info(f"💾 JSON sauvegardé: {filename} ({file_size:.2f} MB)")
        
        except Exception as e:
            logger.error(f"❌ Erreur sauvegarde JSON {filename}: {e}")
    
    def save_to_mongodb(self, data: List[Dict], collection_name: str):
        """
        Sauvegarder dans MongoDB
        """
        try:
            # Ajouter timestamp
            for item in data:
                item['last_updated'] = datetime.now().isoformat()
            
            # Insérer dans MongoDB
            count = self.mongodb_service.insert_places(collection_name, data)
            
            # Créer les index
            self.mongodb_service.create_indexes(collection_name)
            
            logger.info(
                f"💾 MongoDB sauvegardé: {collection_name} ({count} documents)"
            )
        
        except Exception as e:
            logger.error(f"❌ Erreur MongoDB {collection_name}: {e}")
    
    def save_checkpoint(self, category_key: str, data: List[Dict], stats: Dict):
        """
        Sauvegarder un checkpoint
        """
        checkpoint_file = os.path.join(
            CHECKPOINT_DIR,
            f'{category_key}_checkpoint.json'
        )
        
        checkpoint_data = {
            'category': category_key,
            'timestamp': datetime.now().isoformat(),
            'places_count': len(data),
            'stats': {
                'api_calls': stats.get('api_calls_used', 0),
                'governorates': stats.get('coverage', 0),
                'duration': str(stats.get('duration', 'N/A'))
            }
        }
        
        try:
            with open(checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(checkpoint_data, f, ensure_ascii=False, indent=2)
            logger.debug(f"   💾 Checkpoint sauvegardé: {category_key}")
        except Exception as e:
            logger.error(f"   ❌ Erreur checkpoint: {e}")
    
    def generate_final_report(self):
        """
        Générer le rapport final
        """
        logger.info("\n" + "=" * 80)
        logger.info("📊 RAPPORT FINAL DE L'EXTRACTION")
        logger.info("=" * 80)
        
        # Durée totale
        duration = self.stats['end_time'] - self.stats['start_time']
        logger.info(f"\n⏱️  Durée totale: {duration}")
        logger.info(
            f"   • Début: {self.stats['start_time'].strftime('%Y-%m-%d %H:%M:%S')}"
        )
        logger.info(
            f"   • Fin: {self.stats['end_time'].strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        # Résultats par catégorie
        logger.info(f"\n📁 Résultats par catégorie:")
        total_places = 0
        
        for cat_key, cat_stats in self.stats['categories'].items():
            places_count = cat_stats['places_found']
            api_calls = cat_stats.get('api_calls_used', 0)
            coverage = cat_stats.get('coverage', 0)
            
            total_places += places_count
            
            logger.info(
                f"\n   {get_category_display_name(cat_key)}:"
            )
            logger.info(f"      • Établissements: {places_count}")
            logger.info(f"      • Gouvernorats: {coverage}/24")
            logger.info(f"      • Requêtes API: {api_calls}")
            logger.info(f"      • Durée: {cat_stats.get('duration', 'N/A')}")
        
        # Totaux
        logger.info(f"\n📊 TOTAUX:")
        logger.info(f"   • Établissements: {total_places}")
        logger.info(f"   • Gouvernorats couverts: {len(self.stats['governorates_covered'])}/24")
        logger.info(f"   • Requêtes API: {self.stats['total_api_calls']}")
        logger.info(f"   • Coût estimé: ${self.stats['total_api_calls'] * 0.032:.2f}")
        
        # Couverture géographique
        coverage_percent = (
            len(self.stats['governorates_covered']) / 24 * 100
        )
        logger.info(f"\n🗺️  Couverture géographique: {coverage_percent:.1f}%")
        
        if coverage_percent < 100:
            missing = set(ALL_GOVERNORATES) - self.stats['governorates_covered']
            logger.warning(f"   ⚠️  Gouvernorats manquants: {', '.join(missing)}")
        else:
            logger.info("   ✅ Couverture complète de la Tunisie!")
        
        logger.info("\n" + "=" * 80)
    
    def run_extraction(self, categories: List[str] = None):
        """
        Lancer l'extraction complète
        
        Args:
            categories: Liste des catégories à extraire (None = toutes)
        """
        self.stats['start_time'] = datetime.now()
        
        logger.info("\n" + "=" * 80)
        logger.info("🚀 EXTRACTION MÉDICALE - TUNISIE")
        logger.info("=" * 80)
        logger.info("Mode: 100% Text Search API")
        logger.info(f"Début: {self.stats['start_time'].strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"Gouvernorats: {len(ALL_GOVERNORATES)}")
        
        # Déterminer les catégories à extraire
        if categories:
            cats_to_extract = {
                k: v for k, v in PLACE_CATEGORIES.items() if k in categories
            }
        else:
            cats_to_extract = PLACE_CATEGORIES
        
        logger.info(f"Catégories: {len(cats_to_extract)}")
        logger.info("=" * 80 + "\n")
        
        # Extraire chaque catégorie
        for idx, (category_key, category_config) in enumerate(cats_to_extract.items(), 1):
            logger.info(f"\n{'#' * 80}")
            logger.info(f"CATÉGORIE {idx}/{len(cats_to_extract)}")
            logger.info(f"{'#' * 80}\n")
            
            try:
                # Extraction
                places = self.extract_category(category_key, category_config)
                
                if places:
                    # Sauvegarder JSON
                    self.save_to_json(places, category_config['filename'])
                    
                    # Sauvegarder MongoDB
                    self.save_to_mongodb(places, category_config['collection'])
                    
                    # Checkpoint
                    self.save_checkpoint(
                        category_key,
                        places,
                        self.stats['categories'][category_key]
                    )
                else:
                    logger.warning(f"⚠️  Aucun résultat pour {category_key}")
            
            except Exception as e:
                logger.error(f"❌ Erreur critique pour {category_key}: {e}", exc_info=True)
                self.stats['categories'][category_key] = {
                    'error': str(e),
                    'places_found': 0
                }
            
            # Délai entre catégories
            if idx < len(cats_to_extract):
                delay = EXTRACTION_CONFIG['delay_between_categories']
                logger.info(f"\n⏸️  Pause de {delay}s avant la prochaine catégorie...\n")
                time.sleep(delay)
        
        # Finalisation
        self.stats['end_time'] = datetime.now()
        self.stats['duration'] = self.stats['end_time'] - self.stats['start_time']
        self.stats['total_api_calls'] = self.places_service.get_request_count()
        self.stats['total_places'] = sum(
            cat.get('places_found', 0)
            for cat in self.stats['categories'].values()
        )
        
        # Rapport final
        self.generate_final_report()
        
        # Fermer MongoDB
        self.mongodb_service.close()
        
        logger.info("\n✅ Extraction terminée!\n")


def main(categories: List[str] = None):
    """
    Point d'entrée principal
    
    Args:
        categories: Liste des catégories à extraire (None = toutes)
    """
    try:
        extractor = MedicalDataExtractor()
        extractor.run_extraction(categories=categories)
    except KeyboardInterrupt:
        logger.warning("\n⚠️  Extraction interrompue par l'utilisateur")
    except Exception as e:
        logger.error(f"\n❌ Erreur fatale: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    # Lancer l'extraction complète
    main()
    
    # Pour extraire seulement certaines catégories:
    # main(categories=['pharmacies', 'doctors'])