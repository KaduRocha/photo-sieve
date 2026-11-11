import argparse
import sqlite3
from pathlib import Path

from photosieve import reporter
from photosieve.comparison.analysis_cache import ImageAnalysisCache
from photosieve.comparison.hybrid_detector import (
    CROP_PHASH_THRESHOLD,
    find_hybrid_similarities,
)
from photosieve.comparison.persistent_store import (
    DEFAULT_CACHE_PATH,
    PersistentStore,
)
from photosieve.duplicate_detector import find_exact_duplicates
from photosieve.file_manager import (
    ActionKind,
    default_quarantine_directory,
    execute_actions,
    plan_duplicate_actions,
    plan_similar_actions,
)
from photosieve.report_exporter import (
    AnalysisReport,
    validate_report_path,
    write_report,
)
from photosieve.reporter import format_size
from photosieve.scanner import ImageScanner
from photosieve.similarity_detector import find_similarity_groups

__all__ = ["format_size", "main"]


def _bounded_int(minimum: int, maximum: int | None = None):
    """Cria um tipo argparse que valida um inteiro dentro de um intervalo."""

    def parse(value: str) -> int:
        try:
            number = int(value)
        except ValueError as error:
            raise argparse.ArgumentTypeError(
                f"'{value}' não é um inteiro válido."
            ) from error

        if number < minimum or (maximum is not None and number > maximum):
            limit = f"{minimum}-{maximum}" if maximum is not None else f">= {minimum}"
            raise argparse.ArgumentTypeError(
                f"valor {number} fora do intervalo permitido ({limit})."
            )

        return number

    return parse


def _score_range(value: str) -> float:
    try:
        number = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            f"'{value}' não é um número válido."
        ) from error

    if not 0.0 <= number <= 1.0:
        raise argparse.ArgumentTypeError(
            f"valor {number} fora do intervalo permitido (0.0-1.0)."
        )

    return number


