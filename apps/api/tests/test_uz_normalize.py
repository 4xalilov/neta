import pytest

from engine.uz.normalize import (
    MONTHS,
    OKINA,
    TUTUQ,
    chunk_for_tts,
    cyr_to_lat,
    decimal_to_words,
    normalize_apostrophes,
    number_to_words,
    ordinal_to_words,
    split_sentences,
    subtitle_lines,
    to_display_text,
    to_tts_text,
)

# ---------------------------------------------------------------------------
# normalize_apostrophes
# ---------------------------------------------------------------------------

def test_okina_variants():
    for s in ["o'zbek", "o‘zbek", "o’zbek", "o`zbek"]:
        assert normalize_apostrophes(s) == f"o{OKINA}zbek"


def test_okina_uppercase():
    assert normalize_apostrophes("O'zbekiston") == f"O{OKINA}zbekiston"
    assert normalize_apostrophes("G'oyalar") == f"G{OKINA}oyalar"
    assert normalize_apostrophes("O'ZBEKISTON") == f"O{OKINA}ZBEKISTON"


def test_tutuq():
    assert normalize_apostrophes("ma'no") == f"ma{TUTUQ}no"


def test_mixed():
    assert normalize_apostrophes("g'oya va she'r") == f"g{OKINA}oya va she{TUTUQ}r"


def test_quote_phrase_stays_quote():
    # So'z/ibora atrofidagi tik tirnoq — okina/tutuqqa aylanmasligi kerak.
    assert normalize_apostrophes("'salom' dedi") == "'salom' dedi"
    assert normalize_apostrophes("u 'ha' dedi") == "u 'ha' dedi"
    assert normalize_apostrophes("u 'yaxshi fikr' dedi") == "u 'yaxshi fikr' dedi"


def test_quote_phrase_multi_word_stays_quote():
    # Tirnoq ko'p so'zli iboraning ikkala chetida ham tirnoq bo'lib qoladi.
    # Izoh: agar tirnoq ICHIDAGI so'zning o'zida ham apostrof (oʻ/ʼ manbasi)
    # bo'lsa (masalan "'a'lo'"), qaysi apostrof tirnoqni yopishini ajratish
    # tabiiy til darajasida qat'iy hal qilib bo'lmaydigan chegaraviy holat —
    # bu holda ichkarida so'z oxiridagi apostrof umumiy qoidaga ko'ra ʼ/ʻ ga
    # aylanadi (bilinadigan cheklov, hisobotda qayd etilgan).
    assert normalize_apostrophes("u 'yaxshi fikr' dedi, hammaga") == (
        "u 'yaxshi fikr' dedi, hammaga"
    )


def test_empty_string():
    assert normalize_apostrophes("") == ""


# ---------------------------------------------------------------------------
# number_to_words
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "n,expected",
    [
        (0, "nol"),
        (1, "bir"),
        (5, "besh"),
        (9, "toʻqqiz"),
        (10, "oʻn"),
        (11, "oʻn bir"),
        (15, "oʻn besh"),
        (20, "yigirma"),
        (24, "yigirma toʻrt"),
        (90, "toʻqson"),
        (99, "toʻqson toʻqqiz"),
        (100, "bir yuz"),
        (101, "bir yuz bir"),
        (123, "bir yuz yigirma uch"),
        (500, "besh yuz"),
        (999, "toʻqqiz yuz toʻqson toʻqqiz"),
        (1000, "bir ming"),
        (2026, "ikki ming yigirma olti"),
        (20000, "yigirma ming"),
        (1_500_000, "bir million besh yuz ming"),
    ],
)
def test_number_to_words(n, expected):
    assert number_to_words(n) == expected


def test_number_to_words_negative():
    assert number_to_words(-42) == "minus qirq ikki"
    assert number_to_words(-1) == "minus bir"


