from app.services.face.embedding import cosine_similarity, extract_embedding
from tests.synthetic_documents import generate_face_like_image as _face_like_image


def test_embedding_is_a_real_fixed_length_vector():
    embedding = extract_embedding(_face_like_image(1))
    assert len(embedding) > 0
    assert all(isinstance(v, float) for v in embedding)


def test_identical_image_has_similarity_near_one():
    image_bytes = _face_like_image(1)
    embedding_a = extract_embedding(image_bytes)
    embedding_b = extract_embedding(image_bytes)
    assert cosine_similarity(embedding_a, embedding_b) > 0.999


def test_different_images_have_lower_similarity_than_identical():
    same_a = extract_embedding(_face_like_image(1))
    same_b = extract_embedding(_face_like_image(1))
    different = extract_embedding(_face_like_image(7))

    same_similarity = cosine_similarity(same_a, same_b)
    different_similarity = cosine_similarity(same_a, different)
    assert same_similarity > different_similarity


def test_embedding_respects_crop_box():
    image_bytes = _face_like_image(1)
    full = extract_embedding(image_bytes)
    cropped = extract_embedding(image_bytes, box=(30, 30, 170, 190))
    assert full != cropped
