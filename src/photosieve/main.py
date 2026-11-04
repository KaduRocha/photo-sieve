
import argparse
from pathlib import Path

from photosieve.comparison.hybrid_detector import find_hybrid_similarities
from photosieve.duplicate_detector import find_exact_duplicates
from photosieve.scanner import ImageScanner
from photosieve.similarity_detector import find_similarity_groups


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
    print("=" * 60)

    try:
        result = scanner.scan(directory)

    except (FileNotFoundError, NotADirectoryError) as error:
        print(f"Error: {error}")
        return

    print(f"Directory: {result.root_directory}")
    print()
    print("SCAN RESULTS")
    print("-" * 60)
    print(f"Directories scanned: {result.directories_scanned}")
    print(f"Image files examined: {result.files_examined}")
    print(f"Valid images: {result.total_images}")
    print(f"Invalid images: {len(result.errors)}")
    print(f"Total image size: {format_size(result.total_size_bytes)}")
    print(f"Execution time: {result.duration_seconds:.2f} seconds")

    if result.images_found:
        print()
        print("IMAGE INVENTORY")
        print("-" * 60)

        for image in result.images_found:
            relative_path = Path(image.path).relative_to(
                result.root_directory
            )

            print(
                f"{relative_path!s:<55} "
                f"{image.width}x{image.height} "
                f"{format_size(image.size_bytes):>12}"
            )

    print()
    print("Scan completed.")


def run_duplicates(directory: Path) -> None:
    scanner = ImageScanner()

    print()
    print("PhotoSieve - Duplicate Detection")
    print("=" * 60)
    print(f"Directory: {directory.expanduser().resolve()}")
    print("Scanning and calculating SHA-256...")
    print()

    try:
        result = scanner.scan(directory)
        duplicate_groups = find_exact_duplicates(result.images_found)

    except (FileNotFoundError, NotADirectoryError, OSError, RuntimeError) as error:
        print(f"Error: {error}")
        return

    total_duplicates = sum(
        len(group.images) - 1
        for group in duplicate_groups
    )

    total_reclaimable = sum(
        group.reclaimable_bytes
        for group in duplicate_groups
    )

    print("DUPLICATE ANALYSIS")
    print("-" * 60)
    print(f"Images analyzed: {result.total_images}")
    print(f"Duplicate groups: {len(duplicate_groups)}")
    print(f"Duplicate files: {total_duplicates}")
    print(f"Potential space recovery: {format_size(total_reclaimable)}")

    for index, group in enumerate(duplicate_groups, start=1):
        print()
        print(f"GROUP {index}")
        print("-" * 60)
        print(f"SHA-256: {group.sha256}")
        print(f"Files: {len(group.images)}")
        print(f"Recoverable: {format_size(group.reclaimable_bytes)}")

        for image in group.images:
            relative_path = Path(image.path).relative_to(
                result.root_directory
            )
            print(f"  {relative_path}")

    if not duplicate_groups:
        print()
        print("No exact duplicates found.")

    print()
    print("=" * 60)
    print("No files were modified or deleted.")
    print("Duplicate analysis completed.")



def run_similar(directory: Path, threshold: int) -> None:
    scanner = ImageScanner()

    print()
    print("PhotoSieve - Visual Similarity Detection")
    print("=" * 60)
    print(f"Directory: {directory.expanduser().resolve()}")
    print(f"Similarity threshold: {threshold}/64")
    print("Scanning and calculating perceptual hashes...")
    print()

    try:
        result = scanner.scan(directory)

        groups = find_similarity_groups(
            result.images_found,
            threshold=threshold,
        )

    except (
        FileNotFoundError,
        NotADirectoryError,
        OSError,
        RuntimeError,
        ValueError,
    ) as error:
        print(f"Error: {error}")
        return

    grouped_images = sum(
        len(group.images)
        for group in groups
    )

    print("SIMILARITY ANALYSIS")
    print("-" * 60)
    print(f"Images analyzed: {result.total_images}")
    print(f"Similarity groups: {len(groups)}")
    print(f"Images in groups: {grouped_images}")
    print(f"Images without matches: {result.total_images - grouped_images}")

    for index, group in enumerate(groups, start=1):
        print()
        print(f"GROUP {index}")
        print("-" * 60)
        print(f"Files: {len(group.images)}")
        print(f"Classification: {group.classification}")
        print(f"Maximum distance: {group.max_distance}/64")
        print(f"Similarity: {group.similarity_percent:.2f}%")

        for image in group.images:
            relative_path = Path(image.path).relative_to(
                result.root_directory
            )

            print(f"  {relative_path}")

    if not groups:
        print()
        print("No similar image groups found.")

    print()
    print("=" * 60)
    print("No files were modified or deleted.")
    print("Similarity analysis completed.")



