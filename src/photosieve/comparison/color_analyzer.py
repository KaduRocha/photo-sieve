
from pathlib import Path

from PIL import Image, ImageOps

HISTOGRAM_BINS = 32

# Weights for HSV channels.
HUE_WEIGHT = 0.50
SATURATION_WEIGHT = 0.25
VALUE_WEIGHT = 0.25


ColorHistogram = tuple[
    tuple[float, ...],
    tuple[float, ...],
    tuple[float, ...],
]


def calculate_color_histogram(
    file_path: str | Path,
) -> ColorHistogram:
    """
    Calculate a normalized HSV color histogram.

    The image is resized to a standard dimension to normalize
    the number of pixels analyzed.

    Returns normalized histograms for:
    - Hue
    - Saturation
    - Value
    """
    path = Path(file_path)

    with Image.open(path) as image:
        image.seek(0)

        normalized_image = ImageOps.exif_transpose(image)
        normalized_image = normalized_image.convert("HSV")
        normalized_image = normalized_image.resize((256, 256))

        raw_histogram = normalized_image.histogram()

    channels = []

    for channel_index in range(3):
        start = channel_index * 256
        end = start + 256

        channel_histogram = raw_histogram[start:end]

        grouped_histogram = [
            sum(channel_histogram[i:i + 8])
            for i in range(0, 256, 8)
        ]

        total = sum(grouped_histogram)

        normalized_histogram = tuple(
            count / total
            for count in grouped_histogram
        )

        channels.append(normalized_histogram)

    return tuple(channels)


def compare_color_histograms(
    histogram_a: ColorHistogram,
    histogram_b: ColorHistogram,
) -> float:
    """
    Compare two HSV histograms using histogram intersection.

    Returns a similarity score between 0.0 and 1.0.
    """
    if len(histogram_a) != 3 or len(histogram_b) != 3:
        raise ValueError("Histograms must contain three HSV channels.")

    if any(
        len(a) != len(b) or len(a) == 0
        for a, b in zip(histogram_a, histogram_b)
    ):
        raise ValueError("Histogram channels must have matching dimensions.")

    def intersection(
        channel_a: tuple[float, ...],
        channel_b: tuple[float, ...],
    ) -> float:
        return sum(
            min(value_a, value_b)
            for value_a, value_b in zip(channel_a, channel_b)
        )

    hue_similarity = intersection(
        histogram_a[0],
        histogram_b[0],
    )

    saturation_similarity = intersection(
        histogram_a[1],
        histogram_b[1],
    )

    value_similarity = intersection(
        histogram_a[2],
        histogram_b[2],
    )

    similarity = (
        hue_similarity * HUE_WEIGHT
        + saturation_similarity * SATURATION_WEIGHT
        + value_similarity * VALUE_WEIGHT
    )

    return max(0.0, min(1.0, similarity))


def calculate_color_similarity(
    image_a: str | Path,
    image_b: str | Path,
) -> float:
    """
    Calculate the color similarity between two images.
    """
    histogram_a = calculate_color_histogram(image_a)
    histogram_b = calculate_color_histogram(image_b)

    return compare_color_histograms(
        histogram_a,
        histogram_b,
    )
