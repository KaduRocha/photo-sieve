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

        hashes = []

        for scale in CROP_SCALES:
            window_width = max(1, round(width * scale))
            window_height = max(1, round(height * scale))

            for row in range(CROP_WINDOW_POSITIONS):
                for column in range(CROP_WINDOW_POSITIONS):
                    left = round((width - window_width) * column / (CROP_WINDOW_POSITIONS - 1))
                    top = round((height - window_height) * row / (CROP_WINDOW_POSITIONS - 1))

                    window = normalized_image.crop(
                        (left, top, left + window_width, top + window_height)
                    )

                    hashes.append(imagehash.phash(window, hash_size=hash_size))

        return hashes
