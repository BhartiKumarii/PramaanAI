"""OCR extraction tuned for the MRZ zone specifically: restricted to the
actual MRZ character set (A-Z, 0-9, '<') and a single-text-block page
segmentation mode, which is far more reliable for monospace MRZ text than
the general-purpose extraction used for the front-of-document VIZ fields.
"""
import io

import pytesseract
from PIL import Image, ImageOps

_MRZ_CONFIG = "--psm 6 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789<"


def extract_mrz_text(image_bytes: bytes) -> str:
    image = Image.open(io.BytesIO(image_bytes))
    image = ImageOps.exif_transpose(image)
    image = image.convert("L")
    image = ImageOps.autocontrast(image)
    return pytesseract.image_to_string(image, config=_MRZ_CONFIG)
