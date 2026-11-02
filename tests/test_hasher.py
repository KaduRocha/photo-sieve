
from photosieve.hasher import calculate_sha256


def test_same_content_produces_same_hash(tmp_path):
    file_a = tmp_path / "photo_a.jpg"
    file_b = tmp_path / "photo_b.jpg"

    content = b"photo binary content"

    file_a.write_bytes(content)
    file_b.write_bytes(content)

    assert calculate_sha256(file_a) == calculate_sha256(file_b)


def test_different_content_produces_different_hash(tmp_path):
    file_a = tmp_path / "photo_a.jpg"
    file_b = tmp_path / "photo_b.jpg"

    file_a.write_bytes(b"photo A")
    file_b.write_bytes(b"photo B")

    assert calculate_sha256(file_a) != calculate_sha256(file_b)


def test_hash_empty_file(tmp_path):
    file_path = tmp_path / "empty.jpg"
    file_path.write_bytes(b"")

    result = calculate_sha256(file_path)

    assert result == (
        "e3b0c44298fc1c149afbf4c8996fb924"
        "27ae41e4649b934ca495991b7852b855"
    )
