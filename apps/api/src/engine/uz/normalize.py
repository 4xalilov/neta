"""O'zbek (lotin) matn normalizatori — TTS va subtitr uchun.

Qoidalar: docs/05-uzbek-language.md. Testlar: tests/test_uz_normalize.py.

Modul sof Python: tashqi kutubxona yo'q, ``engine.settings`` import qilinmaydi —
shuning uchun testlar muhit o'zgaruvchilarisiz ishlaydi.
"""
import re
import textwrap

OKINA = "ʻ"   # U+02BB — oʻ, gʻ (til orqa unlisi)
TUTUQ = "ʼ"   # U+02BC — maʼno, sheʼr (tutuq/hamza belgisi)

# ---------------------------------------------------------------------------
# 1. Apostrof normalizatsiyasi
# ---------------------------------------------------------------------------

# o/g dan keyin kelgan har qanday apostrof-variant -> OKINA.
_OKINA_VARIANTS = re.compile(r"(?<=[oOgG])['‘’`ʻʼ]")
# o/g dan boshqa harf/raqamdan keyin kelgan apostrof-variant -> TUTUQ.
_TUTUQ_VARIANTS = re.compile(r"(?<=[^oOgG\s])['‘’`ʼ]")

# Bitta so'z yoki ibora atrofidagi tik tirnoq — iqtibos/qo'shtirnoq sifatida
# ishlatilgan: 'salom' kabi. Ochilish belgisi so'z boshida (yoki bo'shliqdan
# keyin), yopilish belgisi so'z oxirida (yoki bo'shliqdan oldin) bo'lishi kerak —
# shunda ular oʻ/ʼ ga aylanmay, tirnoq bo'lib qoladi.
_QUOTE_PHRASE = re.compile(r"(?<!\w)(['`‘’])([^'`‘’\n]{1,120}?)\1(?!\w)")


def _apply_okina_tutuq(text: str) -> str:
    text = _OKINA_VARIANTS.sub(OKINA, text)
    text = _TUTUQ_VARIANTS.sub(TUTUQ, text)
    return text


def normalize_apostrophes(text: str) -> str:
    """Apostrof variantlarini ichki standartga keltiradi.

    - ``o' g' o` g` o‘ g‘`` -> ``oʻ gʻ`` (OKINA, U+02BB)
    - so'z ichidagi boshqa apostrof -> ``ʼ`` (TUTUQ, U+02BC), masalan ``ma'no`` -> ``maʼno``
    - ``'salom'`` kabi so'z/ibora atrofidagi tik tirnoq — tirnoq bo'lib qoladi
    """
    # Tirnoq sifatida ishlatilgan juftliklarni vaqtincha ajratib olamiz —
    # aks holda pastdagi umumiy o'tish ularni ham oʻ/ʼ ga aylantirib qo'yadi.
    quoted: list[str] = []

    def _stash_quote(m: re.Match) -> str:
        inner = _apply_okina_tutuq(m.group(2))
        quoted.append(f"'{inner}'")
        return f"\0Q{len(quoted) - 1}\0"

    text = _QUOTE_PHRASE.sub(_stash_quote, text)
    text = _apply_okina_tutuq(text)
    for i, phrase in enumerate(quoted):
        text = text.replace(f"\0Q{i}\0", phrase)
    return text


# ---------------------------------------------------------------------------
# 2. Raqam -> so'z
# ---------------------------------------------------------------------------

_ONES = [
    "nol", "bir", "ikki", "uch", "toʻrt", "besh",
    "olti", "yetti", "sakkiz", "toʻqqiz",
]
_TENS_WORDS = {
    1: "oʻn", 2: "yigirma", 3: "oʻttiz", 4: "qirq", 5: "ellik",
    6: "oltmish", 7: "yetmish", 8: "sakson", 9: "toʻqson",
}
_SCALES = [("milliard", 10**9), ("million", 10**6), ("ming", 10**3)]

MONTHS = [
    "yanvar", "fevral", "mart", "aprel", "may", "iyun",
    "iyul", "avgust", "sentyabr", "oktyabr", "noyabr", "dekabr",
]

_MAX_NUMBER = 999_999_999_999