def test_number_to_words_upper_bound():
    assert number_to_words(999_999_999_999) == (
        "toʻqqiz yuz toʻqson toʻqqiz milliard "
        "toʻqqiz yuz toʻqson toʻqqiz million "
        "toʻqqiz yuz toʻqson toʻqqiz ming "
        "toʻqqiz yuz toʻqson toʻqqiz"
    )


def test_number_to_words_out_of_range():
    with pytest.raises(ValueError):
        number_to_words(1_000_000_000_000)


# ---------------------------------------------------------------------------
# ordinal_to_words
# ---------------------------------------------------------------------------

_ORDINALS = [
    (1, "birinchi"), (2, "ikkinchi"), (3, "uchinchi"), (4, "toʻrtinchi"),
    (5, "beshinchi"), (6, "oltinchi"), (7, "yettinchi"), (8, "sakkizinchi"),
    (9, "toʻqqizinchi"), (10, "oʻninchi"), (20, "yigirmanchi"),
    (30, "oʻttizinchi"), (40, "qirqinchi"), (50, "ellikinchi"),
    (60, "oltmishinchi"), (70, "yetmishinchi"), (80, "saksoninchi"),
    (90, "toʻqsoninchi"), (100, "yuzinchi"), (1000, "minginchi"),
]


@pytest.mark.parametrize("n,expected", _ORDINALS)
def test_ordinal_to_words(n, expected):
    assert ordinal_to_words(n) == expected


def test_ordinal_to_words_compound():
    assert ordinal_to_words(24) == "yigirma toʻrtinchi"
    assert ordinal_to_words(2026) == "ikki ming yigirma oltinchi"


# ---------------------------------------------------------------------------
# decimal_to_words
# ---------------------------------------------------------------------------

def test_decimal_to_words():
    assert decimal_to_words("3,5") == "uch butun besh"
    assert decimal_to_words("3.5") == "uch butun besh"
    assert decimal_to_words("3,15") == "uch butun oʻn besh"


def test_decimal_to_words_negative():
    assert decimal_to_words("-3,5") == "minus uch butun besh"


def test_decimal_to_words_invalid():
    with pytest.raises(ValueError):
        decimal_to_words("abc")


# ---------------------------------------------------------------------------
# Sanalar (to_tts_text orqali)
# ---------------------------------------------------------------------------

def test_date_day_month_dash():
    assert to_tts_text("24-sentyabr") == "yigirma toʻrtinchi sentyabr"


def test_date_day_month_space():
    assert to_tts_text("24 sentyabr") == "yigirma toʻrtinchi sentyabr"


def test_date_year():
    assert to_tts_text("2026-yil") == "ikki ming yigirma oltinchi yil"


def test_date_full_dmy():
    assert to_tts_text("24.09.2026") == (
        "yigirma toʻrtinchi sentyabr ikki ming yigirma oltinchi yil"
    )


def test_months_list():
    assert MONTHS[0] == "yanvar"
    assert MONTHS[8] == "sentyabr"
    assert len(MONTHS) == 12


# ---------------------------------------------------------------------------
# Foiz / valyuta / vaqt / telefon / oraliq (to_tts_text orqali)
# ---------------------------------------------------------------------------

def test_percent():
    assert to_tts_text("15%") == "oʻn besh foiz"
    assert to_tts_text("15 %") == "oʻn besh foiz"


def test_currency_space_grouped():
    assert to_tts_text("1 500 000 so'm") == "bir million besh yuz ming soʻm"


def test_currency_dot_grouped():
    assert to_tts_text("1.500.000 so‘m") == "bir million besh yuz ming soʻm"


def test_currency_decimal_million():
    assert to_tts_text("1,5 mln so'm") == "bir butun besh million soʻm"


def test_currency_dollar_sign():
    assert to_tts_text("$20") == "yigirma dollar"


def test_currency_uzs_code():
    assert to_tts_text("20 000 UZS") == "yigirma ming soʻm"


def test_time_round_hour():
    assert to_tts_text("09:00") == "toʻqqiz nol nol"


def test_time_with_soat_prefix():
    assert to_tts_text("soat 09:00") == "soat toʻqqiz"


