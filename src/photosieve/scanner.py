
import os
import time

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image, UnidentifiedImageError


SUPPORTED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".bmp",
    ".tif",
    ".tiff",
    ".gif",
}


@dataclass
class ImageInfo:
    path: str
    filename: str
    extension: str
    image_format: str
    size_bytes: int
    width: int
    height: int
    is_animated: bool


@dataclass
class ScanError:
    path: str
    message: str


@dataclass
class ScanResult:
    root_directory: str
    started_at: str
    duration_seconds: float = 0.0
    directories_scanned: int = 0
    files_examined: int = 0
    images_found: list[ImageInfo] = field(default_factory=list)
    errors: list[ScanError] = field(default_factory=list)

    @property
    def total_size_bytes(self) -> int:
        return sum(image.size_bytes for image in self.images_found)

    @property
    def total_images(self) -> int:
        return len(self.images_found)


class ImageScanner:

    def scan(self, directory: str | Path) -> ScanResult:
        root = Path(directory).expanduser().resolve()

        if not root.exists():
            raise FileNotFoundError(f"Directory not found: {root}")

        if not root.is_dir():
            raise NotADirectoryError(f"Not a directory: {root}")

        started = time.perf_counter()

        result = ScanResult(
            root_directory=str(root),
            started_at=datetime.now(timezone.utc).isoformat(),
        )

        def handle_walk_error(error: OSError) -> None:
            result.errors.append(
                ScanError(
                    path=str(error.filename or root),
                    message=str(error),
                )
            )

        for current_root, directories, filenames in os.walk(
            root,
            onerror=handle_walk_error,
            followlinks=False,
        ):
            directories[:] = sorted(
                directory
                for directory in directories
                if not (Path(current_root) / directory).is_symlink()
            )

            result.directories_scanned += 1

            for filename in sorted(filenames):
                file_path = Path(current_root) / filename

                if file_path.is_symlink():
                    continue

                if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                    continue

                result.files_examined += 1

                try:
                    image_info = self._analyze_image(file_path)

                    result.images_found.append(image_info)

                except (OSError, ValueError, UnidentifiedImageError) as error:
                    result.errors.append(
                        ScanError(
                            path=str(file_path),
                            message=str(error),
                        )
                    )

        result.duration_seconds = time.perf_counter() - started

        return result

    @staticmethod
    def _analyze_image(file_path: Path) -> ImageInfo:
        stat = file_path.stat()

        with Image.open(file_path) as image:
            image.verify()

        with Image.open(file_path) as image:
            return ImageInfo(
                path=str(file_path),
                filename=file_path.name,
                extension=file_path.suffix.lower(),
                image_format=image.format or "UNKNOWN",
                size_bytes=stat.st_size,
                width=image.width,
                height=image.height,
                is_animated=getattr(image, "is_animated", False),
            )