def _three_digit_words(n: int) -> list[str]:
    """0..999 oralig'idagi sonni so'zlarga ajratadi (yordamchi funksiya)."""
    parts: list[str] = []
    h, r = divmod(n, 100)
    if h:
        parts.append(_ONES[h])
        parts.append("yuz")
    t, o = divmod(r, 10)
    if t:
        parts.append(_TENS_WORDS[t])
    if o:
        parts.append(_ONES[o])
    return parts


def number_to_words(n: int) -> str:
    """Butun sonni o'zbekcha so'zga o'giradi (0 ... 999 999 999 999, manfiy ham)."""
    if n == 0:
        return "nol"
    neg = n < 0
    value = abs(n)
    if value > _MAX_NUMBER:
        raise ValueError(f"number_to_words: {n} qo'llab-quvvatlanadigan chegaradan katta")

    groups: list[str] = []
    remaining = value
    for name, scale in _SCALES:
        group_value, remaining = divmod(remaining, scale)
        if group_value:
            groups.extend(_three_digit_words(group_value))
            groups.append(name)
    if remaining or not groups:
        groups.extend(_three_digit_words(remaining))

    result = " ".join(groups)
    return f"minus {result}" if neg else result


_VOWELS = set("aeiou")


def ordinal_to_words(n: int) -> str:
    """Tartib son so'zi: -inchi (undoshdan keyin) yoki -nchi (unlidan keyin)."""
    words = number_to_words(n).split(" ")
    # "bir yuz" -> "yuzinchi", "bir ming" -> "minginchi" (yaxlit yuzlik/minglikda
    # "bir" tartib songa qo'shilmaydi).
    if len(words) == 2 and words[0] == "bir":
        words = [words[1]]
    last = words[-1]
    suffix = "nchi" if last[-1] in _VOWELS else "inchi"
    words[-1] = last + suffix
    return " ".join(words)


_DECIMAL_RE = re.compile(r"(-?\d+)[.,](\d+)")


def decimal_to_words(s: str) -> str:
    """O'nli kasr: "3,5"/"3.5" -> "uch butun besh"."""
    m = _DECIMAL_RE.fullmatch(s.strip())
    if not m:
        raise ValueError(f"decimal_to_words: {s!r} o'nli kasr emas")
    whole, frac = m.groups()
    return f"{number_to_words(int(whole))} butun {number_to_words(int(frac))}"


def _digits_from_grouped(s: str) -> int:
    """"1 500 000" / "1.500.000" / "1ʼ500ʼ000" -> 1500000 (guruh ajratkichlarini olib tashlaydi)."""
    s = s.strip()
    neg = s.startswith("-")
    if neg:
        s = s[1:]
    cleaned = re.sub(r"[ .,ʼ]", "", s)
    val = int(cleaned) if cleaned else 0
    return -val if neg else val


# ---------------------------------------------------------------------------
# 3. Qisqartmalar
# ---------------------------------------------------------------------------

ABBREVIATIONS: dict[str, str] = {
    "va h.k.": "va hokazo",
    "h.k.": "hokazo",
    "t.r.": "telefon raqami",
    "m-n": "million",
    "mln": "million",
    "mlrd": "milliard",
    "kg": "kilogramm",
    "km": "kilometr",
    "sm": "santimetr",
    "IT": "ay-ti",
    "SMM": "es-em-em",
    "CRM": "si-ar-em",
    "USD": "dollar",
    "UZS": "soʻm",
    "dr.": "doktor",
    "prof.": "professor",
    "koʻch.": "koʻchasi",
    "tel.": "telefon",
}


def _build_abbrev_pattern(mapping: dict[str, str]) -> re.Pattern:
    keys = sorted(mapping.keys(), key=len, reverse=True)
    parts = []
    for key in keys:
        escaped = re.escape(key)
        if key.endswith("."):
            parts.append(rf"\b{escaped}")
        else:
            parts.append(rf"\b{escaped}\b")
    return re.compile("|".join(parts))


def _expand_abbreviations(text: str, *, ai_reading: str) -> str:
    mapping = dict(ABBREVIATIONS)
    mapping["AI"] = ai_reading
    pattern = _build_abbrev_pattern(mapping)

    def repl(m: re.Match) -> str:
        return mapping[m.group(0)]

    return pattern.sub(repl, text)


# ---------------------------------------------------------------------------
# 4. Sanalar
# ---------------------------------------------------------------------------

