import argparse
import json
from itertools import combinations
from pathlib import Path

from photosieve.comparison.analysis_cache import ImageAnalysisCache
from photosieve.comparison.hybrid_detector import find_hybrid_similarities
from photosieve.scanner import ImageScanner


def parse_args():
    parser = argparse.ArgumentParser(
        description="Evaluate PhotoSieve hybrid detection against benchmark ground truth."
    )

    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("data/benchmark_500"),
        help="Benchmark dataset directory.",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="Number of parallel workers.",
    )
    parser.add_argument(
        "--phash-threshold",
        type=int,
        default=12,
        help="Maximum pHash distance for candidate pairs.",
    )
    parser.add_argument(
        "--minimum-score",
        type=float,
        default=0.70,
        help="Minimum hybrid similarity score.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional JSON report path.",
    )

    return parser.parse_args()


def normalize_path(path: str | Path) -> str:
    return Path(path).resolve().as_posix()


def get_image_path(image) -> str:
    return normalize_path(image.path)


def calculate_metrics(true_positives, false_positives, false_negatives):
    precision = (
        true_positives / (true_positives + false_positives)
        if true_positives + false_positives
        else 0.0
    )

    recall = (
        true_positives / (true_positives + false_negatives)
        if true_positives + false_negatives
        else 0.0
    )

    f1_score = (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )

    return {
        "precision": precision,
        "recall": recall,
        "f1_score": f1_score,
    }


