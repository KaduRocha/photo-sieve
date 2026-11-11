"""
Exportação dos resultados da análise para JSON, CSV e HTML.

O formato é escolhido pela extensão do arquivo de saída. O relatório HTML
é autocontido (miniaturas embutidas em base64) e todo conteúdo vindo do
sistema de arquivos é escapado.
"""

import base64
import csv
import html
import io
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image, ImageOps

from photosieve.comparison.hybrid_detector import HybridComparison
from photosieve.duplicate_detector import DuplicateGroup
from photosieve.file_manager import (
    choose_best_quality,
    choose_image_to_keep,
)
from photosieve.reporter import format_size, relative_path
from photosieve.scanner import ImageInfo, ScanResult

SUPPORTED_FORMATS = {".json", ".csv", ".html", ".htm"}
THUMBNAIL_SIZE = (220, 220)
CSV_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


@dataclass
class AnalysisReport:
    """Resultado completo de uma análise, pronto para exportação."""

    root_directory: str
    parameters: dict
    scan: ScanResult
    duplicate_groups: list[DuplicateGroup]
    comparisons: list[HybridComparison]

    @property
    def similar_comparisons(self) -> list[HybridComparison]:
        return [c for c in self.comparisons if not c.is_exact_duplicate]


def validate_report_path(path: str | Path) -> Path:
    """Valida a extensão antes de executar a análise (falha cedo)."""
    report_path = Path(path).expanduser()

    if report_path.suffix.lower() not in SUPPORTED_FORMATS:
        raise ValueError(
            "Formato de relatório não suportado: "
            f"'{report_path.suffix}'. Use .json, .csv ou .html."
        )

    return report_path


def _rel(report: AnalysisReport, path: str) -> str:
    return relative_path(path, report.root_directory).as_posix()


def _best_of(*images: ImageInfo) -> ImageInfo:
    return choose_best_quality(list(images))


def build_json_data(report: AnalysisReport) -> dict:
    scan = report.scan

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "directory": report.root_directory,
        "parameters": report.parameters,
        "summary": {
            "images": scan.total_images,
            "invalid_images": len(scan.errors),
            "total_size_bytes": scan.total_size_bytes,
            "exact_duplicate_groups": len(report.duplicate_groups),
            "similar_pairs": len(report.similar_comparisons),
            "reclaimable_bytes": sum(
                group.reclaimable_bytes for group in report.duplicate_groups
            ),
        },
        "exact_duplicates": [
            {
                "sha256": group.sha256,
                "reclaimable_bytes": group.reclaimable_bytes,
                "files": [
                    {
                        "path": _rel(report, image.path),
                        "size_bytes": image.size_bytes,
                    }
                    for image in group.images
                ],
            }
            for group in report.duplicate_groups
        ],
        "similar_pairs": [
            {
                "image_a": _rel(report, c.image_a.path),
                "image_b": _rel(report, c.image_b.path),
                "classification": c.classification,
                "similarity_percent": c.similarity_percent,
                "phash_distance": c.phash_distance,
                "color_similarity": round(c.color_similarity, 4),
                "metadata_similarity": round(c.metadata_similarity, 4),
                "is_crop_match": c.is_crop_match,
                "crop_distance": c.crop_distance,
                "suggested_keep": _rel(
                    report, _best_of(c.image_a, c.image_b).path
                ),
            }
            for c in report.similar_comparisons
        ],
        "errors": [
            {"path": error.path, "message": error.message}
            for error in scan.errors
        ],
    }


def _csv_safe(value) -> str:
    """Neutraliza 'formula injection' em planilhas (Excel/LibreOffice)."""
    text = str(value)

    if text.startswith(CSV_FORMULA_PREFIXES):
        return "'" + text

    return text


CSV_COLUMNS = [
    "kind",
    "group",
    "classification",
    "similarity_percent",
    "phash_distance",
    "color_similarity",
    "metadata_similarity",
    "is_crop_match",
    "path_a",
    "path_b",
    "suggested_keep",
]


def build_csv(report: AnalysisReport) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_COLUMNS)

    for index, group in enumerate(report.duplicate_groups, start=1):
        keeper = choose_image_to_keep(group)

        for other in group.images:
            if other is keeper:
                continue

            writer.writerow(
                [
                    "exact_duplicate",
                    index,
                    "EXACT_DUPLICATE",
                    100.0,
                    0,
                    1.0,
                    1.0,
                    False,
                    _csv_safe(_rel(report, keeper.path)),
                    _csv_safe(_rel(report, other.path)),
                    _csv_safe(_rel(report, keeper.path)),
                ]
            )

    for index, c in enumerate(report.similar_comparisons, start=1):
        writer.writerow(
            [
                "similar_pair",
                index,
                c.classification,
                c.similarity_percent,
                c.phash_distance,
                round(c.color_similarity, 4),
                round(c.metadata_similarity, 4),
                c.is_crop_match,
                _csv_safe(_rel(report, c.image_a.path)),
                _csv_safe(_rel(report, c.image_b.path)),
                _csv_safe(_rel(report, _best_of(c.image_a, c.image_b).path)),
            ]
        )

    return buffer.getvalue()


def _thumbnail_data_uri(path: str) -> str | None:
    try:
        with Image.open(path) as image:
            image.seek(0)
            thumbnail = ImageOps.exif_transpose(image).convert("RGB")
            thumbnail.thumbnail(THUMBNAIL_SIZE)

            buffer = io.BytesIO()
            thumbnail.save(buffer, format="JPEG", quality=75)
    except (OSError, ValueError):
        return None

    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")

    return f"data:image/jpeg;base64,{encoded}"


