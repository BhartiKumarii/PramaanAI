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
RUN pip install --no-cache-dir -r requirements.txt

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

# Render sets $PORT at runtime; docker-compose leaves it unset and the
# entrypoint falls back to 8000. Migrations + demo-user seeding run here
# (not baked into the image) so they apply on every container start,
# including Render's ephemeral filesystem. Invoked via `sh` (not made
# executable + exec'd directly) since local docker-compose bind-mounts the
# repo over the image, which would otherwise strip the executable bit.
CMD ["sh", "./docker-entrypoint.sh"]
