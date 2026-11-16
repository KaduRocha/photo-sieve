from pathlib import Path

import imagehash
from PIL import Image, ImageOps

import photosieve.formats  # noqa: F401  (registra HEIC, se disponível)


def calculate_phash(
    file_path: str | Path,
    hash_size: int = 8,
) -> imagehash.ImageHash:
    """
    Calculate the perceptual hash (pHash) of an image.

    EXIF orientation is normalized before calculating the hash.
    For animated images, the first frame is analyzed.
    """
    path = Path(file_path)

    with Image.open(path) as image:
        image.seek(0)

        normalized_image = ImageOps.exif_transpose(image)
        normalized_image = normalized_image.convert("RGB")

        return imagehash.phash(
            normalized_image,
            hash_size=hash_size,
        )

# Janelas usadas para detectar recortes: fração do lado da imagem original.
# Grade 5x5 x 6 escalas = 150 janelas: ponto de equilíbrio entre recall e custo
# medido em recortes aleatórios de fotos reais (ver README).
CROP_SCALES = (0.9, 0.85, 0.8, 0.75, 0.7, 0.65)
CROP_WINDOW_POSITIONS = 5  # grade 5x5 por escala

# Janelas de proporção livre (escala diferente em cada eixo), pois recortes
# manuais raramente preservam a proporção. Grade 3x3 por formato.
CROP_FREE_SHAPES = tuple(
    (width_scale, height_scale)
    for width_scale in (0.9, 0.8, 0.7)
    for height_scale in (0.9, 0.8, 0.7)
    if width_scale != height_scale
)
CROP_FREE_POSITIONS = 3

# Janelas por imagem: 6 escalas x 5x5 + 6 formatos livres x 3x3.
CROP_WINDOW_COUNT = (
    len(CROP_SCALES) * CROP_WINDOW_POSITIONS**2
    + len(CROP_FREE_SHAPES) * CROP_FREE_POSITIONS**2
)
CROP_ANALYSIS_SIZE = 256


def calculate_window_phashes(
    file_path: str | Path,
    hash_size: int = 8,
) -> list[imagehash.ImageHash]:
    """
    Calcula o pHash de janelas internas da imagem (grade 5x5 em várias escalas).

    Se a imagem B é um recorte da imagem A, o pHash global de B tende a ser
    próximo do pHash de alguma janela de A. Isso permite detectar recortes
    sem depender de features locais.
    """
    path = Path(file_path)

    with Image.open(path) as image:
        image.seek(0)

        normalized_image = ImageOps.exif_transpose(image)
        normalized_image = normalized_image.convert("RGB")
        normalized_image.thumbnail((CROP_ANALYSIS_SIZE, CROP_ANALYSIS_SIZE))

        width, height = normalized_image.size

        shapes = [(scale, scale, CROP_WINDOW_POSITIONS) for scale in CROP_SCALES]
        shapes += [
            (width_scale, height_scale, CROP_FREE_POSITIONS)
            for width_scale, height_scale in CROP_FREE_SHAPES
        ]

        hashes = []

        for width_scale, height_scale, positions in shapes:
            window_width = max(1, round(width * width_scale))
            window_height = max(1, round(height * height_scale))

            for row in range(positions):
                for column in range(positions):
                    left = round((width - window_width) * column / (positions - 1))
                    top = round((height - window_height) * row / (positions - 1))

                    window = normalized_image.crop(
                        (left, top, left + window_width, top + window_height)
                    )

                    hashes.append(imagehash.phash(window, hash_size=hash_size))

        return hashes


# Transformações geométricas (além da identidade) testadas na detecção de
# rotações e espelhamentos: os 7 elementos restantes do grupo diedral D4.
TRANSFORMS = (
    Image.Transpose.ROTATE_90,
    Image.Transpose.ROTATE_180,
    Image.Transpose.ROTATE_270,
    Image.Transpose.FLIP_LEFT_RIGHT,
    Image.Transpose.FLIP_TOP_BOTTOM,
    Image.Transpose.TRANSPOSE,
    Image.Transpose.TRANSVERSE,
)


def calculate_transform_phashes(
    file_path: str | Path,
    hash_size: int = 8,
) -> list[imagehash.ImageHash]:
    """
    Calcula o pHash da imagem rotacionada (90/180/270) e espelhada.

    Se a imagem B é a A girada ou espelhada, o pHash de B tende a ser
    próximo ao de alguma dessas variantes de A.
    """
    path = Path(file_path)

    with Image.open(path) as image:
        image.seek(0)

        normalized_image = ImageOps.exif_transpose(image)
        normalized_image = normalized_image.convert("RGB")

        return [
            imagehash.phash(
                normalized_image.transpose(transform),
                hash_size=hash_size,
            )
            for transform in TRANSFORMS
        ]
