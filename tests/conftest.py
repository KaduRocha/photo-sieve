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


def make_scene(path, seed, size=(400, 400)):
    """Imagem sintética com formas aleatórias (determinística pela semente)."""
    import random

    rng = random.Random(seed)
    image = Image.new("RGB", size, tuple(rng.randint(20, 235) for _ in range(3)))
    draw = ImageDraw.Draw(image)

    for _ in range(18):
        color = tuple(rng.randint(20, 245) for _ in range(3))
        x1, y1 = rng.randint(0, size[0] - 1), rng.randint(0, size[1] - 1)
        x2, y2 = rng.randint(x1, size[0]), rng.randint(y1, size[1])
        draw.rectangle((x1, y1, x2, y2), fill=color)

    image.save(path)
    return image