def run_scan(directory: Path) -> None:
    scanner = ImageScanner()

    reporter.print_header("PhotoSieve - Image Scanner")

    try:
        result = scanner.scan(directory)

    except (FileNotFoundError, NotADirectoryError) as error:
        print(f"Error: {error}")
        return

    print(f"Directory: {result.root_directory}")
    print()
    reporter.print_section("SCAN RESULTS")
    reporter.print_scan_summary(result)

    if result.images_found:
        print()
        reporter.print_section("IMAGE INVENTORY")

        for image in result.images_found:
            relative_path = reporter.relative_path(
                image.path, result.root_directory
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

    reporter.print_header("PhotoSieve - Duplicate Detection")
    print(f"Directory: {directory.expanduser().resolve()}")
    print("Scanning and calculating SHA-256...")
    print()

    try:
        result = scanner.scan(directory)
        duplicate_groups = find_exact_duplicates(result.images_found)

    except (FileNotFoundError, NotADirectoryError, OSError, RuntimeError) as error:
        print(f"Error: {error}")
        return

    total_duplicates = sum(len(group.images) - 1 for group in duplicate_groups)
    total_reclaimable = sum(group.reclaimable_bytes for group in duplicate_groups)

    reporter.print_section("DUPLICATE ANALYSIS")
    print(f"Images analyzed: {result.total_images}")
    print(f"Duplicate groups: {len(duplicate_groups)}")
    print(f"Duplicate files: {total_duplicates}")
    print(f"Potential space recovery: {format_size(total_reclaimable)}")

    for index, group in enumerate(duplicate_groups, start=1):
        reporter.print_duplicate_group(index, group, result.root_directory)

    if not duplicate_groups:
        print()
        print("No exact duplicates found.")

    reporter.print_footer("Duplicate analysis completed.")


def run_similar(directory: Path, threshold: int) -> None:
    scanner = ImageScanner()

    reporter.print_header("PhotoSieve - Visual Similarity Detection")
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

    grouped_images = sum(len(group.images) for group in groups)

    reporter.print_section("SIMILARITY ANALYSIS")
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
        reporter.print_image_paths(group.images, result.root_directory)

    if not groups:
        print()
        print("No similar image groups found.")

    reporter.print_footer("Similarity analysis completed.")


def run_analyze(
    directory: Path,
    phash_threshold: int,
    minimum_score: float,
    workers: int = 4,
    cache_path: Path | None = None,
    report_path: Path | None = None,
    detect_crops: bool = False,
    crop_threshold: int = CROP_PHASH_THRESHOLD,
) -> None:
    scanner = ImageScanner()
    width = 70
    store = None

    reporter.print_header("PhotoSieve - Intelligent Photo Analysis", width)
    print(f"Directory: {directory.expanduser().resolve()}")
    print(f"Parallel workers: {workers}")
    print(f"Crop detection: {'on' if detect_crops else 'off'}")
    print(f"Persistent cache: {cache_path if cache_path else 'off'}")
    print("Scanning images and analyzing similarities...")
    print()

    try:
        if report_path is not None:
            # Falha cedo, antes de uma análise potencialmente longa.
            report_path = validate_report_path(report_path)

        result = scanner.scan(directory)

        if len(result.images_found) < 2:
            print("At least two valid images are required for analysis.")
            print(f"Images found: {result.total_images}")
            return

        if cache_path is not None:
            store = PersistentStore(cache_path)

        # Cache compartilhado: o SHA-256 calculado na busca de duplicatas
        # exatas é reaproveitado pela análise híbrida.
        analysis_cache = ImageAnalysisCache(store)

        duplicate_groups = find_exact_duplicates(
            result.images_found,
            cache=analysis_cache,
        )

        comparisons = find_hybrid_similarities(
            result.images_found,
            phash_threshold=phash_threshold,
            minimum_score=minimum_score,
            cache=analysis_cache,
            max_workers=workers,
            detect_crops=detect_crops,
            crop_threshold=crop_threshold,
        )

    except (
        FileNotFoundError,
        NotADirectoryError,
        OSError,
        RuntimeError,
        ValueError,
        sqlite3.Error,
    ) as error:
        print(f"Error: {error}")
        return

    finally:
        if store is not None:
            store.close()

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

    total_duplicate_files = sum(len(group.images) - 1 for group in duplicate_groups)
    total_reclaimable = sum(group.reclaimable_bytes for group in duplicate_groups)

    reporter.print_section("SCAN SUMMARY", width)
    reporter.print_scan_summary(result)

    print()
    reporter.print_section("HYBRID ANALYSIS", width)
    print(f"Exact duplicate groups: {len(duplicate_groups)}")
    print(f"Duplicate files: {total_duplicate_files}")
    print(f"Very high similarity pairs: {classification_counts['VERY_HIGH_SIMILARITY']}")
    print(f"High similarity pairs: {classification_counts['HIGH_SIMILARITY']}")
    print(f"Possible similarity pairs: {classification_counts['POSSIBLE_SIMILARITY']}")
    print(f"Potentially recoverable space: {format_size(total_reclaimable)}")

    if duplicate_groups:
        print()
        reporter.print_section("EXACT DUPLICATES", width)

        for index, group in enumerate(duplicate_groups, start=1):
            reporter.print_duplicate_group(
                index,
                group,
                result.root_directory,
                show_sha256=False,
            )

    if similar_comparisons:
        print()
        reporter.print_section("SIMILAR IMAGE PAIRS", width)

        for index, comparison in enumerate(similar_comparisons, start=1):
            image_a = reporter.relative_path(
                comparison.image_a.path, result.root_directory
            )
            image_b = reporter.relative_path(
                comparison.image_b.path, result.root_directory
            )

            print()
            print(f"PAIR {index}")
            print(f"Classification: {comparison.classification}")
            print(f"Similarity: {comparison.similarity_percent:.2f}%")
            print(f"pHash distance: {comparison.phash_distance}/64")
            print(f"Color similarity: {comparison.color_similarity:.2%}")
            print(f"Metadata similarity: {comparison.metadata_similarity:.2%}")
            if comparison.is_crop_match:
                print(f"Crop match: yes (window distance {comparison.crop_distance}/64)")
            print(f"  {image_a}")
            print(f"  {image_b}")

    if not duplicate_groups and not similar_comparisons:
        print()
        print("No duplicate or similar images found.")

    reporter.print_scan_errors(result, width)

    if report_path is not None:
        try:
            written = write_report(
                AnalysisReport(
                    root_directory=result.root_directory,
                    parameters={
                        "phash_threshold": phash_threshold,
                        "minimum_score": minimum_score,
                        "workers": workers,
                        "detect_crops": detect_crops,
                        "crop_threshold": crop_threshold,
                    },
                    scan=result,
                    duplicate_groups=duplicate_groups,
                    comparisons=comparisons,
                ),
                report_path,
            )
            print()
            print(f"Report written: {written}")
        except OSError as error:
            print(f"Error writing report: {error}")

    reporter.print_footer("Hybrid analysis completed.", width)


def run_dedupe(
    directory: Path,
    quarantine_directory: Path | None = None,
    delete: bool = False,
    apply: bool = False,
    assume_yes: bool = False,
    similar: bool = False,
    minimum_score: float = 0.90,
    phash_threshold: int = 12,
    workers: int = 4,
    cache_path: Path | None = None,
    detect_crops: bool = False,
    crop_threshold: int = CROP_PHASH_THRESHOLD,
) -> None:
    scanner = ImageScanner()
    kind = ActionKind.DELETE if delete else ActionKind.MOVE
    store = None

    reporter.print_header("PhotoSieve - Duplicate Cleanup")
    print(f"Directory: {directory.expanduser().resolve()}")
    print(f"Action: {kind.value.upper()}")
    print(f"Scope: {'exact + similar images' if similar else 'exact duplicates'}")
    print(f"Mode: {'APPLY' if apply else 'DRY-RUN (no files will be changed)'}")

    try:
        if similar and delete:
            raise ValueError(
                "--delete não pode ser usado com --similar: "
                "imagens semelhantes só podem ir para a quarentena."
            )

        result = scanner.scan(directory)
        groups = []

        if kind is ActionKind.MOVE:
            quarantine = quarantine_directory or default_quarantine_directory(
                result.root_directory
            )
            print(f"Quarantine: {quarantine}")
        else:
            quarantine = None

        if cache_path is not None:
            store = PersistentStore(cache_path)

        analysis_cache = ImageAnalysisCache(store)

        if similar:
            comparisons = find_hybrid_similarities(
                result.images_found,
                phash_threshold=phash_threshold,
                minimum_score=minimum_score,
                cache=analysis_cache,
                max_workers=workers,
                detect_crops=detect_crops,
                crop_threshold=crop_threshold,
            )
            actions = plan_similar_actions(
                comparisons,
                result.root_directory,
                quarantine_directory=quarantine,
                minimum_score=minimum_score,
            )
        else:
            groups = find_exact_duplicates(
                result.images_found,
                cache=analysis_cache,
            )
            actions = plan_duplicate_actions(
                groups,
                result.root_directory,
                kind=kind,
                quarantine_directory=quarantine,
            )

    except (
        FileNotFoundError,
        NotADirectoryError,
        OSError,
        RuntimeError,
        ValueError,
        sqlite3.Error,
    ) as error:
        print(f"Error: {error}")
        return

    finally:
        if store is not None:
            store.close()

    print()
    reporter.print_section("PLAN")

    if not similar:
        print(f"Duplicate groups: {len(groups)}")

    print(f"Files to {kind.value}: {len(actions)}")
    print(
        f"Space affected: {format_size(sum(a.target.size_bytes for a in actions))}"
    )

    for action in actions:
        kept = reporter.relative_path(action.kept.path, result.root_directory)
        target = reporter.relative_path(action.target.path, result.root_directory)
        detail = ""

        if similar:
            detail = (
                "  (exact)"
                if action.exact
                else f"  ({action.similarity_percent:.2f}% similar)"
            )

        print()
        print(f"  KEEP    {kept}")
        print(f"  {kind.value.upper():<7} {target}{detail}")

    if not actions:
        print()
        print("Nothing to do.")
        return

    if not apply:
        print()
        print("=" * 60)
        print("Dry-run: no files were modified. Use --apply to execute.")
        return

    if delete and not assume_yes:
        answer = input(
            f"\nPermanently DELETE {len(actions)} file(s)? This cannot be undone. [y/N] "
        )

        if answer.strip().lower() not in {"y", "yes", "s", "sim"}:
            print("Cancelled. No files were modified.")
            return

    report = execute_actions(actions, kind=kind, apply=True)

    print()
    reporter.print_section("RESULT")
    print(f"Files processed: {len(report.processed)}")
    print(f"Space affected: {format_size(report.bytes_affected)}")
    print(f"Failures: {len(report.failures)}")

    for failure in report.failures:
        print(f"  {failure.path}: {failure.message}")

    print()
    print("=" * 60)
    print("Cleanup completed.")


def _add_crop_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--detect-crops",
        action="store_true",
        help="Also detect images that are crops of others (slower, more memory)",
    )
    parser.add_argument(
        "--crop-threshold",
        type=_bounded_int(0, 64),
        default=CROP_PHASH_THRESHOLD,
        help=f"Maximum pHash distance for crop matches (default: {CROP_PHASH_THRESHOLD})",
    )


