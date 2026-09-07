"""Error Level Analysis (ELA): re-save the image at a known JPEG quality
and diff it against the original. Regions that were compressed a
different number of times than their surroundings (e.g. a pasted/edited
patch) show a different error level than genuinely untouched regions.

Pure Pillow, no external model — real pixel-level analysis, not a
placeholder score.
"""
import io
import statistics
from dataclasses import dataclass

from PIL import Image, ImageChops, ImageStat


@dataclass
class BlockStat:
    x0: int
    y0: int
    x1: int
    y1: int
    mean_error: float
    z_score: float = 0.0


def compute_ela_image(image_bytes: bytes, quality: int = 90) -> Image.Image:
    """Grayscale per-pixel error level: |original - resaved-at-`quality`|."""
    original = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    buffer = io.BytesIO()
    original.save(buffer, "JPEG", quality=quality)
    buffer.seek(0)
    resaved = Image.open(buffer).convert("RGB")
    return ImageChops.difference(original, resaved).convert("L")


def block_statistics(ela_image: Image.Image, grid: int = 8) -> list[BlockStat]:
    """Mean ELA intensity per grid cell, real pixel stats via PIL's
    ImageStat — not sampled or estimated."""
    width, height = ela_image.size
    grid = max(1, min(grid, width, height))
    cell_w = max(1, width // grid)
    cell_h = max(1, height // grid)

    blocks: list[BlockStat] = []
    for row in range(grid):
        for col in range(grid):
            x0, y0 = col * cell_w, row * cell_h
            x1 = width if col == grid - 1 else x0 + cell_w
            y1 = height if row == grid - 1 else y0 + cell_h
            crop = ela_image.crop((x0, y0, x1, y1))
            mean = ImageStat.Stat(crop).mean[0]
            blocks.append(BlockStat(x0=x0, y0=y0, x1=x1, y1=y1, mean_error=mean))

    means = [b.mean_error for b in blocks]
    mu = statistics.fmean(means)
    sigma = statistics.pstdev(means) or 1e-6
    for block in blocks:
        block.z_score = (block.mean_error - mu) / sigma
    return blocks


def most_anomalous_block(blocks: list[BlockStat]) -> BlockStat:
    return max(blocks, key=lambda b: b.z_score)