_MONTH_ALT = "|".join(MONTHS)
_DATE_DMY_RE = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b")
_DATE_YEAR_RE = re.compile(r"\b(\d{3,4})-yil\b")
_DATE_DAY_MONTH_RE = re.compile(rf"\b(\d{{1,2}})[-\s]({_MONTH_ALT})\b")


def _date_dmy_repl(m: re.Match) -> str:
    day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
    month_name = MONTHS[month - 1] if 1 <= month <= 12 else str(month)
    return f"{ordinal_to_words(day)} {month_name} {ordinal_to_words(year)} yil"


def _convert_dates(text: str) -> str:
    text = _DATE_DMY_RE.sub(_date_dmy_repl, text)
    text = _DATE_YEAR_RE.sub(lambda m: f"{ordinal_to_words(int(m.group(1)))} yil", text)
    text = _DATE_DAY_MONTH_RE.sub(
        lambda m: f"{ordinal_to_words(int(m.group(1)))} {m.group(2)}", text
    )
    return text


# ---------------------------------------------------------------------------
# 5. Foiz / valyuta / vaqt / telefon
# ---------------------------------------------------------------------------

_PHONE_RE = re.compile(r"\+(\d+)((?:\s+\d+)+)")


def _phone_repl(m: re.Match) -> str:
    groups = [m.group(1), *m.group(2).split()]
    words = [number_to_words(int(g)) for g in groups]
    return "plyus " + ", ".join(words)


_TIME_RE = re.compile(r"(?i)(soat\s+)?\b(\d{1,2}):(\d{2})\b")


def _time_repl(m: re.Match) -> str:
    soat_prefix, hh, mm = m.group(1), m.group(2), m.group(3)
    hour_words = number_to_words(int(hh))
    prefix = f"{soat_prefix.strip()} " if soat_prefix else ""
    if mm == "00":
        return f"{prefix}{hour_words}" if soat_prefix else f"{hour_words} nol nol"
    return f"{prefix}{hour_words} {number_to_words(int(mm))}"


_PERCENT_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*%")


def _percent_repl(m: re.Match) -> str:
    num = m.group(1)
    words = decimal_to_words(num) if re.search(r"[.,]", num) else number_to_words(int(num))
    return f"{words} foiz"


_DOLLAR_RE = re.compile(r"\$\s*(-?\d[\d .,ʼ]*)")


def _dollar_repl(m: re.Match) -> str:
    return f"{number_to_words(_digits_from_grouped(m.group(1)))} dollar"


_DECIMAL_SCALE_RE = re.compile(r"\b(-?\d+[.,]\d+)\s*(million|milliard)\b")


def _decimal_scale_repl(m: re.Match) -> str:
    return f"{decimal_to_words(m.group(1))} {m.group(2)}"


def _convert_currency_percent_time_phone(text: str) -> str:
    text = _PHONE_RE.sub(_phone_repl, text)
    text = _TIME_RE.sub(_time_repl, text)
    text = _PERCENT_RE.sub(_percent_repl, text)
    text = _DOLLAR_RE.sub(_dollar_repl, text)
    text = _DECIMAL_SCALE_RE.sub(_decimal_scale_repl, text)
    return text


# ---------------------------------------------------------------------------
# 6. Qolgan raqamlar, tartib sonlar, oraliqlar
# ---------------------------------------------------------------------------

_ORDINAL_CHI_RE = re.compile(r"\b(\d+)-chi\b")
_ORDINAL_DASH_RE = re.compile(r"\b(\d+)-(?=[^\W\d])")
_RANGE_RE = re.compile(r"\b(\d+)\s*-\s*(\d+)\b")
_GROUPED_THOUSANDS_RE = re.compile(r"(?<!\w)(-?\d{1,3}(?:[ .,ʼ]\d{3})+)(?!\w)")
_DECIMAL_TOKEN_RE = re.compile(r"\b(-?\d+[.,]\d{1,2})\b")
_PLAIN_INT_RE = re.compile(r"\b(-?\d+)\b")


