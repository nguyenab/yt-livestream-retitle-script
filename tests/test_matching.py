from app.matching import normalize, matches_any

BASE = "Lễ thờ phượng - Worship Service - Hội Thánh Tin Lành Ân Điển"


def test_normalize_strips_diacritics_and_case():
    assert normalize("Lễ thờ phượng") == "le tho phuong"


def test_normalize_strips_date_prefix():
    assert normalize(f"Sunday, May 10th, 2026 - {BASE}") == normalize(BASE)


def test_normalize_collapses_whitespace():
    assert normalize("Worship   Service\n") == "worship service"


def test_matches_any_true_with_date_prefix():
    title = f"Sunday, May 10th, 2026 - {BASE}"
    assert matches_any(title, [BASE]) is True


def test_matches_any_true_case_insensitive():
    assert matches_any(BASE.upper(), [BASE]) is True


def test_matches_any_false_for_unrelated():
    assert matches_any("Some Random Video", [BASE]) is False
