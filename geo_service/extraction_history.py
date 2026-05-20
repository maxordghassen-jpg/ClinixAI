"""
Visualisation et analyse de l'historique des extractions
"""
import os
import json
from datetime import datetime, timedelta
from typing import List, Dict
from extraction_history import ExtractionHistory
from services.mongodb_service import MongoDBService
from config.settings import DATA_DIR, PLACE_CATEGORIES
from tabulate import tabulate
import matplotlib.pyplot as plt
import pandas as pd


class HistoryViewer:
    """Visualisation de l'historique des extractions"""
    
    def __init__(self):
        self.history = ExtractionHistory()
        self.mongodb = MongoDBService()
    
    def display_dashboard(self):
        """Afficher le tableau de bord complet"""
        print("\n" + "=" * 100)
        print("📊 TABLEAU DE BORD - HISTORIQUE DES EXTRACTIONS")
        print("=" * 100)
        
        # Statistiques globales
        self._display_global_stats()
        
        # Dernières exécutions
        self._display_recent_runs()
        
        # Performance par catégorie
        self._display_category_performance()
        
        # Tendances
        self._display_trends()
        
    def _display_global_stats(self):
        """Afficher les statistiques globales"""
        stats = self.history.get_statistics_summary()
        
        print("\n📈 STATISTIQUES GLOBALES")
        print("-" * 50)
        
        # Calculer le taux de succès
        success_rate = 0
        if stats['total_runs'] > 0:
            success_rate = (stats['successful_runs'] / stats['total_runs']) * 100
        
        # Formater la durée moyenne
        avg_duration = stats.get('avg_duration_seconds', 0)
        avg_hours = int(avg_duration // 3600)
        avg_minutes = int((avg_duration % 3600) // 60)
        avg_duration_str = f"{avg_hours}h {avg_minutes}m"
        
        # Dernière exécution
        last_run_str = "Jamais"
        days_since = "N/A"
        if stats['last_run_date']:
            last_run = datetime.fromisoformat(stats['last_run_date'])
            last_run_str = last_run.strftime('%Y-%m-%d %H:%M')
            days_since = (datetime.now() - last_run).days
        
        data = [
            ["Total des exécutions", stats['total_runs']],
            ["Exécutions réussies", f"{stats['successful_runs']} ({success_rate:.1f}%)"],
            ["Exécutions échouées", stats['failed_runs']],
            ["Durée moyenne", avg_duration_str],
            ["Total nouveaux établissements", stats['total_new_places']],
            ["Total mises à jour", stats['total_updated_places']],
            ["Dernière exécution", f"{last_run_str} (il y a {days_since} jours)"]
        ]
        
        print(tabulate(data, headers=["Métrique", "Valeur"], tablefmt="grid"))
    
    def _display_recent_runs(self):
        """Afficher les dernières exécutions"""
        print("\n📅 DERNIÈRES EXÉCUTIONS")
        print("-" * 50)
        
        runs = self.history.get_last_runs(10)
        
        if not runs:
            print("Aucune exécution trouvée")
            return
        
        table_data = []
        for run in runs:
            start_time = datetime.fromisoformat(run['start_time'])
            duration = run.get('duration_seconds', 0)
            duration_str = f"{int(duration // 60)}m" if duration else "N/A"
            
            status_emoji = {
                'success': '✅',
                'partial_success': '⚠️',
                'error': '❌',
                'running': '🔄'
            }.get(run['status'], '❓')
            
            table_data.append([
                run['run_id'],
                start_time.strftime('%Y-%m-%d %H:%M'),
                f"{status_emoji} {run['status']}",
                run['trigger_type'],
                duration_str,
                run.get('total_new_places', 0),
                run.get('total_updated_places', 0),
                run.get('total_errors', 0)
            ])
        
        headers = ["Run ID", "Date", "Statut", "Déclencheur", "Durée", "Nouveaux", "MAJ", "Erreurs"]
        print(tabulate(table_data, headers=headers, tablefmt="grid"))
    
    def _display_category_performance(self):
        """Afficher les performances par catégorie"""
        print("\n🏥 PERFORMANCE PAR CATÉGORIE (Dernière exécution)")
        print("-" * 50)
        
        # Obtenir la dernière exécution
        runs = self.history.get_last_runs(1)
        
        if not runs or not runs[0].get('categories_processed'):
            print("Aucune donnée de catégorie disponible")
            return
        
        last_run = runs[0]
        categories = last_run.get('categories_processed', [])
        
        table_data = []
        for cat in categories:
            errors_count = len(cat.get('errors', [])) if cat.get('errors') else 0
            status = "✅" if errors_count == 0 else "⚠️"
            
            table_data.append([
                cat['category'],
                cat.get('total_found', 0),
                cat.get('new_places', 0),
                cat.get('updated_places', 0),
                cat.get('duplicates_removed', 0),
                f"{status} {errors_count}"
            ])
        
        headers = ["Catégorie", "Total trouvé", "Nouveaux", "MAJ", "Doublons", "Erreurs"]
        print(tabulate(table_data, headers=headers, tablefmt="grid"))
    
    def _display_trends(self):
        """Afficher les tendances sur 30 jours"""
        print("\n📉 TENDANCES SUR 30 JOURS")
        print("-" * 50)
        
        # Calculer les dates
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        print(f"Période: {start_date.strftime('%Y-%m-%d')} → {end_date.strftime('%Y-%m-%d')}\n")
        
        total_new_30d = 0
        total_updated_30d = 0
        
        for category_key, category_config in PLACE_CATEGORIES.items():
            changes = self.mongodb.get_changes_since_date(
                category_config['collection'],
                start_date
            )
            
            if changes['new_count'] > 0 or changes['updated_count'] > 0:
                print(f"• {category_key}:")
                print(f"  🆕 Nouveaux: {changes['new_count']}")
                print(f"  🔄 Mis à jour: {changes['updated_count']}")
                
                total_new_30d += changes['new_count']
                total_updated_30d += changes['updated_count']
        
        print(f"\n📊 TOTAL SUR 30 JOURS:")
        print(f"   • Nouveaux établissements: {total_new_30d}")
        print(f"   • Établissements mis à jour: {total_updated_30d}")
        
        # Calculer le taux de croissance
        for category_key, category_config in PLACE_CATEGORIES.items():
            stats = self.mongodb.get_collection_stats(category_config['collection'])
            if stats['total_documents'] > 0:
                growth_rate = (total_new_30d / stats['total_documents']) * 100
                print(f"\n📈 Taux de croissance (30j): {growth_rate:.2f}%")
                break
    
    def export_report(self, output_file: str = None):
        """Exporter un rapport complet en JSON"""
        if not output_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = os.path.join(DATA_DIR, f"history_report_{timestamp}.json")
        
        # Collecter toutes les données
        report = {
            'generated_at': datetime.now().isoformat(),
            'global_stats': self.history.get_statistics_summary(),
            'last_runs': self.history.get_last_runs(30),
            'collections_stats': {}
        }
        
        # Ajouter les statistiques par collection
        for category_key, category_config in PLACE_CATEGORIES.items():
            stats = self.mongodb.get_collection_stats(category_config['collection'])
            report['collections_stats'][category_key] = stats
        
        # Sauvegarder le rapport
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"\n✅ Rapport exporté vers: {output_file}")
    
    def cleanup_old_history(self, days_to_keep: int = 90):
        """Nettoyer l'historique ancien"""
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        # Compter les enregistrements à supprimer
        count = self.history.collection.count_documents({
            'start_time': {'$lt': cutoff_date.isoformat()}
        })
        
        if count > 0:
            print(f"\n🗑️  Suppression de {count} enregistrements de plus de {days_to_keep} jours...")
            
            # Supprimer les anciens enregistrements
            result = self.history.collection.delete_many({
                'start_time': {'$lt': cutoff_date.isoformat()}
            })
            
            print(f"✅ {result.deleted_count} enregistrements supprimés")
        else:
            print(f"\nℹ️  Aucun enregistrement de plus de {days_to_keep} jours à supprimer")
    
    def close(self):
        """Fermer les connexions"""
        self.history.close()
        self.mongodb.close()


def main():
    """Point d'entrée principal"""
    viewer = HistoryViewer()
    
    while True:
        print("\n" + "=" * 60)
        print("MENU - VISUALISATION DE L'HISTORIQUE")
        print("=" * 60)
        print("1. Afficher le tableau de bord")
        print("2. Exporter un rapport JSON")
        print("3. Nettoyer l'historique ancien")
        print("4. Quitter")
        print("-" * 60)
        
        try:
            choice = input("Votre choix (1-4): ").strip()
            
            if choice == "1":
                viewer.display_dashboard()
            elif choice == "2":
                viewer.export_report()
            elif choice == "3":
                days = input("Nombre de jours à conserver (défaut: 90): ").strip()
                days = int(days) if days else 90
                viewer.cleanup_old_history(days)
            elif choice == "4":
                print("👋 Au revoir!")
                break
            else:
                print("❌ Choix invalide")
                
        except KeyboardInterrupt:
            print("\n👋 Au revoir!")
            break
        except Exception as e:
            print(f"❌ Erreur: {e}")
    
    viewer.close()


if __name__ == "__main__":
    main()