def test_time_with_minutes():
    assert to_tts_text("14:35") == "oʻn toʻrt oʻttiz besh"


def test_phone_number():
    assert to_tts_text("+998 90 123 45 67") == (
        "plyus toʻqqiz yuz toʻqson sakkiz, toʻqson, "
        "bir yuz yigirma uch, qirq besh, oltmish yetti"
    )


def test_range():
    assert to_tts_text("5-10") == "beshdan oʻngacha"


def test_ordinal_dash_suffix():
    assert to_tts_text("5-chi") == "beshinchi"


def test_ordinal_dash_before_noun():
    assert to_tts_text("5-sinf") == "beshinchi sinf"


def test_plain_thousand_separators():
    assert to_tts_text("1 234") == "bir ming ikki yuz oʻttiz toʻrt"
    assert to_tts_text("1.234") == "bir ming ikki yuz oʻttiz toʻrt"
    assert to_tts_text("1,234") == "bir ming ikki yuz oʻttiz toʻrt"
    assert to_tts_text("1'234") == "bir ming ikki yuz oʻttiz toʻrt"


# ---------------------------------------------------------------------------
# Qisqartmalar
# ---------------------------------------------------------------------------

def test_abbreviations_basic():
    assert to_tts_text("va h.k.") == "va hokazo"
    assert to_tts_text("t.r.") == "telefon raqami"
    assert to_tts_text("mln") == "million"
    assert to_tts_text("m-n") == "million"
    assert to_tts_text("mlrd") == "milliard"
    assert to_tts_text("kg") == "kilogramm"
    assert to_tts_text("km") == "kilometr"
    assert to_tts_text("sm") == "santimetr"


def test_abbreviations_tech():
    assert to_tts_text("IT") == "ay-ti"
    assert to_tts_text("SMM") == "es-em-em"
    assert to_tts_text("CRM") == "si-ar-em"
    assert to_tts_text("USD") == "dollar"
    assert to_tts_text("UZS") == "soʻm"


def test_abbreviations_titles():
    assert to_tts_text("dr. Aliyev") == "doktor Aliyev"
    assert to_tts_text("prof. Karimova") == "professor Karimova"
    assert to_tts_text("tel. raqamingiz") == "telefon raqamingiz"
    assert to_tts_text("ko'ch. Navoiy") == "koʻchasi Navoiy"


def test_abbreviation_ai_configurable():
    assert to_tts_text("AI yordamchi") == "sunʼiy intellekt yordamchi"
    assert to_tts_text("AI yordamchi", ai_reading="ey-ay") == "ey-ay yordamchi"


def test_abbreviation_no_false_positive_inside_word():
    # "AI" so'z ichida (masalan AIDA) qisqartma sifatida almashtirilmasin.
    assert "AIDA" in to_tts_text("AIDA reja")


# ---------------------------------------------------------------------------
# Chet so'zlar transliteratsiyasi
# ---------------------------------------------------------------------------

def test_foreign_words():
    assert to_tts_text("Reels") == "Rils"
    assert to_tts_text("Instagram") == "Instagram"
    assert to_tts_text("TikTok") == "Tik-Tok"
    assert to_tts_text("YouTube") == "Yutub"
    assert to_tts_text("Telegram") == "Telegram"
    assert to_tts_text("iPhone") == "Ayfon"
    assert to_tts_text("Google") == "Gugl"
    assert to_tts_text("WhatsApp") == "Votsap"
    assert to_tts_text("like") == "layk"
    assert to_tts_text("story") == "stori"
    assert to_tts_text("stories") == "storis"


def test_foreign_words_case_insensitive():
    assert to_tts_text("REELS") == "Rils"
    assert to_tts_text("reels") == "Rils"


def test_foreign_words_extra_translit():
    out = to_tts_text("Netflix ko'rdim", extra_translit={"Netflix": "Netfliks"})
    assert out == "Netfliks koʻrdim"


