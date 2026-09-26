FROM python:3.11-slim

WORKDIR /app

# psycopg2-binary and cryptography ship manylinux wheels for this platform,
# so no compiler/libpq-dev is needed here. Add them back only if a future
# dependency (e.g. an ML lib without wheels) requires building from source.

# Tesseract binary + English language data for OCR (Module 1). Not a pip
# package — pytesseract just shells out to this binary.
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-eng \
    libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# The image runs with PRAMAAN_MEDIAPIPE=false (below), so MediaPipe and the
# opencv-contrib build it drags in (plus matplotlib) are not installed:
# ~350 MB less image, a second full copy of OpenCV avoided. InsightFace and
# RapidOCR still pull in plain opencv-python. Every MediaPipe import in app/
# is guarded and falls back when it is missing. Local dev keeps the full
# requirements.txt.
RUN grep -vE '^(mediapipe|opencv-contrib-python)' requirements.txt > /tmp/requirements-server.txt \
    && pip install --no-cache-dir -r /tmp/requirements-server.txt

COPY . .

# PP-OCRv5 Devanagari recognition model (~8 MB, Apache-2.0, PaddlePaddle) for
# reading Nepali/Hindi text. Weights are not kept in git; if this download
# fails the server still starts and reports the stage as "not installed".
RUN python -c "import urllib.request, yaml, os; \
d='models/ocr/devanagari_v5'; os.makedirs(d, exist_ok=True); \
b='https://huggingface.co/PaddlePaddle/devanagari_PP-OCRv5_mobile_rec_onnx/resolve/main/'; \
[urllib.request.urlretrieve(b + f, os.path.join(d, f)) for f in ('inference.onnx', 'inference.yml')]; \
ch = yaml.safe_load(open(os.path.join(d, 'inference.yml')))['PostProcess']['character_dict']; \
open(os.path.join(d, 'keys.txt'), 'w').write(chr(10).join(ch) + chr(10))" \
    || echo "Devanagari OCR model download failed; Nepali/Hindi text will not be read"

EXPOSE 8000

# Memory profile for small instances (Render free: 512 MB). Measured with
# 3 verifications + 2 in parallel: 685 MB peak before, ~420 MB after.
#  - MediaPipe off: InsightFace detects faces, liveness is measured on the phone
#  - one verification at a time; one ONNX thread per OCR engine
#  - two glibc arenas instead of one per thread
# Override any of these with environment variables on a larger instance.
ENV PRAMAAN_MEDIAPIPE=false \
    PRAMAAN_MAX_CONCURRENT_VERIFICATIONS=1 \
    PRAMAAN_OCR_THREADS=1 \
    OMP_NUM_THREADS=1 \
    MALLOC_ARENA_MAX=2

# Render sets $PORT at runtime; docker-compose leaves it unset and the
# entrypoint falls back to 8000. Migrations + demo-user seeding run here
# (not baked into the image) so they apply on every container start,
# including Render's ephemeral filesystem. Invoked via `sh` (not made
# executable + exec'd directly) since local docker-compose bind-mounts the
# repo over the image, which would otherwise strip the executable bit.
CMD ["sh", "./docker-entrypoint.sh"]
