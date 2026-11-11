
import json
import random
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance

IMAGE_SIZE = (512, 512)
BASE_IMAGE_COUNT = 100
UNRELATED_IMAGE_COUNT = 100
RANDOM_SEED = 42


def generate_image(seed: int) -> Image.Image:
    rng = random.Random(seed)

    background = tuple(rng.randint(20, 235) for _ in range(3))
    image = Image.new("RGB", IMAGE_SIZE, background)
    draw = ImageDraw.Draw(image)

    for _ in range(18):
        color = tuple(rng.randint(20, 245) for _ in range(3))

        x1 = rng.randint(0, IMAGE_SIZE[0] - 1)
        y1 = rng.randint(0, IMAGE_SIZE[1] - 1)
        x2 = rng.randint(x1, IMAGE_SIZE[0])
        y2 = rng.randint(y1, IMAGE_SIZE[1])

        shape = rng.choice(["rectangle", "ellipse", "line"])

        if shape == "rectangle":
            draw.rectangle((x1, y1, x2, y2), fill=color)
        elif shape == "ellipse":
            draw.ellipse((x1, y1, x2, y2), fill=color)
        else:
            draw.line(
                (x1, y1, x2, y2),
                fill=color,
                width=rng.randint(2, 12),
            )

    return image


def generate_dataset(output_directory: Path) -> None:
    if output_directory.exists():
        raise FileExistsError(
            f"Output directory already exists: {output_directory}\n"
            "Choose another directory or remove the existing dataset."
        )

    categories = [
        "originals",
        "exact_duplicates",
        "resized",
        "brightness",
        "unrelated",
    ]

    for category in categories:
        (output_directory / category).mkdir(parents=True)

    manifest = {
        "seed": RANDOM_SEED,
        "image_size": IMAGE_SIZE,
        "base_image_count": BASE_IMAGE_COUNT,
        "unrelated_image_count": UNRELATED_IMAGE_COUNT,
        "images": [],
    }

    for index in range(BASE_IMAGE_COUNT):
        group_id = f"group_{index:04d}"
        image = generate_image(RANDOM_SEED + index)

        original_path = (
            output_directory
            / "originals"
            / f"{group_id}_original.png"
        )
        image.save(original_path, format="PNG")

        exact_path = (
            output_directory
            / "exact_duplicates"
            / f"{group_id}_exact.png"
        )
        shutil.copy2(original_path, exact_path)

        resized_path = (
            output_directory
            / "resized"
            / f"{group_id}_resized.jpg"
        )

        resized_image = image.resize(
            (448, 448),
            Image.Resampling.LANCZOS,
        )
        resized_image.save(
            resized_path,
            format="JPEG",
            quality=88,
        )

        brightness_path = (
            output_directory
            / "brightness"
            / f"{group_id}_brightness.jpg"
        )

        brightness_image = ImageEnhance.Brightness(image).enhance(1.08)
        brightness_image.save(
            brightness_path,
            format="JPEG",
            quality=92,
        )

        for category, path in [
            ("original", original_path),
            ("exact_duplicate", exact_path),
            ("resized", resized_path),
            ("brightness", brightness_path),
        ]:
            manifest["images"].append(
                {
                    "path": str(path.relative_to(output_directory)),
                    "group_id": group_id,
                    "category": category,
                }
            )

    for index in range(UNRELATED_IMAGE_COUNT):
        image = generate_image(
            RANDOM_SEED + 100_000 + index
        )

        path = (
            output_directory
            / "unrelated"
            / f"unrelated_{index:04d}.png"
        )

        image.save(path, format="PNG")

        manifest["images"].append(
            {
                "path": str(path.relative_to(output_directory)),
                "group_id": None,
                "category": "unrelated",
            }
        )

    manifest_path = output_directory / "manifest.json"

    with manifest_path.open("w", encoding="utf-8") as file:
        json.dump(
            manifest,
            file,
            indent=4,
            ensure_ascii=False,
        )

    print("Benchmark dataset generated successfully.")
    print(f"Output directory: {output_directory.resolve()}")
    print(f"Total images: {len(manifest['images'])}")
    print(f"Base groups: {BASE_IMAGE_COUNT}")
    print(f"Unrelated images: {UNRELATED_IMAGE_COUNT}")
    print(f"Manifest: {manifest_path.resolve()}")


def main() -> None:
    output_directory = (
        Path(sys.argv[1]).expanduser()
        if len(sys.argv) > 1
        else Path("data/benchmark_500")
    )

    generate_dataset(output_directory)


if __name__ == "__main__":
    main()