def test_foreign_words_brand_override():
    # Standart lug'atni brend darajasida bekor qilish mumkin.
    out = to_tts_text("Instagram", extra_translit={"Instagram": "Instagrám"})
    assert out == "Instagrám"


# ---------------------------------------------------------------------------
# Ruscha o'zlashmalar
# ---------------------------------------------------------------------------

def test_russian_replaced_by_default():
    assert to_tts_text("katta skidka bor") == "katta chegirma bor"


def test_russian_kept_when_allowed():
    assert to_tts_text("katta skidka bor", allow_russian=True) == "katta skidka bor"


# ---------------------------------------------------------------------------
# split_sentences / chunk_for_tts
# ---------------------------------------------------------------------------

def test_split_sentences():
    text = "Siz tayyormisiz? Boshlaymiz! Bu birinchi gap. Bu ikkinchi."
    assert split_sentences(text) == [
        "Siz tayyormisiz?",
        "Boshlaymiz!",
        "Bu birinchi gap.",
        "Bu ikkinchi.",
    ]


def test_split_sentences_empty():
    assert split_sentences("") == []
    assert split_sentences("   ") == []


def test_chunk_for_tts_short_sentence_untouched():
    assert chunk_for_tts("Bu qisqa gap.") == ["Bu qisqa gap."]


def test_chunk_for_tts_splits_long_sentence():
    long_sentence = (
        "Biz bugun Instagram uchun ajoyib kontent tayyorlaymiz va uni chop "
        "qilamiz, lekin avval strategiyani belgilaymiz chunki bu juda muhim "
        "qadam hisoblanadi."
    )
    chunks = chunk_for_tts(long_sentence, max_words=10)
    assert len(chunks) > 1
    for c in chunks:
        assert len(c.split()) <= 10
    # so'zlar yo'qolmasligi kerak
    assert sum(len(c.split()) for c in chunks) == len(long_sentence.split())


# ---------------------------------------------------------------------------
# to_tts_text idempotentligi
# ---------------------------------------------------------------------------

def test_to_tts_text_idempotent():
    raw = "Chegirma 15%, 1 500 000 so'm, 2026-yil 24-sentyabr, +998 90 123 45 67"
    once = to_tts_text(raw)
    twice = to_tts_text(once)
    assert once == twice


def test_to_tts_text_default_call_signature():
    # apps/api/src/engine/integrations/tts.py to_tts_text(text) deb chaqiradi.
    assert to_tts_text("15%") == "oʻn besh foiz"


# ---------------------------------------------------------------------------
# to_display_text
# ---------------------------------------------------------------------------

def test_to_display_text_keeps_numbers():
    out = to_display_text("2026-yil 15% chegirma, o'zbek")
    assert "2026" in out
    assert "15%" in out
    assert f"o{OKINA}zbek" in out


# ---------------------------------------------------------------------------
# subtitle_lines
# ---------------------------------------------------------------------------

def test_subtitle_lines_word_boundary():
    text = "Bu juda uzun subtitr matni, ikki qatorga bo'linadi"
    lines = subtitle_lines(text, max_chars=30, max_lines=2)
    assert len(lines) == 2
    for line in lines:
        assert len(line) <= 30
        # so'z o'rtasidan kesilmasligi kerak
        assert not line.endswith("-")


def test_subtitle_lines_overflow_merges_into_last_line():
    # max_lines dan ko'p qator kerak bo'lsa, oxirgi qator max_chars dan
    # oshishi mumkin (eng yaxshi urinish) — so'z yo'qolmaydi.
    text = "Bu juda uzun subtitr matni bo'lib ikki qatorga bo'linishi kerak"
    lines = subtitle_lines(text, max_chars=30, max_lines=2)
    assert len(lines) == 2
    assert " ".join(text.split()) == " ".join(" ".join(lines).split())


def test_subtitle_lines_short_text_one_line():
    assert subtitle_lines("Salom dunyo", max_chars=42, max_lines=2) == ["Salom dunyo"]


def test_subtitle_lines_empty():
    assert subtitle_lines("") == []


