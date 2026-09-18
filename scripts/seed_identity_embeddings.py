"""Idempotent demo seeder for identity_embeddings (see
app/models/identity_embedding.py) — real face embeddings computed from
real face photographs (the AT&T/Olivetti Faces dataset, a public academic
dataset; 40 anonymized subjects, 10 photos each — see
https://cs.nyu.edu/~roweis/data/olivettifaces.mat), so the multi-identity
clustering feature (app/services/identity_graph/graph.py) has genuine,
non-trivial embedding data to cluster instead of only synthetic test
vectors. Every declared name/document number here is invented for this
demo — the dataset's subjects are anonymized and were never told their
photos would be reused this way beyond the dataset's original academic
license, so no real name is ever attached to a real photo. Skips a
subject's seed rows if that subject's document number already exists.

Most subjects get 3 photos filed under one consistent demo identity —
an ordinary repeat crossing, which must NOT cluster as multi-identity.
A handful of subjects are deliberately filed under *two different*
demo identities (same face, different declared name/document number)
to produce real, verifiable CLUSTER_FOUND cases.

Usage (from project root, images already extracted to /tmp/olivetti_images
via scipy — see the accompanying extraction step):
    python -m scripts.seed_identity_embeddings
"""
import glob
import os

from app.db.session import SessionLocal
from app.repositories.identity_embedding_repository import insert_embedding, list_all
from app.services.face.embedding import extract_embedding

IMAGE_DIR = "/tmp/olivetti_images"
DOC_PREFIX = "OLV"

# Subjects 37-39 get filed under TWO demo identities each (their first
# two photos under identity A, next two under identity B) — a genuine
# same-face-different-identity fraud case for the identity graph to find.
MISMATCH_SUBJECTS = {37, 38, 39}


def _photos_for(subject: int) -> list[str]:
    pattern = os.path.join(IMAGE_DIR, f"subject_{subject:02d}_photo_*.png")
    return sorted(glob.glob(pattern))


def seed_identity_embeddings() -> None:
    if not os.path.isdir(IMAGE_DIR):
        raise SystemExit(f"{IMAGE_DIR} not found — extract the Olivetti images first")

    db = SessionLocal()
    try:
        existing_doc_numbers = {r.document_number for r in list_all(db) if r.document_number}
        inserted = 0

        for subject in range(40):
            photos = _photos_for(subject)
            if not photos:
                continue

            if subject in MISMATCH_SUBJECTS:
                doc_a = f"{DOC_PREFIX}{subject:03d}A"
                doc_b = f"{DOC_PREFIX}{subject:03d}B"
                if doc_a in existing_doc_numbers or doc_b in existing_doc_numbers:
                    print(f"subject {subject}: mismatch pair already seeded; skipping.")
                    continue
                name_a = f"Demo Subject {subject:02d}A"
                name_b = f"Demo Subject {subject:02d}B"
                for path in photos[:2]:
                    embedding = extract_embedding(open(path, "rb").read())
                    insert_embedding(db, name_a, doc_a, embedding)
                    inserted += 1
                for path in photos[2:4]:
                    embedding = extract_embedding(open(path, "rb").read())
                    insert_embedding(db, name_b, doc_b, embedding)
                    inserted += 1
                print(f"subject {subject}: seeded as TWO identities ({name_a} / {name_b}) — deliberate mismatch")
                continue

            doc_number = f"{DOC_PREFIX}{subject:03d}"
            if doc_number in existing_doc_numbers:
                print(f"subject {subject}: {doc_number} already seeded; skipping.")
                continue
            name = f"Demo Subject {subject:02d}"
            for path in photos[:3]:
                embedding = extract_embedding(open(path, "rb").read())
                insert_embedding(db, name, doc_number, embedding)
                inserted += 1
            print(f"subject {subject}: seeded 3 photos under one identity ({name})")

        print(f"\nInserted {inserted} identity embedding records.")
    finally:
        db.close()


if __name__ == "__main__":
    seed_identity_embeddings()
