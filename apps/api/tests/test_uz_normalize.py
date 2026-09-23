from engine.uz.normalize import OKINA, TUTUQ, normalize_apostrophes


def test_okina_variants():
    for s in ["o'zbek", "o‘zbek", "o’zbek", "o`zbek"]:
        assert normalize_apostrophes(s) == f"o{OKINA}zbek"


def test_tutuq():
    assert normalize_apostrophes("ma'no") == f"ma{TUTUQ}no"


def test_mixed():
    assert normalize_apostrophes("g'oya va she'r") == f"g{OKINA}oya va she{TUTUQ}r"
