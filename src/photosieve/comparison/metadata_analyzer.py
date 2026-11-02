
from dataclasses import dataclass
from pathlib import Path

from PIL import ExifTags, Image, ImageOps


@dataclass
class ImageMetadata:
    width: int
    height: int
    format: str
    mode: str
    megapixels: float
    aspect_ratio: float
    has_transparency: bool
    camera_make: str | None
    camera_model: str | None
    date_taken: str | None
    orientation: int | None


def extract_image_metadata(
    file_path: str | Path,
) -> ImageMetadata:
    """
    Extract technical and EXIF metadata from an image.

    Missing EXIF information is represented by None.
    Image dimensions are normalized according to EXIF orientation.
    """
    path = Path(file_path)

    with Image.open(path) as image:
        exif = image.getexif()

        make = exif.get(ExifTags.Base.Make)
        model = exif.get(ExifTags.Base.Model)
        orientation = exif.get(ExifTags.Base.Orientation)

        date_taken = exif.get(ExifTags.Base.DateTimeOriginal)

        if date_taken is None:
            date_taken = exif.get(ExifTags.Base.DateTime)

        normalized_image = ImageOps.exif_transpose(image)

        width, height = normalized_image.size

        return ImageMetadata(
            width=width,
            height=height,
            format=image.format or "UNKNOWN",
            mode=image.mode,
            megapixels=round((width * height) / 1_000_000, 2),
            aspect_ratio=round(width / height, 4),
            has_transparency=(
                "A" in image.getbands()
                or "transparency" in image.info
            ),
            camera_make=str(make).strip() if make else None,
            camera_model=str(model).strip() if model else None,
            date_taken=str(date_taken).strip() if date_taken else None,
            orientation=int(orientation) if orientation is not None else None,
        )
