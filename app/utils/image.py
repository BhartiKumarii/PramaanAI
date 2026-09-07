"""Shared image preprocessing utilities."""
import io

from PIL import Image


def downscale_image_bytes(image_bytes: bytes, max_dimension: int = 1600, quality: int = 90) -> bytes:
    """Cap an uploaded photo's longer side at `max_dimension` pixels,
    re-encoded as JPEG. Real phone camera photos (often 3000-4000px on the
    long side) get decoded into several full-resolution RGB buffers across
    the OCR/ELA/face pipeline downstream (e.g. ELA alone holds the original,
    a resaved copy, and their diff, all at full resolution) — this caps that
    footprint before any of them run, which matters on memory-constrained
    hosts (e.g. Render's free tier, 512MB). Detection logic itself is
    untouched, only the input resolution. No-op if already at or under the
    cap, so a well-sized upload isn't re-encoded for no reason.
    """
    image = Image.open(io.BytesIO(image_bytes))
    longest_side = max(image.size)
    if longest_side <= max_dimension:
        return image_bytes

    scale = max_dimension / longest_side
    new_size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    resized = image.convert("RGB").resize(new_size, Image.LANCZOS)
    buffer = io.BytesIO()
    resized.save(buffer, "JPEG", quality=quality)
    return buffer.getvalue()
