
import argparse

from pathlib import Path

from photosieve.scanner import ImageScanner


def format_size(size_bytes: int) -> str:
    size = float(size_bytes)

    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024:
            return f"{size:.2f} {unit}"

        size /= 1024

    return f"{size:.2f} PB"


def run_scan(directory: Path) -> None:
    scanner = ImageScanner()

    print()
    print("PhotoSieve - Image Scanner")
    print("=" * 50)
    print(f"Directory: {directory.expanduser().resolve()}")
    print("Scanning images...")
    print()

    try:
        result = scanner.scan(directory)

    except (FileNotFoundError, NotADirectoryError) as error:
        print(f"Error: {error}")
        return

    print("SCAN RESULTS")
    print("-" * 50)
    print(f"Directories scanned: {result.directories_scanned}")
    print(f"Image files examined: {result.files_examined}")
    print(f"Valid images: {result.total_images}")
    print(f"Invalid images: {len(result.errors)}")
    print(f"Total image size: {format_size(result.total_size_bytes)}")
    print(f"Execution time: {result.duration_seconds:.2f} seconds")

    if result.errors:
        print()
        print("ERRORS")
        print("-" * 50)

        for error in result.errors:
            print(f"File: {error.path}")
            print(f"Reason: {error.message}")
            print()

    if result.images_found:
        print()
        print("IMAGE INVENTORY")
        print("-" * 50)

        for image in result.images_found:
            dimensions = f"{image.width}x{image.height}"

            print(
                f"{image.filename:<35} "
                f"{dimensions:<12} "
                f"{format_size(image.size_bytes):>12}"
            )

    print()
    print("=" * 50)
    print("Scan completed.")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="photosieve",
        description="Intelligent Photo Deduplication and Management Tool",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    scan_parser = subparsers.add_parser(
        "scan",
        help="Scan a directory and inventory its images",
    )

    scan_parser.add_argument(
        "directory",
        type=Path,
        help="Directory containing images",
    )

    args = parser.parse_args()

    if args.command == "scan":
        run_scan(args.directory)


if __name__ == "__main__":
    main()
