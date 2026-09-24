"""Devanagari (Nepali/Hindi) field parsing — synthetic lines, no real data."""
from app.services.docverify.fields import extract_native_fields
from app.services.docverify.types import OcrLine


def L(text, x, y, w=200, h=30, conf=0.95):
    return OcrLine(text=text, confidence=conf, bbox=[x, y, x + w, y + h])


def test_label_and_value_on_same_line():
    f = extract_native_fields([L("नाम थर: राम बहादुर थापा", 10, 10), L("जन्म मिति: २०४४-०६-१०", 10, 60)])
    assert f["name_native"].value == "राम बहादुर थापा"
    assert f["name_native"].source == "ocr_devanagari"
    # Bikram Sambat, kept as BS — never read as a Gregorian date
    assert f["date_of_birth_bs"].value == "2044-06-10 BS"
    assert "date_of_birth" not in f


def test_value_under_a_standalone_label_and_misspelt_label():
    f = extract_native_fields([L("राषट्टिय परिचय नम्वर  NIN", 300, 140), L("३९३-३८४-५१५", 300, 170)])
    assert f["national_id_number"].value == "393-384-515"


def test_far_away_line_is_not_taken_as_the_value():
    f = extract_native_fields([L("नाम थर", 300, 250), L("२०४४-०६-१०", 300, 540)])
    assert "name_native" not in f


def test_another_label_is_not_a_value():
    f = extract_native_fields([L("नाम", 650, 1240, w=60), L("दर्जा:", 650, 1283, w=60)])
    assert "name_native" not in f


def test_sex_words():
    assert extract_native_fields([L("पुरुष/ MALE", 10, 10)])["sex_native"].value == "M"
    assert extract_native_fields([L("महिला", 10, 10)])["sex_native"].value == "F"


def test_invalid_bs_month_rejected():
    f = extract_native_fields([L("जन्म मिति: २०३४-९०-२३", 10, 10)])
    assert "date_of_birth_bs" not in f


def test_misread_label_takes_the_value_to_its_right():
    f = extract_native_fields([L("नाम शर", 146, 132, w=47, h=13), L("राम कुमार श्रेष्ठ", 228, 127, w=123, h=23),
                               L("महिला", 515, 127, w=52, h=26)])
    assert f["name_native"].value == "राम कुमार श्रेष्ठ"