def main():
    args = parse_args()
    dataset = args.dataset.expanduser().resolve()
    manifest_path = dataset / "manifest.json"

    if not manifest_path.is_file():
        raise FileNotFoundError(f"Manifest not found: {manifest_path}")

    with manifest_path.open(encoding="utf-8") as file:
        manifest = json.load(file)

    manifest_images = {
        normalize_path(dataset / item["path"]): item
        for item in manifest["images"]
    }

    print("=" * 70)
    print("PHOTOSIEVE - BENCHMARK EVALUATION")
    print("=" * 70)
    print(f"Dataset: {dataset}")
    print(f"Workers: {args.workers}")
    print(f"pHash threshold: {args.phash_threshold}")
    print(f"Minimum score: {args.minimum_score:.2f}")
    print()

    print("Scanning images...")

    scan_result = ImageScanner().scan(dataset)
    images = scan_result.images_found

    print(f"Images found: {len(images)}")
    print(f"Scan errors: {len(scan_result.errors)}")

    if not images:
        raise RuntimeError("No valid images found in benchmark dataset.")

    scanned_paths = {
        normalize_path(image.path)
        for image in images
    }

    missing_from_manifest = scanned_paths - manifest_images.keys()

    if missing_from_manifest:
        raise RuntimeError(
            f"{len(missing_from_manifest)} scanned images are missing from manifest."
        )

    image_details = {
        path: {
            "path": manifest_images[path]["path"],
            "group_id": manifest_images[path]["group_id"],
            "category": manifest_images[path]["category"],
        }
        for path in scanned_paths
    }

    print()
    print("Running hybrid detection...")

    comparisons = find_hybrid_similarities(
        images,
        phash_threshold=args.phash_threshold,
        minimum_score=args.minimum_score,
        cache=ImageAnalysisCache(),
        max_workers=args.workers,
    )

    print(f"Detected pairs: {len(comparisons)}")

    actual_positive_pairs = set()

    for path_a, path_b in combinations(sorted(scanned_paths), 2):
        group_a = image_details[path_a]["group_id"]
        group_b = image_details[path_b]["group_id"]

        if group_a is not None and group_a == group_b:
            actual_positive_pairs.add((path_a, path_b))

    predicted_pairs = set()
    comparison_details = {}

    for comparison in comparisons:
        path_a = get_image_path(comparison.image_a)
        path_b = get_image_path(comparison.image_b)

        pair = tuple(sorted((path_a, path_b)))

        predicted_pairs.add(pair)
        comparison_details[pair] = {
            "similarity_score": comparison.similarity_score,
            "classification": comparison.classification,
            "phash_distance": comparison.phash_distance,
            "color_similarity": comparison.color_similarity,
            "metadata_similarity": comparison.metadata_similarity,
            "is_exact_duplicate": comparison.is_exact_duplicate,
        }

    true_positive_pairs = actual_positive_pairs & predicted_pairs
    false_positive_pairs = predicted_pairs - actual_positive_pairs
    false_negative_pairs = actual_positive_pairs - predicted_pairs

    true_positives = len(true_positive_pairs)
    false_positives = len(false_positive_pairs)
    false_negatives = len(false_negative_pairs)

    total_possible_pairs = len(images) * (len(images) - 1) // 2
    true_negatives = (
        total_possible_pairs
        - true_positives
        - false_positives
        - false_negatives
    )

    metrics = calculate_metrics(
        true_positives,
        false_positives,
        false_negatives,
    )

    print()
    print("=" * 70)
    print("EVALUATION RESULTS")
    print("=" * 70)
    print(f"Total images:             {len(images):>10,}")
    print(f"Possible pairs:           {total_possible_pairs:>10,}")
    print(f"Expected positive pairs:  {len(actual_positive_pairs):>10,}")
    print(f"Detected pairs:           {len(predicted_pairs):>10,}")
    print()
    print(f"True Positives (TP):      {true_positives:>10,}")
    print(f"False Positives (FP):     {false_positives:>10,}")
    print(f"False Negatives (FN):     {false_negatives:>10,}")
    print(f"True Negatives (TN):      {true_negatives:>10,}")
    print()
    print(f"Precision:                {metrics['precision'] * 100:>9.2f}%")
    print(f"Recall:                   {metrics['recall'] * 100:>9.2f}%")
    print(f"F1-score:                 {metrics['f1_score'] * 100:>9.2f}%")
    print("=" * 70)

    false_positive_details = []
    for pair in sorted(false_positive_pairs):
        detail = {
            "image_a": image_details[pair[0]],
            "image_b": image_details[pair[1]],
            **comparison_details[pair],
        }
        false_positive_details.append(detail)

    false_negative_details = [
        {
            "image_a": image_details[pair[0]],
            "image_b": image_details[pair[1]],
        }
        for pair in sorted(false_negative_pairs)
    ]

    if false_positive_details:
        print("\nFALSE POSITIVES")
        print("-" * 70)

        for item in false_positive_details:
            print(
                f"{item['image_a']['path']} <-> "
                f"{item['image_b']['path']}"
            )
            print(
                f"  Score: {item['similarity_score']:.4f} | "
                f"Classification: {item['classification']} | "
                f"pHash distance: {item['phash_distance']}"
            )

    if false_negative_details:
        print("\nFALSE NEGATIVES")
        print("-" * 70)

        for item in false_negative_details:
            print(
                f"{item['image_a']['path']} <-> "
                f"{item['image_b']['path']}"
            )

    report = {
        "dataset": str(dataset),
        "parameters": {
            "workers": args.workers,
            "phash_threshold": args.phash_threshold,
            "minimum_score": args.minimum_score,
        },
        "totals": {
            "images": len(images),
            "possible_pairs": total_possible_pairs,
            "expected_positive_pairs": len(actual_positive_pairs),
            "detected_pairs": len(predicted_pairs),
            "true_positives": true_positives,
            "false_positives": false_positives,
            "false_negatives": false_negatives,
            "true_negatives": true_negatives,
        },
        "metrics": metrics,
        "false_positives": false_positive_details,
        "false_negatives": false_negative_details,
    }

    if args.output:
        output_path = args.output.expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with output_path.open("w", encoding="utf-8") as file:
            json.dump(report, file, indent=4, ensure_ascii=False)

        print(f"\nJSON report saved: {output_path.resolve()}")

    print("\nEvaluation completed.")


if __name__ == "__main__":
    main()
