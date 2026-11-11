import pytest
from PIL import Image, ImageDraw


def make_image(path, color="red", size=(100, 100), stripe=None):
    """Cria uma imagem de teste; `stripe` gera conteúdo visualmente distinto."""
    image = Image.new("RGB", size, color=color)

    if stripe is not None:
        ImageDraw.Draw(image).rectangle(
            (0, 0, size[0] // 2, size[1]), fill=stripe
        )

    image.save(path)
    return path


@pytest.fixture
def photo_dir(tmp_path):
    """
    Diretório com: 2 duplicatas exatas (a, a_copy), 1 imagem diferente (b)
    e 1 arquivo inválido (broken.jpg).
    """
    directory = tmp_path / "photos"
    directory.mkdir()

    make_image(directory / "a.png", "red", stripe="blue")
    make_image(directory / "a_copy.png", "red", stripe="blue")
    make_image(directory / "b.png", "green", stripe="yellow")
    (directory / "broken.jpg").write_bytes(b"not an image")

    return directory