def _add_cache_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--cache-db",
        type=Path,
        default=DEFAULT_CACHE_PATH,
        help=f"SQLite cache of analysis results (default: {DEFAULT_CACHE_PATH})",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Do not read or write the persistent cache",
    )


def _cache_path(args: argparse.Namespace) -> Path | None:
    return None if args.no_cache else args.cache_db


def build_parser() -> argparse.ArgumentParser:
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
    scan_parser.add_argument("directory", type=Path, help="Directory containing images")

    duplicate_parser = subparsers.add_parser(
        "duplicates",
        help="Find exact duplicate images using SHA-256",
    )
    duplicate_parser.add_argument(
        "directory", type=Path, help="Directory containing images"
    )

    similar_parser = subparsers.add_parser(
        "similar",
        help="Find visually similar images using pHash",
    )
    similar_parser.add_argument(
        "directory", type=Path, help="Directory containing images"
    )
    similar_parser.add_argument(
        "--threshold",
        type=_bounded_int(0, 64),
        default=6,
        help="Maximum Hamming distance (0-64, default: 6)",
    )

    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Run a complete hybrid image analysis",
    )
    analyze_parser.add_argument(
        "directory", type=Path, help="Directory containing images"
    )
    analyze_parser.add_argument(
        "--phash-threshold",
        type=_bounded_int(0, 64),
        default=12,
        help="Maximum pHash distance for candidate pairs (0-64, default: 12)",
    )
    analyze_parser.add_argument(
        "--minimum-score",
        type=_score_range,
        default=0.70,
        help="Minimum hybrid similarity score (0.0-1.0, default: 0.70)",
    )
    analyze_parser.add_argument(
        "--workers",
        type=_bounded_int(1),
        default=4,
        help="Maximum number of parallel workers (>= 1, default: 4)",
    )
    analyze_parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Write a report; format by extension: .json, .csv or .html",
    )
    _add_crop_arguments(analyze_parser)
    _add_cache_arguments(analyze_parser)

    dedupe_parser = subparsers.add_parser(
        "dedupe",
        help="Move (default) or delete exact duplicates, keeping one copy",
    )
    dedupe_parser.add_argument(
        "directory", type=Path, help="Directory containing images"
    )
    dedupe_parser.add_argument(
        "--quarantine-dir",
        type=Path,
        default=None,
        help="Where duplicates are moved (default: sibling '<dir>_photosieve_duplicates')",
    )
    dedupe_parser.add_argument(
        "--delete",
        action="store_true",
        help="Permanently delete duplicates instead of moving them",
    )
    dedupe_parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually execute the plan (default is a dry-run)",
    )
    dedupe_parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the confirmation prompt when deleting",
    )
    dedupe_parser.add_argument(
        "--similar",
        action="store_true",
        help="Also quarantine visually similar images, keeping the best quality "
        "(highest resolution, then size). Never combined with --delete",
    )
    dedupe_parser.add_argument(
        "--similar-min-score",
        type=_score_range,
        default=0.90,
        help="Minimum similarity to act on with --similar (0.0-1.0, default: 0.90)",
    )
    dedupe_parser.add_argument(
        "--phash-threshold",
        type=_bounded_int(0, 64),
        default=12,
        help="Maximum pHash distance for candidate pairs with --similar (default: 12)",
    )
    dedupe_parser.add_argument(
        "--workers",
        type=_bounded_int(1),
        default=4,
        help="Maximum number of parallel workers (>= 1, default: 4)",
    )
    _add_crop_arguments(dedupe_parser)
    _add_cache_arguments(dedupe_parser)

    return parser


def main() -> None:
    args = build_parser().parse_args()

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
            cache_path=_cache_path(args),
            report_path=args.report,
            detect_crops=args.detect_crops,
            crop_threshold=args.crop_threshold,
        )

    elif args.command == "dedupe":
        run_dedupe(
            args.directory,
            quarantine_directory=args.quarantine_dir,
            delete=args.delete,
            apply=args.apply,
            assume_yes=args.yes,
            similar=args.similar,
            minimum_score=args.similar_min_score,
            phash_threshold=args.phash_threshold,
            workers=args.workers,
            cache_path=_cache_path(args),
            detect_crops=args.detect_crops,
            crop_threshold=args.crop_threshold,
        )


if __name__ == "__main__":
    main()
