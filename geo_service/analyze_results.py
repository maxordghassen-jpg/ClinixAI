"""
Script d'analyse des résultats d'extraction
Génère des statistiques détaillées et des graphiques
"""
import json
import os
from collections import Counter, defaultdict
from typing import Dict, List
from utils.logger import get_logger

logger = get_logger(__name__)


class ResultsAnalyzer:
    def __init__(self, data_dir='data'):
        self.data_dir = data_dir
        self.doctors_data = None
        self.all_data = {}
    
    def load_data(self):
        """Charger toutes les données"""
        logger.info("📂 Chargement des données...")
        
        data_files = {
            'doctors': 'doctors.json',
            'pharmacies': 'pharmacies.json',
            'clinics': 'clinics.json',
            'analysis_labs': 'analysis_labs.json',
            'nurses': 'nurses.json',
            'physiotherapists': 'physiotherapists.json'
        }
        
        for category, filename in data_files.items():
            filepath = os.path.join(self.data_dir, filename)
            if os.path.exists(filepath):
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        self.all_data[category] = json.load(f)
                    logger.info(f"  ✓ {category}: {len(self.all_data[category])} enregistrements")
                except Exception as e:
                    logger.error(f"  ✗ Erreur chargement {category}: {e}")
            else:
                logger.warning(f"  ⚠️  Fichier non trouvé: {filename}")
        
        self.doctors_data = self.all_data.get('doctors', [])
    
    def analyze_specialties(self):
        """Analyse détaillée des spécialités médicales"""
        if not self.doctors_data:
            logger.warning("⚠️  Aucune donnée de médecins à analyser")
            return
        
        logger.info("\n" + "="*70)
        logger.info("📊 ANALYSE DÉTAILLÉE DES SPÉCIALITÉS MÉDICALES")
        logger.info("="*70)
        
        # Compter par spécialité
        specialty_count = Counter()
        no_specialty = []
        
        for doctor in self.doctors_data:
            specialty = doctor.get('specialty')
            if specialty:
                specialty_count[specialty] += 1
            else:
                no_specialty.append(doctor)
        
        # Afficher top spécialités
        logger.info("\n🏆 TOP 15 Spécialités:")
        for idx, (specialty, count) in enumerate(specialty_count.most_common(15), 1):
            percentage = (count / len(self.doctors_data)) * 100
            logger.info(f"  {idx:2d}. {specialty:25s}: {count:4d} ({percentage:5.2f}%)")
        
        # Statistiques globales
        total = len(self.doctors_data)
        with_spec = sum(specialty_count.values())
        without_spec = len(no_specialty)
        coverage = (with_spec / total * 100) if total > 0 else 0
        
        logger.info(f"\n📈 Statistiques Globales:")
        logger.info(f"  • Total médecins: {total:,}")
        logger.info(f"  • Avec spécialité: {with_spec:,} ({coverage:.1f}%)")
        logger.info(f"  • Sans spécialité: {without_spec:,}")
        logger.info(f"  • Nombre de spécialités: {len(specialty_count)}")
        
        # Évaluation de la couverture
        if coverage >= 90:
            logger.info(f"\n✅ EXCELLENT: {coverage:.1f}% de couverture!")
        elif coverage >= 80:
            logger.info(f"\n✓ TRÈS BON: {coverage:.1f}% de couverture")
        elif coverage >= 70:
            logger.info(f"\n✓ BON: {coverage:.1f}% de couverture")
        else:
            logger.warning(f"\n⚠️  ATTENTION: Seulement {coverage:.1f}% de couverture")
        
        # Exemples sans spécialité
        if no_specialty:
            logger.info(f"\n❓ Exemples de médecins sans spécialité (10 premiers):")
            for doc in no_specialty[:10]:
                logger.info(f"  • {doc.get('name')} - {doc.get('search_city')}")
        
        return {
            'total': total,
            'with_specialty': with_spec,
            'without_specialty': without_spec,
            'coverage_percent': coverage,
            'specialty_breakdown': dict(specialty_count)
        }
    
    def analyze_by_governorate(self):
        """Analyse par gouvernorat"""
        if not self.doctors_data:
            return
        
        logger.info("\n" + "="*70)
        logger.info("🗺️  RÉPARTITION PAR GOUVERNORAT")
        logger.info("="*70)
        
        gov_count = Counter()
        gov_specialties = defaultdict(set)
        
        for doctor in self.doctors_data:
            gov = doctor.get('governorate', 'Unknown')
            gov_count[gov] += 1
            
            specialty = doctor.get('specialty')
            if specialty:
                gov_specialties[gov].add(specialty)
        
        logger.info("\n📍 Médecins par Gouvernorat:")
        for gov, count in sorted(gov_count.items(), key=lambda x: x[1], reverse=True):
            spec_count = len(gov_specialties[gov])
            logger.info(f"  • {gov:20s}: {count:4d} médecins, {spec_count:2d} spécialités")
        
        return dict(gov_count)
    
    def analyze_all_categories(self):
        """Analyse de toutes les catégories"""
        logger.info("\n" + "="*70)
        logger.info("📋 RÉSUMÉ PAR CATÉGORIE")
        logger.info("="*70)
        
        total_all = 0
        for category, data in self.all_data.items():
            count = len(data)
            total_all += count
            
            # Compter par gouvernorat
            gov_count = Counter(item.get('governorate', 'Unknown') for item in data)
            gov_covered = len([g for g in gov_count if g != 'Unknown'])
            
            logger.info(f"\n{category.upper()}:")
            logger.info(f"  • Total: {count:,}")
            logger.info(f"  • Gouvernorats: {gov_covered}/24")
            
            # Top 5 villes
            city_count = Counter(item.get('search_city', 'Unknown') for item in data)
            logger.info(f"  • Top 5 villes:")
            for city, c in city_count.most_common(5):
                logger.info(f"    - {city}: {c}")
        
        logger.info(f"\n{'='*70}")
        logger.info(f"TOTAL GÉNÉRAL: {total_all:,} établissements")
        logger.info(f"{'='*70}")
    
    def analyze_data_quality(self):
        """Analyse de la qualité des données"""
        if not self.doctors_data:
            return
        
        logger.info("\n" + "="*70)
        logger.info("🔍 QUALITÉ DES DONNÉES")
        logger.info("="*70)
        
        total = len(self.doctors_data)
        
        # Vérifier la complétude
        with_phone = sum(1 for d in self.doctors_data if d.get('phone_number'))
        with_address = sum(1 for d in self.doctors_data if d.get('address'))
        with_rating = sum(1 for d in self.doctors_data if d.get('rating'))
        with_website = sum(1 for d in self.doctors_data if d.get('website'))
        with_hours = sum(1 for d in self.doctors_data if d.get('opening_hours'))
        
        logger.info("\n📊 Complétude des Données:")
        logger.info(f"  • Avec téléphone: {with_phone:,} ({with_phone/total*100:.1f}%)")
        logger.info(f"  • Avec adresse: {with_address:,} ({with_address/total*100:.1f}%)")
        logger.info(f"  • Avec note: {with_rating:,} ({with_rating/total*100:.1f}%)")
        logger.info(f"  • Avec site web: {with_website:,} ({with_website/total*100:.1f}%)")
        logger.info(f"  • Avec horaires: {with_hours:,} ({with_hours/total*100:.1f}%)")
        
        # Statistiques sur les notes
        ratings = [d.get('rating') for d in self.doctors_data if d.get('rating')]
        if ratings:
            avg_rating = sum(ratings) / len(ratings)
            logger.info(f"\n⭐ Notes:")
            logger.info(f"  • Note moyenne: {avg_rating:.2f}/5")
            logger.info(f"  • Note min: {min(ratings)}")
            logger.info(f"  • Note max: {max(ratings)}")
    
    def export_summary(self, output_file='data/analysis_summary.json'):
        """Exporter un résumé en JSON"""
        summary = {
            'total_establishments': sum(len(data) for data in self.all_data.values()),
            'categories': {
                cat: len(data) for cat, data in self.all_data.items()
            }
        }
        
        # Ajouter analyse spécialités si disponible
        if self.doctors_data:
            specialty_analysis = self.analyze_specialties()
            summary['doctors_specialty_analysis'] = specialty_analysis
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        logger.info(f"\n💾 Résumé exporté: {output_file}")
    
    def run_full_analysis(self):
        """Exécuter l'analyse complète"""
        logger.info("="*70)
        logger.info("🔬 ANALYSE COMPLÈTE DES RÉSULTATS")
        logger.info("="*70)
        
        self.load_data()
        
        if self.doctors_data:
            self.analyze_specialties()
            self.analyze_by_governorate()
            self.analyze_data_quality()
        
        self.analyze_all_categories()
        self.export_summary()
        
        logger.info("\n" + "="*70)
        logger.info("✅ Analyse terminée!")
        logger.info("="*70)


def main():
    """Point d'entrée"""
    analyzer = ResultsAnalyzer()
    analyzer.run_full_analysis()


if __name__ == "__main__":
    main()