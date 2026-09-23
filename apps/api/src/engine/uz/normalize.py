"""O'zbek matn normalizatori. docs/05-uzbek-language.md.

TODO (1.3): raqam→so'z, sana, qisqartma, transliteratsiya.
"""
import re

OKINA = "ʻ"   # ʻ  (oʻ, gʻ)
TUTUQ = "ʼ"   # ʼ  (maʼno)

_OKINA_VARIANTS = re.compile(r"(?<=[oOgG])[\'‘’`ʻʼ]")
_TUTUQ_VARIANTS = re.compile(r"(?<=[^oOgG\s])[\'‘’`ʼ]")


def normalize_apostrophes(text: str) -> str:
    text = _OKINA_VARIANTS.sub(OKINA, text)
    text = _TUTUQ_VARIANTS.sub(TUTUQ, text)
    return text


def number_to_words(n: int) -> str:
    raise NotImplementedError("1.3")


def to_tts_text(text: str) -> str:
    """Raqamlar so'z bilan, qisqartmalar ochiq, chet so'zlar transliteratsiya."""
    return normalize_apostrophes(text)