def _convert_numbers_and_ordinals(text: str) -> str:
    text = _ORDINAL_CHI_RE.sub(lambda m: ordinal_to_words(int(m.group(1))), text)
    text = _ORDINAL_DASH_RE.sub(lambda m: ordinal_to_words(int(m.group(1))) + " ", text)
    text = _RANGE_RE.sub(
        lambda m: f"{number_to_words(int(m.group(1)))}dan {number_to_words(int(m.group(2)))}gacha",
        text,
    )
    text = _GROUPED_THOUSANDS_RE.sub(
        lambda m: number_to_words(_digits_from_grouped(m.group(1))), text
    )
    text = _DECIMAL_TOKEN_RE.sub(lambda m: decimal_to_words(m.group(1)), text)
    text = _PLAIN_INT_RE.sub(lambda m: number_to_words(int(m.group(1))), text)
    return text


# ---------------------------------------------------------------------------
# 7. Chet so'zlar transliteratsiyasi
# ---------------------------------------------------------------------------

FOREIGN_WORDS: dict[str, str] = {
    "reels": "Rils",
    "instagram": "Instagram",
    "tiktok": "Tik-Tok",
    "youtube": "Yutub",
    "telegram": "Telegram",
    "iphone": "Ayfon",
    "google": "Gugl",
    "whatsapp": "Votsap",
    "like": "layk",
    "story": "stori",
    "stories": "storis",
}

# Ruscha o'zlashma so'zlar: agar brand ruxsat bermasa (allow_russian=False),
# o'zbekcha muqobili bilan almashtiriladi. Kichik, kengaytiriladigan ro'yxat.
RUSSIAN_TO_UZBEK: dict[str, str] = {
    "skidka": "chegirma",
    "seychas": "hozir",
    "spasibo": "rahmat",
    "konechno": "albatta",
    "vazhno": "muhim",
}


def _translit_pattern(mapping: dict[str, str]) -> re.Pattern:
    keys = sorted(mapping.keys(), key=len, reverse=True)
    return re.compile(r"\b(" + "|".join(re.escape(k) for k in keys) + r")\b", re.IGNORECASE)


def _transliterate_foreign(text: str, *, extra_translit: dict[str, str] | None = None) -> str:
    mapping = dict(FOREIGN_WORDS)
    if extra_translit:
        mapping.update({k.lower(): v for k, v in extra_translit.items()})
    if not mapping:
        return text
    pattern = _translit_pattern(mapping)
    return pattern.sub(lambda m: mapping[m.group(0).lower()], text)


def _replace_russian_loanwords(text: str) -> str:
    if not RUSSIAN_TO_UZBEK:
        return text
    pattern = _translit_pattern(RUSSIAN_TO_UZBEK)
    return pattern.sub(lambda m: RUSSIAN_TO_UZBEK[m.group(0).lower()], text)


# ---------------------------------------------------------------------------
# 8. Bo'shliq tozalash
# ---------------------------------------------------------------------------

def _cleanup_whitespace(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" +([,.;:!?%])", r"\1", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ---------------------------------------------------------------------------
# 9. Orkestratsiya
# ---------------------------------------------------------------------------

def to_tts_text(
    text: str,
    *,
    ai_reading: str = "sunʼiy intellekt",
    extra_translit: dict[str, str] | None = None,
    allow_russian: bool = False,
) -> str:
    """TTS uchun to'liq normalizatsiya: apostrof -> qisqartma -> sana ->
    valyuta/foiz/vaqt/telefon -> raqam/tartib son -> transliteratsiya -> bo'shliq.

    Ikki marta ishga tushirish bir xil natija beradi (idempotent).
    """
    text = normalize_apostrophes(text)
    text = _expand_abbreviations(text, ai_reading=ai_reading)
    text = _convert_dates(text)
    text = _convert_currency_percent_time_phone(text)
    text = _convert_numbers_and_ordinals(text)
    text = _transliterate_foreign(text, extra_translit=extra_translit)
    if not allow_russian:
        text = _replace_russian_loanwords(text)
    text = _cleanup_whitespace(text)
    return text


def to_display_text(text: str) -> str:
    """Ekranda ko'rsatish uchun: faqat apostrof normalizatsiyasi + bo'shliq
    tozalash. Raqamlar raqam holida qoladi (ekranda "15%" chiroyliroq)."""
    text = normalize_apostrophes(text)
    text = _cleanup_whitespace(text)
    return text


# ---------------------------------------------------------------------------
# 10. Jumlalarga bo'lish / TTS uchun bo'laklash
# ---------------------------------------------------------------------------

_SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Za-zʻʼЎўҚқҒғҲҳА-Яа-я0-9\"'‘“])")


