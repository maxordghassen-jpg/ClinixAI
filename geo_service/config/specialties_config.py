"""
Configuration complète des spécialités médicales
Pour optimiser la recherche avec Text Search API
"""

# ============================================================
# 🎯 Configuration Text Search pour médecins
# ============================================================

MEDICAL_SPECIALTIES_CONFIG = [
    # Spécialités primaires (très courantes)
    {
        'query': 'pédiatre',
        'specialty': 'Pédiatre',
        'priority': 1,
        'variations': ['pediatre', 'pédiatrie', 'pediatrie', 'enfant']
    },
    {
        'query': 'cardiologue',
        'specialty': 'Cardiologue',
        'priority': 1,
        'variations': ['cardiologie', 'cardiaque', 'coeur']
    },
    {
        'query': 'gynécologue',
        'specialty': 'Gynécologue',
        'priority': 1,
        'variations': ['gynecologie', 'gynécologie', 'femme']
    },
    {
        'query': 'dermatologue',
        'specialty': 'Dermatologue',
        'priority': 1,
        'variations': ['dermatologie', 'dermatolog', 'peau']
    },
    {
        'query': 'dentiste',
        'specialty': 'Dentiste',
        'priority': 1,
        'variations': ['dentaire', 'dent', 'dental', 'chirurgien dentiste']
    },
    {
        'query': 'ophtalmologue',
        'specialty': 'Ophtalmologue',
        'priority': 1,
        'variations': ['ophtalmologie', 'ophtalmo', 'oeil', 'yeux']
    },
    {
        'query': 'ORL',
        'specialty': 'ORL',
        'priority': 1,
        'variations': ['oto-rhino', 'otorhinolaryngolog', 'nez', 'gorge', 'oreille']
    },
    {
        'query': 'médecin généraliste',
        'specialty': 'Généraliste',
        'priority': 1,
        'variations': ['generaliste', 'médecine générale', 'omnipraticien']
    },
    
    # Spécialités secondaires (communes)
    {
        'query': 'orthopédiste',
        'specialty': 'Orthopédiste',
        'priority': 2,
        'variations': ['orthopédie', 'orthoped']
    },
    {
        'query': 'neurologue',
        'specialty': 'Neurologue',
        'priority': 2,
        'variations': ['neurologie', 'neurolog', 'neuro']
    },
    {
        'query': 'psychiatre',
        'specialty': 'Psychiatre',
        'priority': 2,
        'variations': ['psychiatrie', 'psychiatr']
    },
    {
        'query': 'radiologue',
        'specialty': 'Radiologue',
        'priority': 2,
        'variations': ['radiologie', 'radiolog', 'imagerie']
    },
    {
        'query': 'pneumologue',
        'specialty': 'Pneumologue',
        'priority': 2,
        'variations': ['pneumologie', 'pneumolog', 'poumon']
    },
    {
        'query': 'gastro-entérologue',
        'specialty': 'Gastro-entérologue',
        'priority': 2,
        'variations': ['gastro', 'entérologue', 'gastroenterolog', 'digestif']
    },
    {
        'query': 'endocrinologue',
        'specialty': 'Endocrinologue',
        'priority': 2,
        'variations': ['endocrinologie', 'endocrinolog', 'diabète', 'hormone']
    },
    {
        'query': 'rhumatologue',
        'specialty': 'Rhumatologue',
        'priority': 2,
        'variations': ['rhumatologie', 'rhumatolog', 'articulation']
    },
    {
        'query': 'urologue',
        'specialty': 'Urologue',
        'priority': 2,
        'variations': ['urologie', 'urolog']
    },
    
    # Spécialités chirurgicales
    {
        'query': 'chirurgien',
        'specialty': 'Chirurgien',
        'priority': 3,
        'variations': ['chirurgie', 'chirurg']
    },
    {
        'query': 'anesthésiste',
        'specialty': 'Anesthésiste',
        'priority': 3,
        'variations': ['anesthésie', 'anesthes', 'réanimation']
    },
    
    # Spécialités tertiaires (moins courantes mais importantes)
    {
        'query': 'néphrologue',
        'specialty': 'Néphrologue',
        'priority': 3,
        'variations': ['néphrologie', 'nephro', 'rein']
    },
    {
        'query': 'hématologue',
        'specialty': 'Hématologue',
        'priority': 3,
        'variations': ['hématologie', 'hemato', 'sang']
    },
    {
        'query': 'oncologue',
        'specialty': 'Oncologue',
        'priority': 3,
        'variations': ['oncologie', 'cancer', 'cancérolog']
    },
    {
        'query': 'allergologue',
        'specialty': 'Allergologue',
        'priority': 3,
        'variations': ['allergologie', 'allergie']
    },
    {
        'query': 'gériatre',
        'specialty': 'Gériatre',
        'priority': 3,
        'variations': ['gériatrie', 'personne agée']
    },
    
    # Fallback général
    {
        'query': 'docteur',
        'specialty': None,  # Ne pas assigner de spécialité
        'priority': 4,
        'variations': ['dr', 'médecin']
    }
]


# ============================================================
# 🔍 Mots-clés pour extraction depuis nom/texte
# ============================================================

