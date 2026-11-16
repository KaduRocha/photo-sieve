"""Formatação e impressão dos resultados exibidos pela CLI."""

from collections.abc import Iterable
from pathlib import Path

from photosieve.duplicate_detector import DuplicateGroup
from photosieve.scanner import ImageInfo, ScanResult


def format_size(size_bytes: int) -> str:
    """Converte bytes para uma string legível (B, KB, MB, GB, TB, PB)."""
    size = float(size_bytes)

    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            return f"{size:.2f} {unit}"

        size /= 1024

    return f"{size:.2f} PB"


def relative_path(path: str | Path, root_directory: str | Path) -> Path:
    """Retorna `path` relativo ao diretório raiz da varredura."""
    return Path(path).relative_to(root_directory)


def print_header(title: str, width: int = 60) -> None:
    print()
    print(title)
    print("=" * width)


def print_footer(message: str, width: int = 60) -> None:
    print()
    print("=" * width)
    print("No files were modified or deleted.")
    print(message)


def print_section(title: str, width: int = 60) -> None:
    print(title)
    print("-" * width)


def print_image_paths(
    images: Iterable[ImageInfo],
    root_directory: str | Path,
) -> None:
    for image in images:
        print(f"  {relative_path(image.path, root_directory)}")


def print_scan_summary(result: ScanResult, width: int = 60) -> None:
    print(f"Directories scanned: {result.directories_scanned}")
    print(f"Image files examined: {result.files_examined}")
    print(f"Valid images: {result.total_images}")
    print(f"Invalid images: {len(result.errors)}")
    print(f"Total image size: {format_size(result.total_size_bytes)}")
    print(f"Execution time: {result.duration_seconds:.2f} seconds")


def print_scan_errors(result: ScanResult, width: int = 70) -> None:
    if not result.errors:
        return

    print()
    print_section("SCAN ERRORS", width)

    for error in result.errors:
        print(f"{error.path}: {error.message}")


def print_duplicate_group(
    index: int,
    group: DuplicateGroup,
    root_directory: str | Path,
    width: int = 60,
    show_sha256: bool = True,
) -> None:
    print()
    print(f"GROUP {index}")

    if show_sha256:
        print("-" * width)
        print(f"SHA-256: {group.sha256}")

    print(f"Files: {len(group.images)}")
    print(f"Recoverable: {format_size(group.reclaimable_bytes)}")
    print_image_paths(group.images, root_directory)
