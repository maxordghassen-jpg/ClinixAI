import re
import unicodedata
from difflib import get_close_matches


class SpecialtyNormalizer:
    """Deterministic specialty normalizer.

    Converts any LLM-extracted specialty string — regardless of language,
    script, or spelling variant — into the canonical French label stored in
    the geo_service `doctors` collection (e.g. "Pédiatre", "Cardiologue").

    Resolution order (first match wins):
      1. Exact lowercase lookup in SPECIALTY_FR_MAP
      2. Accent-stripped exact lookup (handles "pédiatre" → "pediatre" match)
      3. Word-boundary substring scan (handles "cardiologist near me")
      4. Fuzzy match on accent-stripped keys via difflib (handles LLM typos
         and cross-script transliterations like "pediatre", "pédiatrе")

    Returns the input unchanged only when all four passes fail, so the
    geo-service still receives something meaningful as a fallback.
    """

    # Canonical map: every key is lowercase.  All known aliases for a
    # specialty map to a single canonical French label.
    SPECIALTY_FR_MAP: dict[str, str] = {
        # ── Cardiology ────────────────────────────────────────────────────────
        "cardiologist":          "Cardiologue",
        "cardiology":            "Cardiologue",
        "heart doctor":          "Cardiologue",
        "قلب":                   "Cardiologue",
        "طبيب قلب":              "Cardiologue",
        "أمراض قلب":             "Cardiologue",
        "cardiologue":           "Cardiologue",

        # ── Neurology ─────────────────────────────────────────────────────────
        "neurologist":           "Neurologue",
        "neurology":             "Neurologue",
        "brain doctor":          "Neurologue",
        "أعصاب":                 "Neurologue",
        "طبيب أعصاب":            "Neurologue",
        "neurologue":            "Neurologue",

        # ── Dermatology ───────────────────────────────────────────────────────
        "dermatologist":         "Dermatologue",
        "dermatology":           "Dermatologue",
        "skin doctor":           "Dermatologue",
        "جلدية":                 "Dermatologue",
        "طبيب جلدية":            "Dermatologue",
        "dermatologue":          "Dermatologue",

        # ── Pediatrics ────────────────────────────────────────────────────────
        "pediatrician":          "Pédiatre",
        "pediatrics":            "Pédiatre",
        "paediatrician":         "Pédiatre",
        "paediatrics":           "Pédiatre",
        "pediatre":              "Pédiatre",   # unaccented LLM variant
        "pédiatre":              "Pédiatre",
        "pédiatrie":             "Pédiatre",
        "pediadtre":             "Pédiatre",   # common typo
        "child doctor":          "Pédiatre",
        "children doctor":       "Pédiatre",
        "doctor for children":   "Pédiatre",
        "kids doctor":           "Pédiatre",
        "baby doctor":           "Pédiatre",
        # Arabic
        "أطفال":                 "Pédiatre",
        "طب أطفال":              "Pédiatre",
        "طبيب أطفال":            "Pédiatre",
        "دكتور أطفال":           "Pédiatre",
        "متخصص أطفال":           "Pédiatre",
        "أمراض الأطفال":         "Pédiatre",
        # Persian / Farsi (LLM may return these for Arabic input)
        "پدیاتری":               "Pédiatre",
        "پدیاتریست":             "Pédiatre",
        "طفل":                   "Pédiatre",

        # ── Gynecology ────────────────────────────────────────────────────────
        "gynecologist":          "Gynécologue",
        "gynaecologist":         "Gynécologue",
        "gynecology":            "Gynécologue",
        "gynaecology":           "Gynécologue",
        "gynécologue":           "Gynécologue",
        "نساء":                  "Gynécologue",
        "طبيب نساء":             "Gynécologue",
        "أمراض نساء":            "Gynécologue",
        "توليد":                 "Gynécologue",

        # ── Ophthalmology ─────────────────────────────────────────────────────
        "ophthalmologist":       "Ophtalmologue",
        "ophthalmology":         "Ophtalmologue",
        "eye doctor":            "Ophtalmologue",
        "ophtalmologue":         "Ophtalmologue",
        "عيون":                  "Ophtalmologue",
        "طبيب عيون":             "Ophtalmologue",
        "أمراض عيون":            "Ophtalmologue",

        # ── ENT ───────────────────────────────────────────────────────────────
        "ent":                   "ORL",
        "otolaryngologist":      "ORL",
        "ear nose throat":       "ORL",
        "ear doctor":            "ORL",
        "orl":                   "ORL",
        "أنف وأذن":              "ORL",
        "أنف وأذن وحنجرة":       "ORL",
        "طبيب أنف":              "ORL",

        # ── Orthopedics ───────────────────────────────────────────────────────
        "orthopedist":           "Orthopédiste",
        "orthopedics":           "Orthopédiste",
        "orthopaedist":          "Orthopédiste",
        "orthopaedics":          "Orthopédiste",
        "bone doctor":           "Orthopédiste",
        "orthopediste":          "Orthopédiste",   # unaccented
        "orthopédiste":          "Orthopédiste",
        "عظام":                  "Orthopédiste",
        "طبيب عظام":             "Orthopédiste",

        # ── Gastroenterology ──────────────────────────────────────────────────
        "gastroenterologist":    "Gastro-entérologue",
        "gastroenterology":      "Gastro-entérologue",
        "gastro":                "Gastro-entérologue",
        "digestive doctor":      "Gastro-entérologue",
        "gastro-entérologue":    "Gastro-entérologue",
        "gastro-enterologue":    "Gastro-entérologue",   # unaccented
        "جهاز هضمي":             "Gastro-entérologue",
        "معدة":                  "Gastro-entérologue",

        # ── Endocrinology ─────────────────────────────────────────────────────
        "endocrinologist":       "Endocrinologue",
        "endocrinology":         "Endocrinologue",
        "diabetes doctor":       "Endocrinologue",
        "endocrinologue":        "Endocrinologue",
        "غدد":                   "Endocrinologue",
        "سكري":                  "Endocrinologue",

        # ── Pulmonology ───────────────────────────────────────────────────────
        "pulmonologist":         "Pneumologue",
        "pulmonology":           "Pneumologue",
        "pneumologist":          "Pneumologue",
        "lung doctor":           "Pneumologue",
        "pneumologue":           "Pneumologue",
        "رئة":                   "Pneumologue",
        "طبيب رئة":              "Pneumologue",

        # ── Nephrology ────────────────────────────────────────────────────────
        "nephrologist":          "Néphrologue",
        "nephrology":            "Néphrologue",
        "kidney doctor":         "Néphrologue",
        "nephrologue":           "Néphrologue",
        "كلى":                   "Néphrologue",
        "طبيب كلى":              "Néphrologue",

        # ── Hematology ────────────────────────────────────────────────────────
        "hematologist":          "Hématologue",
        "hematology":            "Hématologue",
        "haematologist":         "Hématologue",
        "haematology":           "Hématologue",
        "hematologue":           "Hématologue",

        # ── Oncology ──────────────────────────────────────────────────────────
        "oncologist":            "Oncologue",
        "oncology":              "Oncologue",
        "cancer doctor":         "Oncologue",
        "oncologue":             "Oncologue",
        "أورام":                 "Oncologue",

        # ── Psychiatry ────────────────────────────────────────────────────────
        "psychiatrist":          "Psychiatre",
        "psychiatry":            "Psychiatre",
        "mental health doctor":  "Psychiatre",
        "psychiatre":            "Psychiatre",
        "نفسية":                 "Psychiatre",
        "طبيب نفسي":             "Psychiatre",
        "أمراض نفسية":           "Psychiatre",

        # ── Rheumatology ─────────────────────────────────────────────────────
        "rheumatologist":        "Rhumatologue",
        "rheumatology":          "Rhumatologue",
        "joint doctor":          "Rhumatologue",
        "rhumatologue":          "Rhumatologue",
        "روماتيزم":              "Rhumatologue",
        "مفاصل":                 "Rhumatologue",

        # ── Radiology ─────────────────────────────────────────────────────────
        "radiologist":           "Radiologue",
        "radiology":             "Radiologue",
        "radiologue":            "Radiologue",

        # ── Urology ───────────────────────────────────────────────────────────
        "urologist":             "Urologue",
        "urology":               "Urologue",
        "urologue":              "Urologue",
        "بول":                   "Urologue",
        "طبيب بول":              "Urologue",
        "مسالك بولية":           "Urologue",

        # ── Anesthesiology ────────────────────────────────────────────────────
        "anesthesiologist":      "Anesthésiste",
        "anesthesiology":        "Anesthésiste",
        "anaesthesiologist":     "Anesthésiste",
        "anesthesiste":          "Anesthésiste",

        # ── Surgery ───────────────────────────────────────────────────────────
        "surgeon":               "Chirurgien",
        "surgery":               "Chirurgien",
        "chirurgien":            "Chirurgien",
        "جراح":                  "Chirurgien",

        # ── Allergology ───────────────────────────────────────────────────────
        "allergist":             "Allergologue",
        "allergology":           "Allergologue",
        "allergy doctor":        "Allergologue",
        "allergologue":          "Allergologue",
        "حساسية":                "Allergologue",

        # ── Geriatrics ────────────────────────────────────────────────────────
        "geriatrician":          "Gériatre",
        "geriatrics":            "Gériatre",
        "elderly doctor":        "Gériatre",
        "geriatre":              "Gériatre",

        # ── General practice ──────────────────────────────────────────────────
        "general practitioner":  "Généraliste",
        "general practice":      "Généraliste",
        "gp":                    "Généraliste",
        "family doctor":         "Généraliste",
        "generaliste":           "Généraliste",   # unaccented
        "généraliste":           "Généraliste",
        "medecin generaliste":   "Généraliste",
        "médecin généraliste":   "Généraliste",
        "عام":                   "Généraliste",
        "طبيب عام":              "Généraliste",
        "طب عام":                "Généraliste",

        # ── Dentistry ────────────────────────────────────────────────────────
        "dentist":               "Dentiste",
        "dentistry":             "Dentiste",
        "dental doctor":         "Dentiste",
        "dentiste":              "Dentiste",
        "أسنان":                 "Dentiste",
        "طبيب أسنان":            "Dentiste",
        "طب أسنان":              "Dentiste",
    }

    # Longest keys first: multi-word phrases ("general practitioner") must be
    # tried before single-word substrings ("gp", "practitioner").
    _KEYS_BY_LENGTH = sorted(SPECIALTY_FR_MAP, key=len, reverse=True)

    # Accent-stripped index built once at class definition time.
    # Maps stripped_key → canonical French value.  Used by pass 2 and pass 4.
    _STRIPPED_INDEX: dict[str, str] = {}

    @staticmethod
    def _strip_accents(text: str) -> str:
        """Remove combining diacritical marks so "pédiatre" == "pediatre"."""
        return "".join(
            c for c in unicodedata.normalize("NFD", text)
            if unicodedata.category(c) != "Mn"
        )

    @classmethod
    def normalize(cls, specialty: str | None) -> str | None:
        """Return the canonical French specialty label.

        Logs: raw input, which pass matched, and the canonical result.
        Returns the input unchanged only when all four passes fail.
        """
        if not specialty:
            return specialty

        lowered = specialty.lower().strip()

        # ── Pass 1: exact match ───────────────────────────────────────────────
        result = cls.SPECIALTY_FR_MAP.get(lowered)
        if result:
            return result

        # ── Pass 2: accent-stripped exact match ───────────────────────────────
        stripped_input = cls._strip_accents(lowered)
        if not cls._STRIPPED_INDEX:
            cls._STRIPPED_INDEX = {
                cls._strip_accents(k): v
                for k, v in cls.SPECIALTY_FR_MAP.items()
            }
        result = cls._STRIPPED_INDEX.get(stripped_input)
        if result:
            return result

        # ── Pass 3: word-boundary substring scan ─────────────────────────────
        for keyword in cls._KEYS_BY_LENGTH:
            if re.search(rf"\b{re.escape(keyword)}\b", lowered):
                return cls.SPECIALTY_FR_MAP[keyword]

        # ── Pass 4: fuzzy match on accent-stripped keys ───────────────────────
        # Handles LLM typos and cross-script transliterations that are close
        # but not identical (e.g. "pediatre" → "pediatrician").
        # cutoff=0.72 is conservative enough to avoid false positives between
        # distinct specialties.
        candidates = list(cls._STRIPPED_INDEX.keys())
        matches = get_close_matches(stripped_input, candidates, n=1, cutoff=0.72)
        if matches:
            return cls._STRIPPED_INDEX[matches[0]]

        return specialty

    @classmethod
    def normalize_with_log(cls, specialty: str | None) -> tuple[str | None, str]:
        """Return (canonical, log_line) for debug tracing at call sites."""
        if not specialty:
            return specialty, f"raw={specialty!r} -> unchanged (empty)"

        canonical = cls.normalize(specialty)
        changed   = canonical != specialty
        log = (
            f"raw={specialty!r} -> canonical={canonical!r}"
            + (" [normalized]" if changed else " [passthrough]")
        )
        return canonical, log
