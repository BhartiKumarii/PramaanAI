FROM python:3.11-slim

WORKDIR /app

# psycopg2-binary and cryptography ship manylinux wheels for this platform,
# so no compiler/libpq-dev is needed here. Add them back only if a future
# dependency (e.g. an ML lib without wheels) requires building from source.

# Tesseract binary + English language data for OCR (Module 1). Not a pip
# package — pytesseract just shells out to this binary.
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Render sets $PORT at runtime; docker-compose leaves it unset and the
# entrypoint falls back to 8000. Migrations + demo-user seeding run here
# (not baked into the image) so they apply on every container start,
# including Render's ephemeral filesystem. Invoked via `sh` (not made
# executable + exec'd directly) since local docker-compose bind-mounts the
# repo over the image, which would otherwise strip the executable bit.
CMD ["sh", "./docker-entrypoint.sh"]
