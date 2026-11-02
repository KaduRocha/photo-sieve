from pathlib import Path

import imagehash

from PIL import Image, ImageOps


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