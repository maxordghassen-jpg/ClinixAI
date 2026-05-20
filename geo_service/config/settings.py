"""
Configuration settings for Medical Data Extractor
Version complète avec toutes les délégations
"""
import os
from typing import Dict, List
from dotenv import load_dotenv

# Charger les variables d'environnement depuis .env
load_dotenv()

# ============================================================
# 🔑 API Configuration
# ============================================================
GOOGLE_MAPS_API_KEY = os.getenv('GOOGLE_MAPS_API_KEY', 'YOUR_API_KEY_HERE')
MONGODB_URI = os.getenv('MONGODB_URI', 'mongodb://localhost:27017')
DATABASE_NAME = os.getenv('DATABASE_NAME', 'medical_data_tunisia')

# ============================================================
# 📍 Search Configuration
# ============================================================
SEARCH_RADIUS = 15000  # 15km pour couvrir délégations

# ============================================================
# 🗺️ TOUTES LES DÉLÉGATIONS DE TUNISIE
# ============================================================
TUNISIA_DELEGATIONS = [
    # ═══════════════════════════════════════════════════════
    # TUNIS (21 délégations)
    # ═══════════════════════════════════════════════════════
    {'name': 'Tunis Médina', 'governorate': 'Tunis', 'lat': 36.8065, 'lng': 10.1815},
    {'name': 'Bab Bhar', 'governorate': 'Tunis', 'lat': 36.8031, 'lng': 10.1708},
    {'name': 'Bab Souika', 'governorate': 'Tunis', 'lat': 36.8156, 'lng': 10.1750},
    {'name': 'Omrane', 'governorate': 'Tunis', 'lat': 36.8333, 'lng': 10.1667},
    {'name': 'Omrane Supérieur', 'governorate': 'Tunis', 'lat': 36.8500, 'lng': 10.1667},
    {'name': 'Ettahrir', 'governorate': 'Tunis', 'lat': 36.8167, 'lng': 10.1833},
    {'name': 'Ezzouhour', 'governorate': 'Tunis', 'lat': 36.8333, 'lng': 10.2000},
    {'name': 'El Hrairia', 'governorate': 'Tunis', 'lat': 36.8500, 'lng': 10.2167},
    {'name': 'El Kabaria', 'governorate': 'Tunis', 'lat': 36.7833, 'lng': 10.2167},
    {'name': 'Sidi Hassine', 'governorate': 'Tunis', 'lat': 36.7667, 'lng': 10.1667},
    {'name': 'El Ouardia', 'governorate': 'Tunis', 'lat': 36.8333, 'lng': 10.1500},
    {'name': 'Sidi El Béchir', 'governorate': 'Tunis', 'lat': 36.8500, 'lng': 10.2333},
    {'name': 'Djebel Jelloud', 'governorate': 'Tunis', 'lat': 36.8667, 'lng': 10.2000},
    {'name': 'La Marsa', 'governorate': 'Tunis', 'lat': 36.8783, 'lng': 10.3247},
    {'name': 'Le Bardo', 'governorate': 'Tunis', 'lat': 36.8081, 'lng': 10.1370},
    {'name': 'Le Kram', 'governorate': 'Tunis', 'lat': 36.8333, 'lng': 10.3000},
    {'name': 'La Goulette', 'governorate': 'Tunis', 'lat': 36.8183, 'lng': 10.3053},
    {'name': 'Carthage', 'governorate': 'Tunis', 'lat': 36.8531, 'lng': 10.3231},
    {'name': 'El Menzah', 'governorate': 'Tunis', 'lat': 36.8333, 'lng': 10.1667},
    {'name': 'Cité El Khadra', 'governorate': 'Tunis', 'lat': 36.8500, 'lng': 10.1833},
    {'name': 'El Omrane', 'governorate': 'Tunis', 'lat': 36.8333, 'lng': 10.1667},
    
    # ═══════════════════════════════════════════════════════
    # ARIANA (7 délégations)
    # ═══════════════════════════════════════════════════════
    {'name': 'Ariana Ville', 'governorate': 'Ariana', 'lat': 36.8625, 'lng': 10.1956},
    {'name': 'Ettadhamen', 'governorate': 'Ariana', 'lat': 36.8500, 'lng': 10.1667},
    {'name': 'Mnihla', 'governorate': 'Ariana', 'lat': 36.8833, 'lng': 10.1333},
    {'name': 'Raoued', 'governorate': 'Ariana', 'lat': 36.9330, 'lng': 10.1831},
    {'name': 'Kalaat Landlous', 'governorate': 'Ariana', 'lat': 36.9167, 'lng': 10.1667},
    {'name': 'Sidi Thabet', 'governorate': 'Ariana', 'lat': 36.9167, 'lng': 10.0500},
    {'name': 'La Soukra', 'governorate': 'Ariana', 'lat': 36.8667, 'lng': 10.2167},
    
    # ═══════════════════════════════════════════════════════
    # BEN AROUS (12 délégations)
    # ═══════════════════════════════════════════════════════
    {'name': 'Ben Arous', 'governorate': 'Ben Arous', 'lat': 36.7469, 'lng': 10.2192},
    {'name': 'Mégrine', 'governorate': 'Ben Arous', 'lat': 36.7500, 'lng': 10.2333},
    {'name': 'Mohamedia', 'governorate': 'Ben Arous', 'lat': 36.6833, 'lng': 10.2833},
    {'name': 'Fouchana', 'governorate': 'Ben Arous', 'lat': 36.7000, 'lng': 10.1833},
    {'name': 'Ezzahra', 'governorate': 'Ben Arous', 'lat': 36.7522, 'lng': 10.3253},
    {'name': 'Radès', 'governorate': 'Ben Arous', 'lat': 36.7667, 'lng': 10.2833},
    {'name': 'Hammam Lif', 'governorate': 'Ben Arous', 'lat': 36.7333, 'lng': 10.3333},
    {'name': 'Hammam Chott', 'governorate': 'Ben Arous', 'lat': 36.7167, 'lng': 10.3333},
    {'name': 'Bou Mhel', 'governorate': 'Ben Arous', 'lat': 36.7667, 'lng': 10.2167},
    {'name': 'Nouvelle Medina', 'governorate': 'Ben Arous', 'lat': 36.7333, 'lng': 10.1833},
    {'name': 'El Mourouj', 'governorate': 'Ben Arous', 'lat': 36.7333, 'lng': 10.2167},
    {'name': 'Mornag', 'governorate': 'Ben Arous', 'lat': 36.6833, 'lng': 10.3000},
    
    # ═══════════════════════════════════════════════════════
    # MANOUBA (8 délégations)
    # ═══════════════════════════════════════════════════════
    {'name': 'Manouba', 'governorate': 'Manouba', 'lat': 36.8103, 'lng': 10.0969},
    {'name': 'Douar Hicher', 'governorate': 'Manouba', 'lat': 36.8167, 'lng': 10.1000},
    {'name': 'Oued Ellil', 'governorate': 'Manouba', 'lat': 36.8333, 'lng': 10.0833},
    {'name': 'Mornaguia', 'governorate': 'Manouba', 'lat': 36.7500, 'lng': 9.9333},
    {'name': 'Borj El Amri', 'governorate': 'Manouba', 'lat': 36.7167, 'lng': 9.6500},
    {'name': 'Djedeida', 'governorate': 'Manouba', 'lat': 36.8333, 'lng': 9.9167},
    {'name': 'Tebourba', 'governorate': 'Manouba', 'lat': 36.8333, 'lng': 9.7500},
    {'name': 'El Battan', 'governorate': 'Manouba', 'lat': 36.7833, 'lng': 9.8667},
    
    # ═══════════════════════════════════════════════════════
    # NABEUL (16 délégations)
    # ═══════════════════════════════════════════════════════
    {'name': 'Nabeul', 'governorate': 'Nabeul', 'lat': 36.4561, 'lng': 10.7376},
    {'name': 'Dar Chaabane', 'governorate': 'Nabeul', 'lat': 36.4667, 'lng': 10.7500},
    {'name': 'Béni Khiar', 'governorate': 'Nabeul', 'lat': 36.4667, 'lng': 10.7833},
    {'name': 'Korba', 'governorate': 'Nabeul', 'lat': 36.5833, 'lng': 10.8667},
    {'name': 'Menzel Temime', 'governorate': 'Nabeul', 'lat': 36.7833, 'lng': 10.9833},
    {'name': 'Kelibia', 'governorate': 'Nabeul', 'lat': 36.8472, 'lng': 11.0936},
    {'name': 'Hammam Ghezèze', 'governorate': 'Nabeul', 'lat': 36.7333, 'lng': 10.9833},
    {'name': 'Haouaria', 'governorate': 'Nabeul', 'lat': 37.0333, 'lng': 11.0167},
    {'name': 'Soliman', 'governorate': 'Nabeul', 'lat': 36.7000, 'lng': 10.4833},
    {'name': 'Menzel Bouzelfa', 'governorate': 'Nabeul', 'lat': 36.6833, 'lng': 10.5833},
    {'name': 'Beni Khalled', 'governorate': 'Nabeul', 'lat': 36.6500, 'lng': 10.5833},
    {'name': 'Grombalia', 'governorate': 'Nabeul', 'lat': 36.6000, 'lng': 10.5000},
    {'name': 'Bou Argoub', 'governorate': 'Nabeul', 'lat': 36.5833, 'lng': 10.5333},
    {'name': 'Hammamet', 'governorate': 'Nabeul', 'lat': 36.4000, 'lng': 10.6167},
    {'name': 'Takelsa', 'governorate': 'Nabeul', 'lat': 36.7833, 'lng': 10.6333},
    {'name': 'El Mida', 'governorate': 'Nabeul', 'lat': 36.7667, 'lng': 10.8500},
    
    # ═══════════════════════════════════════════════════════
    # ZAGHOUAN (6 délégations)
    # ═══════════════════════════════════════════════════════
    {'name': 'Zaghouan', 'governorate': 'Zaghouan', 'lat': 36.4028, 'lng': 10.1428},
    {'name': 'Zriba', 'governorate': 'Zaghouan', 'lat': 36.5833, 'lng': 10.3333},
    {'name': 'Bir Mcherga', 'governorate': 'Zaghouan', 'lat': 36.5500, 'lng': 10.0500},
    {'name': 'El Fahs', 'governorate': 'Zaghouan', 'lat': 36.3833, 'lng': 9.9000},
    {'name': 'Nadhour', 'governorate': 'Zaghouan', 'lat': 36.3500, 'lng': 10.0667},
    {'name': 'Saouaf', 'governorate': 'Zaghouan', 'lat': 36.3000, 'lng': 10.2000},
    
    # ═══════════════════════════════════════════════════════
    # BIZERTE (14 délégations)
    # ═══════════════════════════════════════════════════════
    {'name': 'Bizerte Nord', 'governorate': 'Bizerte', 'lat': 37.2746, 'lng': 9.8739},
    {'name': 'Bizerte Sud', 'governorate': 'Bizerte', 'lat': 37.2500, 'lng': 9.8667},
    {'name': 'Menzel Bourguiba', 'governorate': 'Bizerte', 'lat': 37.1544, 'lng': 9.7847},
    {'name': 'Menzel Jemil', 'governorate': 'Bizerte', 'lat': 37.2333, 'lng': 9.9167},
    {'name': 'El Alia', 'governorate': 'Bizerte', 'lat': 37.1667, 'lng': 10.0333},
    {'name': 'Ras Jebel', 'governorate': 'Bizerte', 'lat': 37.2167, 'lng': 10.1000},
    {'name': 'Ghar El Melh', 'governorate': 'Bizerte', 'lat': 37.1667, 'lng': 10.1833},
    {'name': 'Mateur', 'governorate': 'Bizerte', 'lat': 37.0403, 'lng': 9.6656},
    {'name': 'Joumine', 'governorate': 'Bizerte', 'lat': 37.1333, 'lng': 9.5833},
    {'name': 'Tinja', 'governorate': 'Bizerte', 'lat': 37.1667, 'lng': 9.7833},
    {'name': 'Utique', 'governorate': 'Bizerte', 'lat': 37.0583, 'lng': 10.0606},
    {'name': 'Sejnane', 'governorate': 'Bizerte', 'lat': 37.0500, 'lng': 9.2333},
    {'name': 'Ghezala', 'governorate': 'Bizerte', 'lat': 37.0667, 'lng': 9.1167},
    {'name': 'Zarzouna', 'governorate': 'Bizerte', 'lat': 37.1000, 'lng': 9.4333},
    
    # ═══════════════════════════════════════════════════════
    # BEJA (9 délégations)
    # ═══════════════════════════════════════════════════════
    {'name': 'Béja Nord', 'governorate': 'Béja', 'lat': 36.7256, 'lng': 9.1817},
    {'name': 'Béja Sud', 'governorate': 'Béja', 'lat': 36.7000, 'lng': 9.1667},
    {'name': 'Amdoun', 'governorate': 'Béja', 'lat': 36.6167, 'lng': 8.9667},
    {'name': 'Nefza', 'governorate': 'Béja', 'lat': 37.0333, 'lng': 9.3167},
    {'name': 'Teboursouk', 'governorate': 'Béja', 'lat': 36.4667, 'lng': 9.2500},
    {'name': 'Tibar', 'governorate': 'Béja', 'lat': 36.6500, 'lng': 9.3667},
    {'name': 'Testour', 'governorate': 'Béja', 'lat': 36.5500, 'lng': 9.4500},
    {'name': 'Goubellat', 'governorate': 'Béja', 'lat': 36.5333, 'lng': 9.6667},
    {'name': 'Mejez El Bab', 'governorate': 'Béja', 'lat': 36.6500, 'lng': 9.6167},
    
    # ═══════════════════════════════════════════════════════
    # JENDOUBA (9 délégations)
    # ═══════════════════════════════════════════════════════
    {'name': 'Jendouba', 'governorate': 'Jendouba', 'lat': 36.5011, 'lng': 8.7803},
    {'name': 'Jendouba Nord', 'governorate': 'Jendouba', 'lat': 36.5167, 'lng': 8.7833},
    {'name': 'Bou Salem', 'governorate': 'Jendouba', 'lat': 36.6167, 'lng': 8.9667},
    {'name': 'Tabarka', 'governorate': 'Jendouba', 'lat': 36.9544, 'lng': 8.7581},
    {'name': 'Aïn Draham', 'governorate': 'Jendouba', 'lat': 36.7833, 'lng': 8.6833},
    {'name': 'Fernana', 'governorate': 'Jendouba', 'lat': 36.6667, 'lng': 8.6500},
    {'name': 'Balta Bou Aouane', 'governorate': 'Jendouba', 'lat': 36.7500, 'lng': 8.9167},
    {'name': 'Oued Meliz', 'governorate': 'Jendouba', 'lat': 36.4833, 'lng': 8.6667},
    {'name': 'Ghardimaou', 'governorate': 'Jendouba', 'lat': 36.4500, 'lng': 8.4500},
    
    # ═══════════════════════════════════════════════════════
    # LE KEF (11 délégations)
    # ═══════════════════════════════════════════════════════
    {'name': 'Le Kef Est', 'governorate': 'Le Kef', 'lat': 36.1697, 'lng': 8.7147},
    {'name': 'Le Kef Ouest', 'governorate': 'Le Kef', 'lat': 36.1500, 'lng': 8.7000},
    {'name': 'Nebeur', 'governorate': 'Le Kef', 'lat': 36.2333, 'lng': 8.7667},
    {'name': 'Sakiet Sidi Youssef', 'governorate': 'Le Kef', 'lat': 36.2333, 'lng': 8.3667},
    {'name': 'Tajerouine', 'governorate': 'Le Kef', 'lat': 36.0667, 'lng': 8.5500},
    {'name': 'Kalaat Senan', 'governorate': 'Le Kef', 'lat': 36.0500, 'lng': 8.8500},
    {'name': 'Kalaat Khasba', 'governorate': 'Le Kef', 'lat': 36.3167, 'lng': 8.9667},
    {'name': 'Jerissa', 'governorate': 'Le Kef', 'lat': 36.0333, 'lng': 8.6333},
    {'name': 'El Ksour', 'governorate': 'Le Kef', 'lat': 36.0833, 'lng': 9.3167},
    {'name': 'Dahmani', 'governorate': 'Le Kef', 'lat': 35.9667, 'lng': 8.8667},
    {'name': 'Sers', 'governorate': 'Le Kef', 'lat': 36.1000, 'lng': 9.0167},
    
    # ═══════════════════════════════════════════════════════
    # SILIANA (11 délégations)
    # ═══════════════════════════════════════════════════════
    {'name': 'Siliana Nord', 'governorate': 'Siliana', 'lat': 36.0858, 'lng': 9.3711},
    {'name': 'Siliana Sud', 'governorate': 'Siliana', 'lat': 36.0667, 'lng': 9.3667},
    {'name': 'Bou Arada', 'governorate': 'Siliana', 'lat': 36.3500, 'lng': 9.6167},
    {'name': 'Gaâfour', 'governorate': 'Siliana', 'lat': 36.3167, 'lng': 9.3167},
    {'name': 'El Aroussa', 'governorate': 'Siliana', 'lat': 36.0833, 'lng': 9.7667},
    {'name': 'El Krib', 'governorate': 'Siliana', 'lat': 36.3167, 'lng': 9.1333},
    {'name': 'Sidi Bou Rouis', 'governorate': 'Siliana', 'lat': 36.1167, 'lng': 9.1833},
    {'name': 'Maktar', 'governorate': 'Siliana', 'lat': 35.8667, 'lng': 9.2000},
    {'name': 'Rouhia', 'governorate': 'Siliana', 'lat': 36.0333, 'lng': 9.5500},
    {'name': 'Kesra', 'governorate': 'Siliana', 'lat': 35.8167, 'lng': 9.3667},
    {'name': 'Bargou', 'governorate': 'Siliana', 'lat': 36.1000, 'lng': 9.6833},
    
    # ═══════════════════════════════════════════════════════
    # SOUSSE (16 délégations)
    # ═══════════════════════════════════════════════════════
    {'name': 'Sousse Médina', 'governorate': 'Sousse', 'lat': 35.8256, 'lng': 10.6369},
    {'name': 'Sousse Riadh', 'governorate': 'Sousse', 'lat': 35.8333, 'lng': 10.6167},
    {'name': 'Sousse Jawhara', 'governorate': 'Sousse', 'lat': 35.8167, 'lng': 10.6333},
    {'name': 'Sousse Sidi Abdelhamid', 'governorate': 'Sousse', 'lat': 35.8333, 'lng': 10.6500},
    {'name': 'Hammam Sousse', 'governorate': 'Sousse', 'lat': 35.8667, 'lng': 10.6000},
    {'name': 'Akouda', 'governorate': 'Sousse', 'lat': 35.8667, 'lng': 10.5667},
    {'name': 'Kalaa Kebira', 'governorate': 'Sousse', 'lat': 35.8667, 'lng': 10.5167},
    {'name': 'Kalaa Sghira', 'governorate': 'Sousse', 'lat': 35.8833, 'lng': 10.4833},
    {'name': 'Sidi Bou Ali', 'governorate': 'Sousse', 'lat': 35.9500, 'lng': 10.4833},
    {'name': 'Hergla', 'governorate': 'Sousse', 'lat': 36.0333, 'lng': 10.5167},
    {'name': 'Enfidha', 'governorate': 'Sousse', 'lat': 36.1333, 'lng': 10.3833},
    {'name': 'Bouficha', 'governorate': 'Sousse', 'lat': 36.2667, 'lng': 10.4333},
    {'name': 'Kondar', 'governorate': 'Sousse', 'lat': 35.8833, 'lng': 10.7167},
    {'name': 'Msaken', 'governorate': 'Sousse', 'lat': 35.7294, 'lng': 10.5808},
    {'name': 'Sidi El Hani', 'governorate': 'Sousse', 'lat': 35.6667, 'lng': 10.3167},
    {'name': 'Zaouiet Sousse', 'governorate': 'Sousse', 'lat': 35.7833, 'lng': 10.6333},
    
    # ═══════════════════════════════════════════════════════
    # MONASTIR (12 délégations)
    # ═══════════════════════════════════════════════════════
    {'name': 'Monastir', 'governorate': 'Monastir', 'lat': 35.7772, 'lng': 10.8263},
    {'name': 'Jemmal', 'governorate': 'Monastir', 'lat': 35.6244, 'lng': 10.7575},
    {'name': 'Ksar Hellal', 'governorate': 'Monastir', 'lat': 35.6478, 'lng': 10.8911},
    {'name': 'Moknine', 'governorate': 'Monastir', 'lat': 35.6333, 'lng': 10.9000},
    {'name': 'Bembla', 'governorate': 'Monastir', 'lat': 35.7167, 'lng': 10.8000},
    {'name': 'Bekalta', 'governorate': 'Monastir', 'lat': 35.6167, 'lng': 11.0000},
    {'name': 'Teboulba', 'governorate': 'Monastir', 'lat': 35.6833, 'lng': 10.9667},
    {'name': 'Sahline', 'governorate': 'Monastir', 'lat': 35.7500, 'lng': 10.7167},
    {'name': 'Zeramdine', 'governorate': 'Monastir', 'lat': 35.6833, 'lng': 10.7833},
    {'name': 'Ksibet el Mediouni', 'governorate': 'Monastir', 'lat': 35.6667, 'lng': 10.8333},
    {'name': 'Ouerdanine', 'governorate': 'Monastir', 'lat': 35.7000, 'lng': 10.6667},
    {'name': 'Sayada-Lamta-Bou Hajar', 'governorate': 'Monastir', 'lat': 35.7167, 'lng': 10.8667},
    
    # ═══════════════════════════════════════════════════════
    # MAHDIA (11 délégations)
    # ═══════════════════════════════════════════════════════
    {'name': 'Mahdia', 'governorate': 'Mahdia', 'lat': 35.5047, 'lng': 11.0622},
    {'name': 'Bou Merdes', 'governorate': 'Mahdia', 'lat': 35.5833, 'lng': 11.0667},
    {'name': 'Ouled Chamekh', 'governorate': 'Mahdia', 'lat': 35.5667, 'lng': 10.8833},
    {'name': 'Chorbane', 'governorate': 'Mahdia', 'lat': 35.2833, 'lng': 10.3833},
    {'name': 'Hebira', 'governorate': 'Mahdia', 'lat': 35.5500, 'lng': 10.5500},
    {'name': 'Essouassi', 'governorate': 'Mahdia', 'lat': 35.4167, 'lng': 10.6667},
    {'name': 'El Jem', 'governorate': 'Mahdia', 'lat': 35.3000, 'lng': 10.7167},
    {'name': 'Chebba', 'governorate': 'Mahdia', 'lat': 35.2333, 'lng': 11.1167},
    {'name': 'Melloulech', 'governorate': 'Mahdia', 'lat': 35.1667, 'lng': 11.0333},
    {'name': 'Sidi Alouane', 'governorate': 'Mahdia', 'lat': 35.3667, 'lng': 10.9333},
    {'name': 'Ksour Essef', 'governorate': 'Mahdia', 'lat': 35.4167, 'lng': 10.9833},
    
    # ═══════════════════════════════════════════════════════
    # SFAX (16 délégations)
    # ═══════════════════════════════════════════════════════
    {'name': 'Sfax Ville', 'governorate': 'Sfax', 'lat': 34.7406, 'lng': 10.7603},
    {'name': 'Sfax Ouest', 'governorate': 'Sfax', 'lat': 34.7500, 'lng': 10.7333},
    {'name': 'Sfax Sud', 'governorate': 'Sfax', 'lat': 34.7167, 'lng': 10.7667},
    {'name': 'Sakiet Ezzit', 'governorate': 'Sfax', 'lat': 34.7925, 'lng': 10.7231},
    {'name': 'Sakiet Eddaier', 'governorate': 'Sfax', 'lat': 34.8167, 'lng': 10.7167},
    {'name': 'Thyna', 'governorate': 'Sfax', 'lat': 34.6833, 'lng': 10.8167},
    {'name': 'Agareb', 'governorate': 'Sfax', 'lat': 34.7333, 'lng': 10.4833},
    {'name': 'Jebiniana', 'governorate': 'Sfax', 'lat': 34.9333, 'lng': 10.9167},
    {'name': 'El Amra', 'governorate': 'Sfax', 'lat': 34.6667, 'lng': 10.5000},
    {'name': 'El Hencha', 'governorate': 'Sfax', 'lat': 34.6333, 'lng': 10.7333},
    {'name': 'Menzel Chaker', 'governorate': 'Sfax', 'lat': 34.6167, 'lng': 10.5667},
    {'name': 'Ghraiba', 'governorate': 'Sfax', 'lat': 34.6667, 'lng': 10.6333},
    {'name': 'Bir Ali Ben Khelifa', 'governorate': 'Sfax', 'lat': 34.7167, 'lng': 10.1000},
    {'name': 'Skhira', 'governorate': 'Sfax', 'lat': 34.2950, 'lng': 10.0700},
    {'name': 'Mahres', 'governorate': 'Sfax', 'lat': 34.5333, 'lng': 10.5000},
    {'name': 'Kerkennah', 'governorate': 'Sfax', 'lat': 34.7333, 'lng': 11.2000},
    
    # ═══════════════════════════════════════════════════════
    # KAIROUAN (11 délégations)
    # ═══════════════════════════════════════════════════════
    {'name': 'Kairouan Nord', 'governorate': 'Kairouan', 'lat': 35.6781, 'lng': 10.0967},
    {'name': 'Kairouan Sud', 'governorate': 'Kairouan', 'lat': 35.6667, 'lng': 10.1000},
    {'name': 'Echbika', 'governorate': 'Kairouan', 'lat': 35.7500, 'lng': 10.0333},
    {'name': 'Sbikha', 'governorate': 'Kairouan', 'lat': 35.9333, 'lng': 10.0333},
    {'name': 'Oueslatia', 'governorate': 'Kairouan', 'lat': 35.8500, 'lng': 9.6500},
    {'name': 'Haffouz', 'governorate': 'Kairouan', 'lat': 35.6333, 'lng': 9.6833},
    {'name': 'El Alaa', 'governorate': 'Kairouan', 'lat': 35.5500, 'lng': 9.5333},
    {'name': 'Hajeb El Ayoun', 'governorate': 'Kairouan', 'lat': 35.5667, 'lng': 9.7167},
    {'name': 'Nasrallah', 'governorate': 'Kairouan', 'lat': 35.5000, 'lng': 10.0667},
    {'name': 'Cherarda', 'governorate': 'Kairouan', 'lat': 35.4500, 'lng': 10.2500},
    {'name': 'Bouhajla', 'governorate': 'Kairouan', 'lat': 35.5833, 'lng': 9.9167},
    
    # ═══════════════════════════════════════════════════════
    # KASSERINE (13 délégations)
    # ═══════════════════════════════════════════════════════
    {'name': 'Kasserine Nord', 'governorate': 'Kasserine', 'lat': 35.1678, 'lng': 8.8364},
    {'name': 'Kasserine Sud', 'governorate': 'Kasserine', 'lat': 35.1500, 'lng': 8.8333},
    {'name': 'Ezzouhour', 'governorate': 'Kasserine', 'lat': 35.1833, 'lng': 8.8500},
    {'name': 'Hassi El Frid', 'governorate': 'Kasserine', 'lat': 35.2333, 'lng': 8.6667},
    {'name': 'Sbeitla', 'governorate': 'Kasserine', 'lat': 35.2333, 'lng': 9.1167},
    {'name': 'Sbiba', 'governorate': 'Kasserine', 'lat': 35.5333, 'lng': 9.0667},
    {'name': 'Jedeliane', 'governorate': 'Kasserine', 'lat': 35.4167, 'lng': 8.8667},
    {'name': 'El Ayoun', 'governorate': 'Kasserine', 'lat': 35.4667, 'lng': 8.7167},
    {'name': 'Thala', 'governorate': 'Kasserine', 'lat': 35.5667, 'lng': 8.6667},
    {'name': 'Hidra', 'governorate': 'Kasserine', 'lat': 34.9667, 'lng': 9.1000},
    {'name': 'Foussana', 'governorate': 'Kasserine', 'lat': 35.5833, 'lng': 9.4333},
    {'name': 'Feriana', 'governorate': 'Kasserine', 'lat': 34.9500, 'lng': 8.5667},
    {'name': 'Majel Bel Abbès', 'governorate': 'Kasserine', 'lat': 35.1500, 'lng': 8.6833},
    
    # ═══════════════════════════════════════════════════════
    # SIDI BOUZID (12 délégations)
    # ═══════════════════════════════════════════════════════
    {'name': 'Sidi Bouzid Ouest', 'governorate': 'Sidi Bouzid', 'lat': 35.0381, 'lng': 9.4858},
    {'name': 'Sidi Bouzid Est', 'governorate': 'Sidi Bouzid', 'lat': 35.0500, 'lng': 9.5000},
    {'name': 'Jilma', 'governorate': 'Sidi Bouzid', 'lat': 34.9833, 'lng': 9.5333},
    {'name': 'Cebbala Ouled Asker', 'governorate': 'Sidi Bouzid', 'lat': 35.1167, 'lng': 9.8333},
    {'name': 'Bir El Hafey', 'governorate': 'Sidi Bouzid', 'lat': 34.9333, 'lng': 9.2167},
    {'name': 'Sidi Ali Ben Aoun', 'governorate': 'Sidi Bouzid', 'lat': 35.0500, 'lng': 9.6667},
    {'name': 'Menzel Bouzaiene', 'governorate': 'Sidi Bouzid', 'lat': 35.0833, 'lng': 9.6333},
    {'name': 'Meknassy', 'governorate': 'Sidi Bouzid', 'lat': 34.6167, 'lng': 9.6000},
    {'name': 'Souk Jedid', 'governorate': 'Sidi Bouzid', 'lat': 35.3333, 'lng': 9.9000},
    {'name': 'Mezzouna', 'governorate': 'Sidi Bouzid', 'lat': 34.5833, 'lng': 9.9000},
    {'name': 'Regueb', 'governorate': 'Sidi Bouzid', 'lat': 34.8500, 'lng': 9.7833},
    {'name': 'Ouled Haffouz', 'governorate': 'Sidi Bouzid', 'lat': 35.3167, 'lng': 9.6500},
    
    # ═══════════════════════════════════════════════════════
    # GABES (10 délégations)
    # ═══════════════════════════════════════════════════════
    {'name': 'Gabès Médina', 'governorate': 'Gabès', 'lat': 33.8815, 'lng': 10.0982},
    {'name': 'Gabès Ouest', 'governorate': 'Gabès', 'lat': 33.8833, 'lng': 10.0833},
    {'name': 'Gabès Sud', 'governorate': 'Gabès', 'lat': 33.8667, 'lng': 10.1000},
    {'name': 'Ghannouch', 'governorate': 'Gabès', 'lat': 33.9500, 'lng': 10.0833},
    {'name': 'El Hamma', 'governorate': 'Gabès', 'lat': 33.8917, 'lng': 9.7983},
    {'name': 'Matmata', 'governorate': 'Gabès', 'lat': 33.5500, 'lng': 9.9667},
    {'name': 'Nouvelle Matmata', 'governorate': 'Gabès', 'lat': 33.5000, 'lng': 10.0333},
    {'name': 'Mareth', 'governorate': 'Gabès', 'lat': 33.6333, 'lng': 10.2833},
    {'name': 'El Metouia', 'governorate': 'Gabès', 'lat': 33.7833, 'lng': 10.0500},
    {'name': 'Menzel El Habib', 'governorate': 'Gabès', 'lat': 33.8333, 'lng': 10.0167},
    
    # ═══════════════════════════════════════════════════════
    # MEDENINE (9 délégations)
    # ═══════════════════════════════════════════════════════
    {'name': 'Médenine Nord', 'governorate': 'Médenine', 'lat': 33.3547, 'lng': 10.5053},
    {'name': 'Médenine Sud', 'governorate': 'Médenine', 'lat': 33.3333, 'lng': 10.5000},
    {'name': 'Beni Khedache', 'governorate': 'Médenine', 'lat': 33.2500, 'lng': 10.1833},
    {'name': 'Ben Guerdane', 'governorate': 'Médenine', 'lat': 33.1333, 'lng': 11.2167},
    {'name': 'Zarzis', 'governorate': 'Médenine', 'lat': 33.5042, 'lng': 11.1122},
    {'name': 'Houmt Souk', 'governorate': 'Médenine', 'lat': 33.8767, 'lng': 10.8578},
    {'name': 'Midoun', 'governorate': 'Médenine', 'lat': 33.8000, 'lng': 10.9833},
    {'name': 'Ajim', 'governorate': 'Médenine', 'lat': 33.7167, 'lng': 10.7500},
    {'name': 'Sidi Makhlouf', 'governorate': 'Médenine', 'lat': 33.5667, 'lng': 10.6833},
    
    # ═══════════════════════════════════════════════════════
    # TATAOUINE (7 délégations)
    # ═══════════════════════════════════════════════════════
    {'name': 'Tataouine Nord', 'governorate': 'Tataouine', 'lat': 32.9297, 'lng': 10.4517},
    {'name': 'Tataouine Sud', 'governorate': 'Tataouine', 'lat': 32.9167, 'lng': 10.4500},
    {'name': 'Smâr', 'governorate': 'Tataouine', 'lat': 32.9667, 'lng': 10.3500},
    {'name': 'Bir Lahmar', 'governorate': 'Tataouine', 'lat': 32.5167, 'lng': 10.7667},
    {'name': 'Ghomrassen', 'governorate': 'Tataouine', 'lat': 33.0833, 'lng': 10.3833},
    {'name': 'Dhehiba', 'governorate': 'Tataouine', 'lat': 32.0833, 'lng': 10.5000},
    {'name': 'Remada', 'governorate': 'Tataouine', 'lat': 32.3167, 'lng': 10.3833},
    
    # ═══════════════════════════════════════════════════════
    # GAFSA (11 délégations)
    # ═══════════════════════════════════════════════════════
    {'name': 'Gafsa Nord', 'governorate': 'Gafsa', 'lat': 34.4250, 'lng': 8.7842},
    {'name': 'Gafsa Sud', 'governorate': 'Gafsa', 'lat': 34.4167, 'lng': 8.7833},
    {'name': 'Sidi Aïch', 'governorate': 'Gafsa', 'lat': 34.4333, 'lng': 8.8000},
    {'name': 'El Ksar', 'governorate': 'Gafsa', 'lat': 34.4833, 'lng': 8.8333},
    {'name': 'Oum El Araies', 'governorate': 'Gafsa', 'lat': 34.5667, 'lng': 8.9333},
    {'name': 'Redeyef', 'governorate': 'Gafsa', 'lat': 34.3833, 'lng': 8.1500},
    {'name': 'Métlaoui', 'governorate': 'Gafsa', 'lat': 34.3217, 'lng': 8.4006},
    {'name': 'Mdhila', 'governorate': 'Gafsa', 'lat': 34.2833, 'lng': 8.7000},
    {'name': 'El Guettar', 'governorate': 'Gafsa', 'lat': 34.3500, 'lng': 8.9500},
    {'name': 'Sned', 'governorate': 'Gafsa', 'lat': 34.1833, 'lng': 8.8333},
    {'name': 'Belkhir', 'governorate': 'Gafsa', 'lat': 34.4667, 'lng': 9.0333},
    
    # ═══════════════════════════════════════════════════════
    # TOZEUR (6 délégations)
    # ═══════════════════════════════════════════════════════
    {'name': 'Tozeur', 'governorate': 'Tozeur', 'lat': 33.9197, 'lng': 8.1339},
    {'name': 'Degache', 'governorate': 'Tozeur', 'lat': 33.9833, 'lng': 8.2000},
    {'name': 'Tameghza', 'governorate': 'Tozeur', 'lat': 34.3667, 'lng': 7.9333},
    {'name': 'Nefta', 'governorate': 'Tozeur', 'lat': 33.8833, 'lng': 7.8833},
    {'name': 'Hazoua', 'governorate': 'Tozeur', 'lat': 33.7833, 'lng': 8.2500},
    {'name': 'Hezoua', 'governorate': 'Tozeur', 'lat': 33.7667, 'lng': 8.2500},
    
    # ═══════════════════════════════════════════════════════
    # KEBILI (6 délégations)
    # ═══════════════════════════════════════════════════════
    {'name': 'Kébili Sud', 'governorate': 'Kébili', 'lat': 33.7047, 'lng': 8.9694},
    {'name': 'Kébili Nord', 'governorate': 'Kébili', 'lat': 33.7167, 'lng': 8.9833},
    {'name': 'Souk Lahad', 'governorate': 'Kébili', 'lat': 33.5667, 'lng': 9.0333},
    {'name': 'Douz Nord', 'governorate': 'Kébili', 'lat': 33.4667, 'lng': 9.0333},
    {'name': 'Douz Sud', 'governorate': 'Kébili', 'lat': 33.4500, 'lng': 9.0167},
    {'name': 'Faouar', 'governorate': 'Kébili', 'lat': 33.6333, 'lng': 9.3667},
]