HTML_STYLE = """
:root{--bg:#fff;--fg:#1c1c1e;--muted:#6b6b70;--card:#f4f4f6;--line:#d8d8de;--accent:#0a6cff}
@media (prefers-color-scheme:dark){:root{--bg:#161618;--fg:#eee;--muted:#9a9aa2;--card:#222226;--line:#3a3a40;--accent:#5aa0ff}}
*{box-sizing:border-box}
body{margin:0;padding:16px;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;max-width:1100px;margin-inline:auto}
h1{font-size:1.5rem;margin:.2em 0}h2{font-size:1.15rem;margin-top:2rem;border-bottom:1px solid var(--line);padding-bottom:.3rem}
.muted{color:var(--muted)}
.summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:1rem 0}
.stat{background:var(--card);border-radius:8px;padding:10px 12px}.stat b{display:block;font-size:1.3rem}
.card{background:var(--card);border-radius:8px;padding:12px;margin:12px 0}
.row{display:flex;flex-wrap:wrap;gap:12px;margin-top:8px}
figure{margin:0;width:220px}figure img{width:100%;border-radius:6px;display:block;background:var(--line)}
figcaption{font-size:.8rem;word-break:break-all;margin-top:4px}
.keep{color:var(--accent);font-weight:600}
.tag{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:0 8px;font-size:.78rem;margin-right:4px}
"""


def build_html(report: AnalysisReport) -> str:
    esc = html.escape
    data = build_json_data(report)
    summary = data["summary"]
    thumbnails: dict[str, str | None] = {}

    def figure(image: ImageInfo, keep: bool) -> str:
        if image.path not in thumbnails:
            thumbnails[image.path] = _thumbnail_data_uri(image.path)

        uri = thumbnails[image.path]
        img = f'<img src="{uri}" alt="">' if uri else '<img alt="sem miniatura">'
        label = _rel(report, image.path)
        mark = '<span class="keep">manter</span> · ' if keep else ""

        return (
            f"<figure>{img}<figcaption>{mark}{esc(label)}<br>"
            f'<span class="muted">{image.width}x{image.height} · '
            f"{esc(format_size(image.size_bytes))}</span></figcaption></figure>"
        )

    parts = [
        "<!doctype html><html lang='pt-BR'><head><meta charset='utf-8'>",
        "<meta name='viewport' content='width=device-width,initial-scale=1'>",
        "<title>PhotoSieve - Relatório</title>",
        f"<style>{HTML_STYLE}</style></head><body>",
        "<h1>PhotoSieve - Relatório de análise</h1>",
        f"<p class='muted'>{esc(report.root_directory)} · {esc(data['generated_at'])}</p>",
        "<div class='summary'>",
        f"<div class='stat'><b>{summary['images']}</b>imagens</div>",
        f"<div class='stat'><b>{summary['exact_duplicate_groups']}</b>grupos de duplicatas</div>",
        f"<div class='stat'><b>{summary['similar_pairs']}</b>pares semelhantes</div>",
        f"<div class='stat'><b>{esc(format_size(summary['reclaimable_bytes']))}</b>recuperáveis</div>",
        "</div>",
    ]

    parts.append("<h2>Duplicatas exatas</h2>")

    if not report.duplicate_groups:
        parts.append("<p class='muted'>Nenhuma duplicata exata.</p>")

    for index, group in enumerate(report.duplicate_groups, start=1):
        keeper = choose_image_to_keep(group)
        parts.append(
            f"<div class='card'><b>Grupo {index}</b> · {len(group.images)} arquivos · "
            f"{esc(format_size(group.reclaimable_bytes))} recuperáveis"
            f"<br><span class='muted'>SHA-256 {esc(group.sha256)}</span><div class='row'>"
        )
        parts.extend(figure(image, image is keeper) for image in group.images)
        parts.append("</div></div>")

    parts.append("<h2>Imagens semelhantes</h2>")

    if not report.similar_comparisons:
        parts.append("<p class='muted'>Nenhum par semelhante.</p>")

    for index, c in enumerate(report.similar_comparisons, start=1):
        best = _best_of(c.image_a, c.image_b)
        crop = "<span class='tag'>recorte</span>" if c.is_crop_match else ""
        parts.append(
            f"<div class='card'><b>Par {index}</b> · {c.similarity_percent:.2f}% "
            f"<span class='tag'>{esc(c.classification)}</span>{crop}"
            f"<br><span class='muted'>pHash {c.phash_distance}/64 · "
            f"cor {c.color_similarity:.0%} · metadados {c.metadata_similarity:.0%}"
            "</span><div class='row'>"
        )
        parts.append(figure(c.image_a, c.image_a is best))
        parts.append(figure(c.image_b, c.image_b is best))
        parts.append("</div></div>")

    parts.append("</body></html>")

    return "".join(parts)


def write_report(report: AnalysisReport, path: str | Path) -> Path:
    """Grava o relatório no formato indicado pela extensão e devolve o caminho."""
    report_path = validate_report_path(path)
    suffix = report_path.suffix.lower()

    if suffix == ".json":
        content = json.dumps(build_json_data(report), indent=2, ensure_ascii=False)
    elif suffix == ".csv":
        content = build_csv(report)
    else:
        content = build_html(report)

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(content, encoding="utf-8", newline="")

    return report_path