SPECIALTY_KEYWORDS_MAPPING = {
    'Pédiatre': ['pédiatre', 'pediatre', 'pédiatrie', 'pediatrie', 'enfant'],
    'Cardiologue': ['cardiologue', 'cardiologie', 'coeur', 'cardiaque', 'cardiovasculaire'],
    'Dentiste': ['dentiste', 'dentaire', 'dent', 'dental', 'chirurgien dentiste', 'stomatolog'],
    'Dermatologue': ['dermatologue', 'dermatologie', 'dermatolog', 'peau', 'cutané'],
    'Gynécologue': ['gynécologue', 'gynécologie', 'gynecolog', 'femme', 'obstétri'],
    'Ophtalmologue': ['ophtalmologue', 'ophtalmologie', 'ophtalmo', 'oeil', 'yeux', 'vision'],
    'ORL': ['orl', 'oto-rhino', 'otorhinolaryngolog', 'nez', 'gorge', 'oreille'],
    'Orthopédiste': ['orthopédiste', 'orthopédie', 'orthoped', 'traumatolog'],
    'Urologue': ['urologue', 'urologie', 'urolog', 'prostate'],
    'Neurologue': ['neurologue', 'neurologie', 'neurolog', 'neuro', 'cerveau'],
    'Psychiatre': ['psychiatre', 'psychiatrie', 'psychiatr', 'psychothérap'],
    'Radiologue': ['radiologue', 'radiologie', 'radiolog', 'imagerie', 'scanner'],
    'Généraliste': ['généraliste', 'médecine générale', 'generaliste', 'omnipraticien'],
    'Pneumologue': ['pneumologue', 'pneumologie', 'pneumolog', 'poumon', 'respiratoire'],
    'Gastro-entérologue': ['gastro', 'entérologue', 'gastroenterolog', 'digestif', 'intestin'],
    'Endocrinologue': ['endocrinologue', 'endocrinologie', 'endocrinolog', 'diabète', 'hormone', 'thyroïde'],
    'Rhumatologue': ['rhumatologue', 'rhumatologie', 'rhumatolog', 'articulation', 'arthrite'],
    'Anesthésiste': ['anesthésiste', 'anesthésie', 'anesthes', 'réanimation'],
    'Chirurgien': ['chirurgien', 'chirurgie', 'chirurg'],
    'Néphrologue': ['néphrologue', 'néphrologie', 'nephro', 'rein', 'dialyse'],
    'Hématologue': ['hématologue', 'hématologie', 'hemato', 'sang'],
    'Oncologue': ['oncologue', 'oncologie', 'cancer', 'cancérolog', 'tumeur'],
    'Allergologue': ['allergologue', 'allergologie', 'allergie', 'immunolog'],
    'Gériatre': ['gériatre', 'gériatrie', 'personne agée', 'vieillissement'],
    'Kinésithérapeute': ['kinésithérapeute', 'kiné', 'physiothérap', 'rééducation'],
    'Sage-femme': ['sage-femme', 'maïeuticien', 'accouchement'],
    'Nutritionniste': ['nutritionniste', 'nutrition', 'diététicien', 'régime'],
    'Psychologue': ['psychologue', 'psychologie', 'thérapie']
}


# ============================================================
# 📊 Configuration pour génération de rapports
# ============================================================

SPECIALTY_GROUPS = {
    'Médecine Générale': ['Généraliste'],
    'Pédiatrie': ['Pédiatre'],
    'Chirurgie': ['Chirurgien', 'Anesthésiste', 'Orthopédiste'],
    'Médecine Interne': ['Cardiologue', 'Pneumologue', 'Gastro-entérologue', 
                         'Endocrinologue', 'Rhumatologue', 'Néphrologue', 'Hématologue'],
    'Spécialités Sensorielles': ['Ophtalmologue', 'ORL'],
    'Santé Mentale': ['Psychiatre', 'Psychologue'],
    'Soins de la Peau': ['Dermatologue'],
    'Santé des Femmes': ['Gynécologue', 'Sage-femme'],
    'Dentisterie': ['Dentiste'],
    'Urologie': ['Urologue'],
    'Oncologie': ['Oncologue'],
    'Imagerie': ['Radiologue'],
    'Rééducation': ['Kinésithérapeute'],
    'Nutrition': ['Nutritionniste'],
    'Allergologie': ['Allergologue'],
    'Gériatrie': ['Gériatre']
}


# ============================================================
# ⚙️ Paramètres de recherche
# ============================================================

SEARCH_CONFIG = {
    # Rechercher uniquement les spécialités prioritaires (priorité 1 et 2)
    'search_priority_only': False,  # Si True, recherche seulement priorité 1 et 2
    
    # Délai entre recherches (en secondes)
    'delay_between_searches': 0.3,
    
    # Nombre max de résultats par spécialité par ville
    'max_results_per_specialty': 60,
    
    # Activer recherche fallback (docteur, médecin)
    'enable_fallback_search': True
}


def get_specialties_to_search(priority_only=False):
    """
    Retourne la liste des spécialités à rechercher
    """
    if priority_only:
        return [s for s in MEDICAL_SPECIALTIES_CONFIG if s['priority'] <= 2]
    return MEDICAL_SPECIALTIES_CONFIG


def get_specialty_display_name(specialty_code):
    """
    Retourne le nom d'affichage d'une spécialité
    """
    for spec_config in MEDICAL_SPECIALTIES_CONFIG:
        if spec_config['specialty'] == specialty_code:
            return spec_config['specialty']
    return specialty_code