# Pour compatibilité avec l'ancien code
TUNISIA_CITIES = TUNISIA_DELEGATIONS

# ============================================================
# 📦 Place Categories Configuration
# ============================================================

PLACE_CATEGORIES = {
    'pharmacy': {
        'type': 'pharmacy',
        'keyword': 'pharmacie',
        'collection': 'pharmacies',
        'filename': 'pharmacies.json'
    },
    'on_call_pharmacy': {
        'type': 'pharmacy',
        'keyword': 'pharmacie de garde',
        'collection': 'on_call_pharmacies',
        'filename': 'on_call_pharmacies.json'
    },
    'night_pharmacy': {
        'type': 'pharmacy',
        'keyword': 'pharmacie de nuit',
        'collection': 'night_pharmacies',
        'filename': 'night_pharmacies.json'
    },
    'parapharmacy': {
        'type': 'store',
        'keyword': 'parapharmacie',
        'collection': 'parapharmacies',
        'filename': 'parapharmacies.json'
    },
    'clinic': {
        'type': 'hospital',
        'keyword': 'clinique',
        'collection': 'clinics',
        'filename': 'clinics.json'
    },
    'hospital': {
        'type': 'hospital',
        'keyword': 'hôpital',
        'collection': 'hospitals',
        'filename': 'hospitals.json'
    },
    'analysis_lab': {
        'type': 'health',
        'keyword': 'laboratoire d\'analyse',
        'collection': 'analysis_labs',
        'filename': 'analysis_labs.json'
    },
    'nurse': {
        'type': 'health',
        'keyword': 'infirmier',
        'collection': 'nurses',
        'filename': 'nurses.json'
    },
    'physiotherapy': {
        'type': 'physiotherapist',
        'keyword': 'kinésithérapie',
        'collection': 'physiotherapists',
        'filename': 'physiotherapists.json'
    },
    'doctor': {
        'type': 'doctor',
        'keyword': 'médecin',
        'collection': 'doctors',
        'filename': 'doctors.json',
        'use_text_search': True  # Utiliser Text Search
    }
}

