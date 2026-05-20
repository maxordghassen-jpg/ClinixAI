"""
Scheduler for automatic monthly execution
Version Text Search - ADAPTÉ À LA STRUCTURE EXISTANTE
"""
import schedule
import time
import os
import json
from datetime import datetime

# Imports adaptés à ta structure
from main import main
from utils.logger import get_logger
from config.settings import SCHEDULE_DAYS, SCHEDULE_TIME, DATA_DIR

logger = get_logger(__name__)

# Créer le dossier data
os.makedirs(DATA_DIR, exist_ok=True)

# Fichier d'historique
HISTORY_FILE = os.path.join(DATA_DIR, 'extraction_history.json')


def load_history():
    """Charger l'historique"""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return []
    return []


def save_history(history):
    """Sauvegarder l'historique"""
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def job():
    """
    Job to be executed
    """
    start_time = datetime.now()
    logger.info("=" * 80)
    logger.info(f"SCHEDULED JOB STARTED at {start_time}")
    logger.info("=" * 80)
    
    status = 'success'
    error = None
    
    try:
        main()
        logger.info("✅ Scheduled job completed successfully")
    except Exception as e:
        status = 'error'
        error = str(e)
        logger.error(f"❌ Error in scheduled job: {e}", exc_info=True)
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    # Sauvegarder dans l'historique
    history = load_history()
    history.append({
        'start_time': start_time.isoformat(),
        'end_time': end_time.isoformat(),
        'duration_seconds': duration,
        'duration_readable': f"{int(duration//3600)}h {int((duration%3600)//60)}m",
        'status': status,
        'trigger': 'scheduled',
        'error': error
    })
    
    # Garder seulement les 100 derniers
    if len(history) > 100:
        history = history[-100:]
    
    save_history(history)


def show_history():
    """Afficher l'historique"""
    history = load_history()
    
    if not history:
        logger.info("📋 Aucun historique trouvé")
        return
    
    logger.info("\n" + "=" * 60)
    logger.info("📋 HISTORIQUE DES EXTRACTIONS")
    logger.info("=" * 60)
    
    total = len(history)
    success = sum(1 for r in history if r['status'] == 'success')
    errors = sum(1 for r in history if r['status'] == 'error')
    
    logger.info(f"Total: {total} | Succès: {success} | Erreurs: {errors}")
    
    if total > 0:
        logger.info("\n5 Dernières exécutions:")
        for run in history[-5:]:
            start = datetime.fromisoformat(run['start_time'])
            icon = "✅" if run['status'] == 'success' else "❌"
            logger.info(
                f"  {icon} {start.strftime('%Y-%m-%d %H:%M')} - "
                f"{run['duration_readable']}"
            )


def run_scheduler():
    """
    Run the scheduler
    """
    logger.info("=" * 80)
    logger.info("MEDICAL DATA EXTRACTOR SCHEDULER")
    logger.info("=" * 80)
    logger.info(f"Schedule: Every {SCHEDULE_DAYS} days at {SCHEDULE_TIME}")
    logger.info(f"Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 80)
    
    # Afficher l'historique
    show_history()
    
    # Vérifier si besoin d'exécuter maintenant
    history = load_history()
    if history:
        last_run = history[-1]
        last_date = datetime.fromisoformat(last_run['start_time'])
        days_since = (datetime.now() - last_date).days
        
        logger.info(f"\n📅 Dernière exécution: il y a {days_since} jours")
        
        if days_since >= SCHEDULE_DAYS:
            logger.info(f"⚠️  Une exécution est en retard!")
            response = input("Exécuter maintenant? (o/n): ")
            if response.lower() == 'o':
                job()
    else:
        logger.info("\n🆕 Première exécution")
        response = input("Lancer maintenant? (o/n): ")
        if response.lower() == 'o':
            job()
    
    # Schedule the job
    schedule.every(SCHEDULE_DAYS).days.at(SCHEDULE_TIME).do(job)
    
    logger.info(f"\n✅ Scheduler actif")
    logger.info(f"⏰ Prochaine exécution: {schedule.next_run()}")
    logger.info("Appuyez sur Ctrl+C pour arrêter\n")
    
    # Keep the scheduler running
    while True:
        try:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
        except KeyboardInterrupt:
            logger.info("\n⛔ Arrêt du scheduler")
            break


if __name__ == "__main__":
    run_scheduler()