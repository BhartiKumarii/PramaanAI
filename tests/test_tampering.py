import io
import os

from PIL import Image

from app.services.tampering.ela import block_statistics, compute_ela_image, most_anomalous_block
from app.services.tampering.pillow_provider import ELATamperingProvider

_PATCH_BOX = (280, 280, 340, 340)  # x0, y0, x1, y1


def _plain_document_bytes(size: tuple[int, int] = (400, 400)) -> bytes:
    image = Image.new("RGB", size, color="white")
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def _spliced_document_bytes(size: tuple[int, int] = (400, 400)) -> bytes:
    """A plain white document with a high-frequency random-noise patch
    pasted in — noise compresses far worse under JPEG than a flat region,
    so a real ELA pass should flag exactly this patch as anomalous."""
    image = Image.new("RGB", size, color="white")
    x0, y0, x1, y1 = _PATCH_BOX
    noise = Image.frombytes("RGB", (x1 - x0, y1 - y0), os.urandom((x1 - x0) * (y1 - y0) * 3))
    image.paste(noise, (x0, y0))
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    return buffer.getvalue()


def _overlaps(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> bool:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    return ax0 < bx1 and bx0 < ax1 and ay0 < by1 and by0 < ay1


def test_ela_flags_spliced_region_as_anomalous():
    blocks = block_statistics(compute_ela_image(_spliced_document_bytes()), grid=8)
    worst = most_anomalous_block(blocks)
    assert _overlaps((worst.x0, worst.y0, worst.x1, worst.y1), _PATCH_BOX)
    assert worst.z_score > 2.0


def test_ela_plain_document_has_no_strong_outlier():
    blocks = block_statistics(compute_ela_image(_plain_document_bytes()), grid=8)
    worst = most_anomalous_block(blocks)
    assert worst.z_score < 2.0


def test_provider_flags_higher_risk_for_spliced_than_plain():
    provider = ELATamperingProvider()
    plain_result = provider.analyze(_plain_document_bytes())
    spliced_result = provider.analyze(_spliced_document_bytes())

    assert spliced_result.tampering_risk > plain_result.tampering_risk
    finding = spliced_result.findings[0]
    assert finding.location is not None
    assert _overlaps(
        (finding.location["x0"], finding.location["y0"], finding.location["x1"], finding.location["y1"]),
        _PATCH_BOX,
    )
    assert str(round(finding.confidence, 2))[:1] != ""  # confidence is a real computed float
    assert "z-score" in finding.reason


def test_tampering_endpoint_requires_auth(client):
    response = client.post(
        "/documents/tampering",
        files={"file": ("doc.png", _spliced_document_bytes(), "image/png")},
    )
    assert response.status_code == 401


def test_tampering_endpoint_rejects_empty_file(client, db_session):
    from app.core.security import hash_password
    from app.models.user import User, UserRole

    user = User(username="tamperingtester", hashed_password=hash_password("Str0ngPass!"), role=UserRole.OFFICER)
    db_session.add(user)
    db_session.commit()
    token = client.post(
        "/auth/login", json={"username": "tamperingtester", "password": "Str0ngPass!"}
    ).json()["access_token"]

    response = client.post(
        "/documents/tampering",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("empty.png", b"", "image/png")},
    )
    assert response.status_code == 400
