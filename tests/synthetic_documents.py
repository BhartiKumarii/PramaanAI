"""Synthetic document image generation for tests only — never commit or
process real identity documents. Renders clean, labeled text on a plain
canvas so OCR extraction can be verified deterministically.
"""
import io

from PIL import Image, ImageDraw, ImageFont

from app.services.validation.mrz import compute_check_digit

_FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
_FONT_REGULAR = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
_FONT_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"


def _load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    path = _FONT_BOLD if bold else _FONT_REGULAR
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


def _render(title: str, lines: list[str], height: int = 800) -> bytes:
    width = 1200
    image = Image.new("RGB", (width, height), color="white")
    draw = ImageDraw.Draw(image)

    draw.text((60, 40), title, font=_load_font(40, bold=True), fill="black")

    label_font = _load_font(28)
    y = 140
    for line in lines:
        draw.text((60, y), line, font=label_font, fill="black")
        y += 60

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def generate_passport_image(
    name: str = "JOHN MICHAEL SMITH",
    passport_number: str = "N1234567",
    nationality: str = "INDIAN",
    date_of_birth: str = "12/04/1990",
    date_of_expiry: str = "11/04/2030",
    gender: str = "M",
) -> bytes:
    lines = [
        f"Name: {name}",
        f"Passport No: {passport_number}",
        f"Nationality: {nationality}",
        f"Date of Birth: {date_of_birth}",
        f"Date of Expiry: {date_of_expiry}",
        f"Sex: {gender}",
    ]
    return _render("REPUBLIC OF EXAMPLIA -- PASSPORT", lines)


def generate_mrz_lines(
    surname: str = "SMITH",
    given_names: str = "JOHN MICHAEL",
    passport_number: str = "N1234567",
    issuing_country: str = "EXA",
    nationality: str = "IND",
    date_of_birth_yymmdd: str = "900412",
    sex: str = "M",
    date_of_expiry_yymmdd: str = "300411",
    personal_number: str = "",
) -> tuple[str, str]:
    """Build a real, check-digit-correct ICAO 9303 TD3 MRZ pair. Checksums
    are computed with the same algorithm the parser validates against, so
    a test corrupting one field afterwards is a genuine negative case."""
    name_field = f"{surname}<<{given_names.replace(' ', '<')}"
    line1 = f"P<{issuing_country}{name_field}".ljust(44, "<")[:44]

    passport_field = passport_number.ljust(9, "<")[:9]
    passport_check = compute_check_digit(passport_field)
    personal_field = personal_number.ljust(14, "<")[:14]
    personal_check = compute_check_digit(personal_field)
    dob_check = compute_check_digit(date_of_birth_yymmdd)
    doe_check = compute_check_digit(date_of_expiry_yymmdd)

    composite_input = (
        passport_field + str(passport_check)
        + date_of_birth_yymmdd + str(dob_check)
        + date_of_expiry_yymmdd + str(doe_check)
        + personal_field + str(personal_check)
    )
    composite_check = compute_check_digit(composite_input)

    line2 = (
        f"{passport_field}{passport_check}{nationality}"
        f"{date_of_birth_yymmdd}{dob_check}{sex}"
        f"{date_of_expiry_yymmdd}{doe_check}"
        f"{personal_field}{personal_check}{composite_check}"
    )
    assert len(line1) == 44 and len(line2) == 44
    return line1, line2


def generate_passport_back_image(line1: str, line2: str) -> bytes:
    """Render two MRZ lines in a monospace font, the way the back of a
    real passport's data page prints its machine-readable zone."""
    width, height = 1200, 300
    image = Image.new("RGB", (width, height), color="white")
    draw = ImageDraw.Draw(image)
    font = _load_font(34)
    try:
        font = ImageFont.truetype(_FONT_MONO, 34)
    except OSError:
        pass
    draw.text((40, 90), line1, font=font, fill="black")
    draw.text((40, 160), line2, font=font, fill="black")

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def generate_face_like_image(seed: int) -> bytes:
    """Not a real face — a distinct, deterministic gradient/shape pattern
    per seed. Enough to exercise the real gradient-histogram face
    embedding with genuinely different pixel content per identity; not a
    substitute for testing against an actual photographed face."""
    image = Image.new("L", (200, 200), color=40 + seed * 5)
    draw = ImageDraw.Draw(image)
    draw.ellipse((30 + seed * 3, 30, 170 + seed * 3, 190), fill=180 - seed * 4)
    draw.ellipse((60, 80 + seed * 2, 90, 110 + seed * 2), fill=20)
    draw.ellipse((110, 80 + seed * 2, 140, 110 + seed * 2), fill=20)
    draw.arc((70, 120, 130, 160), start=0, end=180, fill=10, width=4)
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def generate_visa_image(
    visa_number: str = "V9988776",
    visa_type: str = "TOURIST",
    entry_validity: str = "SINGLE",
    stay_duration: str = "30 DAYS",
) -> bytes:
    lines = [
        f"Visa No: {visa_number}",
        f"Visa Type: {visa_type}",
        f"Entry Validity: {entry_validity}",
        f"Stay Duration: {stay_duration}",
    ]
    return _render("VISA", lines, height=700)