def run_analyze(
    directory: Path,
    phash_threshold: int,
    minimum_score: float,
    workers: int = 4,
) -> None:
    scanner = ImageScanner()

    print()
    print("PhotoSieve - Intelligent Photo Analysis")
    print("=" * 70)
    print(f"Directory: {directory.expanduser().resolve()}")
    print(f"Parallel workers: {workers}")
    print("Scanning images and analyzing similarities...")
    print()

    try:
        result = scanner.scan(directory)

        if len(result.images_found) < 2:
            print("At least two valid images are required for analysis.")
            print(f"Images found: {result.total_images}")
            return

        duplicate_groups = find_exact_duplicates(
            result.images_found
        )

        comparisons = find_hybrid_similarities(
            result.images_found,
            phash_threshold=phash_threshold,
            minimum_score=minimum_score,
            max_workers=workers,
        )

    except (
        FileNotFoundError,
        NotADirectoryError,
        OSError,
        RuntimeError,
        ValueError,
    ) as error:
        print(f"Error: {error}")
        return

    similar_comparisons = [
        comparison
        for comparison in comparisons
        if not comparison.is_exact_duplicate
    ]

    classification_counts = {
        "VERY_HIGH_SIMILARITY": 0,
        "HIGH_SIMILARITY": 0,
        "POSSIBLE_SIMILARITY": 0,
    }

    for comparison in similar_comparisons:
        classification_counts[comparison.classification] += 1

    total_duplicate_files = sum(
        len(group.images) - 1
        for group in duplicate_groups
    )

    total_reclaimable = sum(
        group.reclaimable_bytes
        for group in duplicate_groups
    )

    print("SCAN SUMMARY")
    print("-" * 70)
    print(f"Directories scanned: {result.directories_scanned}")
    print(f"Image files examined: {result.files_examined}")
    print(f"Valid images: {result.total_images}")
    print(f"Invalid images: {len(result.errors)}")
    print(f"Total image size: {format_size(result.total_size_bytes)}")
    print(f"Execution time: {result.duration_seconds:.2f} seconds")

    print()
    print("HYBRID ANALYSIS")
    print("-" * 70)
    print(f"Exact duplicate groups: {len(duplicate_groups)}")
    print(f"Duplicate files: {total_duplicate_files}")
    print(f"Very high similarity pairs: {classification_counts['VERY_HIGH_SIMILARITY']}")
    print(f"High similarity pairs: {classification_counts['HIGH_SIMILARITY']}")
    print(f"Possible similarity pairs: {classification_counts['POSSIBLE_SIMILARITY']}")
    print(f"Potentially recoverable space: {format_size(total_reclaimable)}")

    if duplicate_groups:
        print()
        print("EXACT DUPLICATES")
        print("-" * 70)

        for index, group in enumerate(duplicate_groups, start=1):
            print()
            print(f"GROUP {index}")
            print(f"Files: {len(group.images)}")
            print(f"Recoverable: {format_size(group.reclaimable_bytes)}")

            for image in group.images:
                relative_path = Path(image.path).relative_to(
                    result.root_directory
                )
                print(f"  {relative_path}")

    if similar_comparisons:
        print()
        print("SIMILAR IMAGE PAIRS")
        print("-" * 70)

        for index, comparison in enumerate(
            similar_comparisons,
            start=1,
        ):
            image_a = Path(comparison.image_a.path).relative_to(
                result.root_directory
            )
            image_b = Path(comparison.image_b.path).relative_to(
                result.root_directory
            )

            print()
            print(f"PAIR {index}")
            print(f"Classification: {comparison.classification}")
            print(f"Similarity: {comparison.similarity_percent:.2f}%")
            print(f"pHash distance: {comparison.phash_distance}/64")
            print(f"Color similarity: {comparison.color_similarity:.2%}")
            print(f"Metadata similarity: {comparison.metadata_similarity:.2%}")
            print(f"  {image_a}")
            print(f"  {image_b}")

    if not duplicate_groups and not similar_comparisons:
        print()
        print("No duplicate or similar images found.")

    if result.errors:
        print()
        print("SCAN ERRORS")
        print("-" * 70)

        for error in result.errors:
            print(f"{error.path}: {error.message}")

    print()
    print("=" * 70)
    print("No files were modified or deleted.")
    print("Hybrid analysis completed.")


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

    duplicate_parser = subparsers.add_parser(
        "duplicates",
        help="Find exact duplicate images using SHA-256",
    )

    duplicate_parser.add_argument(
        "directory",
        type=Path,
        help="Directory containing images",
    )

    similar_parser = subparsers.add_parser(
        "similar",
        help="Find visually similar images using pHash",
    )

    similar_parser.add_argument(
        "directory",
        type=Path,
        help="Directory containing images",
    )

    similar_parser.add_argument(
        "--threshold",
        type=int,
        default=6,
        help="Maximum Hamming distance (0-64, default: 6)",
    )

    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Run a complete hybrid image analysis",
    )

    analyze_parser.add_argument(
        "directory",
        type=Path,
        help="Directory containing images",
    )

    analyze_parser.add_argument(
        "--phash-threshold",
        type=int,
        default=12,
        help="Maximum pHash distance for candidate pairs (0-64, default: 12)",
    )

    analyze_parser.add_argument(
        "--minimum-score",
        type=float,
        default=0.70,
        help="Minimum hybrid similarity score (0.0-1.0, default: 0.70)",
    )

    analyze_parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Maximum number of parallel workers (default: 4)",
    )

    args = parser.parse_args()

    if args.command == "scan":
        run_scan(args.directory)

    elif args.command == "duplicates":
        run_duplicates(args.directory)

    elif args.command == "similar":
        run_similar(args.directory, args.threshold)

    elif args.command == "analyze":
        run_analyze(
            args.directory,
            args.phash_threshold,
            args.minimum_score,
            args.workers,
        )


if __name__ == "__main__":
    main()
