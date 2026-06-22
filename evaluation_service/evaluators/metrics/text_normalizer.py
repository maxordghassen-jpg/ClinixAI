"""
Safe text normalisation for NLP surface-overlap metrics (ROUGE / BLEU / EM / ESM).

Design principles:
  - PRESERVE words and multilingual tokens — do NOT strip Arabic/French/accents
  - Only remove punctuation and formatting noise that breaks tokenisation
  - Never destroy meaningful text content

What this normalizer DOES:
  1. Lowercase
  2. Replace common Unicode punctuation variants (curly quotes, em-dash) with ASCII
  3. Remove bullet-point / numbered-list markers at line starts
  4. Strip punctuation characters (keeping letters, digits, spaces in all scripts)
  5. Collapse whitespace

What this normalizer does NOT do:
  - Does NOT transliterate Arabic / Hebrew / CJK characters
  - Does NOT strip accented Latin characters (é, à, ç etc. are preserved as-is)
  - Does NOT remove non-ASCII characters
  - Does NOT apply stemming or lemmatisation (that is the ROUGE scorer's job)
"""

import re
import unicodedata


# Punctuation characters to strip (safe across scripts)
# Keep: letters (any script), digits, spaces
# Remove: ASCII punctuation + common Unicode punctuation
_PUNCT_PAT = re.compile(
    r'[!"#$%&\'()*+,\-./:;<=>?@\[\\\]^_`{|}~'   # ASCII punctuation
    r'‘’“”'                   # curly quotes
    r'–—'                               # en/em dash
    r'•‣…'                         # bullets, ellipsis
    r'،؛؟'                         # Arabic punctuation
    r']',
    re.UNICODE,
)

# Bullet/numbered-list prefix at line start
_BULLET_PAT = re.compile(r'(?m)^\s*(?:\d+[.)]\s*|[-•*·]\s+)', re.UNICODE)


def normalize(text: str) -> str:
    """
    Normalize text for surface-overlap metrics.

    Preserves all script characters (Arabic, French, etc.).
    Removes only punctuation and formatting noise.
    """
    if not text:
        return ""

    # 1. Lowercase (works correctly for all Unicode scripts)
    text = text.lower()

    # 2. Remove list markers at line starts  (1. 2. • - *)
    text = _BULLET_PAT.sub(" ", text)

    # 3. Replace common typographic variants with ASCII
    text = (
        text
        .replace("‘", "'")   # left single quote
        .replace("’", "'")   # right single quote (apostrophe)
        .replace("“", '"')   # left double quote
        .replace("”", '"')   # right double quote
        .replace("–", "-")   # en-dash
        .replace("—", "-")   # em-dash
        .replace("…", " ")   # ellipsis
        .replace(" ", " ")   # non-breaking space
        .replace("\t", " ")       # tab
    )

    # 4. Strip punctuation (preserves letters and digits from ANY Unicode block)
    text = _PUNCT_PAT.sub(" ", text)

    # 5. Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()

    return text


def normalize_pair(candidate: str, reference: str) -> tuple[str, str]:
    """Normalize a candidate/reference pair."""
    return normalize(candidate), normalize(reference)


def normalize_multi(
    candidate: str,
    references: list[str],
) -> tuple[str, list[str]]:
    """Normalize candidate and all references, skipping empty strings."""
    return normalize(candidate), [normalize(r) for r in references if r]