def split_sentences(text: str) -> list[str]:
    """Matnni jumlalarga bo'ladi (., !, ? bo'yicha, bo'shliqni saqlamay)."""
    text = text.strip()
    if not text:
        return []
    parts = _SENTENCE_END_RE.split(text)
    return [p.strip() for p in parts if p.strip()]


_CONJUNCTIONS = ["shuning uchun", "lekin", "ammo", "chunki", "va"]
_CONJ_ALT = "|".join(re.escape(c) for c in _CONJUNCTIONS)
# Vergulдан keyingi bo'shliqda, yoki bog'lovchidan oldingi bo'shliqda bo'linadi —
# vergul oldingi bo'lakka, bog'lovchi keyingi bo'lakka yopishib qoladi.
_BREAK_RE = re.compile(rf"(?<=,)\s+|\s+(?=\b(?:{_CONJ_ALT})\b)")


def _break_segments(sentence: str) -> list[str]:
    """Jumlani vergul/bog'lovchilar bo'yicha bo'laklarga ajratadi."""
    return [seg.strip() for seg in _BREAK_RE.split(sentence) if seg.strip()]


def chunk_for_tts(text: str, max_words: int = 18) -> list[str]:
    """Uzun jumlalarni vergul/bog'lovchilar bo'yicha ≤ max_words so'zli
    bo'laklarga bo'ladi (TTS intonatsiyasi uchun)."""
    chunks: list[str] = []
    for sentence in split_sentences(text):
        words = sentence.split()
        if len(words) <= max_words:
            chunks.append(sentence)
            continue
        segments = _break_segments(sentence)
        current: list[str] = []
        current_len = 0
        for seg in segments:
            seg_words = seg.split()
            if current and current_len + len(seg_words) > max_words:
                chunks.append(" ".join(current).strip())
                current = []
                current_len = 0
            current.extend(seg_words)
            current_len += len(seg_words)
        if current:
            chunks.append(" ".join(current).strip())
    return chunks


# ---------------------------------------------------------------------------
# 11. Subtitr qatorlari
# ---------------------------------------------------------------------------

def subtitle_lines(text: str, max_chars: int = 42, max_lines: int = 2) -> list[str]:
    """So'z chegarasida ≤ max_chars belgili, ≤ max_lines qatorga bo'ladi."""
    text = " ".join(text.split())
    if not text:
        return []
    lines = textwrap.wrap(text, width=max_chars, break_long_words=False, break_on_hyphens=False)
    if len(lines) <= max_lines:
        return lines
    head = lines[: max_lines - 1]
    rest = " ".join(lines[max_lines - 1 :])
    head.append(rest)
    return head


# ---------------------------------------------------------------------------
# 12. Kirill -> lotin transliteratsiyasi (2023 rasmiy qoidalar)
# ---------------------------------------------------------------------------

_CYR_LOWER_MAP = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "ё": "yo", "ж": "j",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n",
    "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f",
    "х": "x", "ц": "ts", "ч": "ch", "ш": "sh", "ъ": TUTUQ, "ь": "",
    "э": "e", "ю": "yu", "я": "ya", "ў": "o" + OKINA, "қ": "q",
    "ғ": "g" + OKINA, "ҳ": "h",
}
_CYR_VOWELS = set("аеёиоуўэюя")
_CYR_WORD_RE = re.compile(r"[А-Яа-яЎўҚқҒғҲҳЁё]+")


def _transliterate_cyrillic_word(word: str) -> str:
    is_all_upper = word.isupper() and len(word) > 1
    lower_word = word.lower()
    out: list[str] = []
    for i, ch in enumerate(word):
        lc = ch.lower()
        if lc == "е":
            prev = lower_word[i - 1] if i > 0 else None
            latin = "ye" if prev is None or prev in _CYR_VOWELS else "e"
        else:
            latin = _CYR_LOWER_MAP.get(lc, lc)
        if ch.isupper() and latin:
            latin = latin.upper() if is_all_upper else (latin[0].upper() + latin[1:])
        out.append(latin)
    return "".join(out)


def cyr_to_lat(text: str) -> str:
    """Kirill yozuvidagi o'zbekcha matnni lotin yozuviga o'giradi (2023 qoidalar)."""
    return _CYR_WORD_RE.sub(lambda m: _transliterate_cyrillic_word(m.group(0)), text)