# ============================================================
# 📁 Directory Configuration
# ============================================================

DATA_DIR = 'data'
LOG_DIR = 'logs'
LOG_FILE = 'medical_extractor.log'
LOG_LEVEL = 'INFO'

# ============================================================
# ⏰ Scheduler Configuration
# ============================================================

SCHEDULE_DAYS = 30  # Run every 30 days
SCHEDULE_TIME = "02:00"  # Run at 2 AM

# ============================================================
# 📊 Display Info
# ============================================================

print(f"✅ {len(TUNISIA_DELEGATIONS)} délégations chargées")

# Compter par gouvernorat
governorates = {}
for delegation in TUNISIA_DELEGATIONS:
    gov = delegation['governorate']
    governorates[gov] = governorates.get(gov, 0) + 1
ALL_GOVERNORATES = list(governorates.keys())
CHECKPOINT_DIR = "checkpoints"
EXTRACTION_CONFIG = {
    "search_radius": SEARCH_RADIUS,
    "schedule_days": SCHEDULE_DAYS,
    "schedule_time": SCHEDULE_TIME,
    "data_dir": DATA_DIR,
    "log_dir": LOG_DIR
}
print(f"   • {len(governorates)} gouvernorats")
print(f"   • {len(PLACE_CATEGORIES)} catégories")