# ---------------------------------------------------------------------------
# cyr_to_lat
# ---------------------------------------------------------------------------

def test_cyr_to_lat_basic_place_names():
    assert cyr_to_lat("Бекобод") == "Bekobod"
    assert cyr_to_lat("Тошкент") == "Toshkent"


def test_cyr_to_lat_special_letters():
    # ц->ts, ч->ch, ш->sh, ў->oʻ, ғ->gʻ, ҳ->h, х->x
    assert cyr_to_lat("цех") == "tsex"
    assert cyr_to_lat("чой") == "choy"
    assert cyr_to_lat("шаҳар") == "shahar"
    assert cyr_to_lat("ғоя") == f"g{OKINA}oya"
    assert cyr_to_lat("ҳозир") == "hozir"
    assert cyr_to_lat("хабар") == "xabar"


def test_cyr_to_lat_tutuq():
    assert cyr_to_lat("объект") == f"ob{TUTUQ}ekt"


def test_cyr_to_lat_ye_context():
    # so'z boshida yoki unlidan keyin "е"->ye, aks holda "e"
    assert cyr_to_lat("Европа") == "Yevropa"
    assert cyr_to_lat("Бекобод") == "Bekobod"


def test_cyr_to_lat_yo_yu_ya():
    assert cyr_to_lat("ёлка") == "yolka"
    assert cyr_to_lat("юрист") == "yurist"
    assert cyr_to_lat("яшик") == "yashik"


def test_cyr_to_lat_all_caps():
    assert cyr_to_lat("ЎЗБЕКИСТОН") == (
        f"O{OKINA}ZBEKISTON"
    )


# ---------------------------------------------------------------------------
# evals/tts_test.md — 3, 4, 7-jumlalar
# ---------------------------------------------------------------------------

def test_eval_sentence_4_discount_percent():
    # 4. "Chegirma oʻn besh foiz, faqat bugun."
    out = to_tts_text("Chegirma 15%, faqat bugun.")
    assert out == "Chegirma oʻn besh foiz, faqat bugun."


def test_eval_sentence_7_currency():
    # 7. "Bir million besh yuz ming soʻm."
    out = to_tts_text("1 500 000 so'm.")
    # Raqam so'zga o'girilganda bosh harf katta bo'lmaydi — jumla boshi katta
    # harfga o'tkazilishi alohida (stilistik) qadam, normalizator vazifasi emas.
    assert out[0].upper() + out[1:] == "Bir million besh yuz ming soʻm."


def test_eval_sentence_3_date_components():
    # 3. "Ikki ming yigirma oltinchi yilning yigirma toʻrtinchi sentyabri."
    # (grammatik -ning/-i qo'shimchalari normalizator doirasidan tashqarida —
    # quyida tub qismlar tekshiriladi)
    assert to_tts_text("2026-yil") == "ikki ming yigirma oltinchi yil"
    assert to_tts_text("24-sentyabr") == "yigirma toʻrtinchi sentyabr"
    assert to_tts_text("24.09.2026") == (
        "yigirma toʻrtinchi sentyabr ikki ming yigirma oltinchi yil"
    )


def test_eval_sentence_1_and_2_apostrophes():
    # 1. "Oʻzbekistonda gʻoyalar tez amalga oshadi."
    assert normalize_apostrophes("O'zbekistonda g'oyalar tez amalga oshadi.") == (
        f"O{OKINA}zbekistonda g{OKINA}oyalar tez amalga oshadi."
    )
    # 2. "Bu yerda maʼno juda muhim."
    assert normalize_apostrophes("Bu yerda ma'no juda muhim.") == (
        f"Bu yerda ma{TUTUQ}no juda muhim."
    )


def test_eval_sentence_10_ai():
    # 10. "Sunʼiy intellekt sizga yordam beradi."
    assert to_tts_text("AI sizga yordam beradi.") == (
        f"sun{TUTUQ}iy intellekt sizga yordam beradi."
    )
