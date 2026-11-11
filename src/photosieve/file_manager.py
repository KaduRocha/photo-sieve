"""
Ações sobre duplicatas exatas: mover para quarentena ou excluir.

Princípios de segurança:
- Duplicatas EXATAS (SHA-256 idêntico) podem ser movidas ou excluídas.
- Imagens apenas SEMELHANTES só podem ir para a quarentena (nunca excluídas)
  e a cópia mantida é sempre a de maior qualidade.
- Sempre existe uma cópia preservada por grupo.
- Antes de agir, o SHA-256 (exatas) ou o tamanho (semelhantes) é reverificado.
- Por padrão nada é alterado (dry-run); o chamador precisa pedir `apply`.
- A ação padrão é mover para quarentena (reversível), não excluir.
"""

import shutil
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from photosieve.comparison.hybrid_detector import HybridComparison
from photosieve.duplicate_detector import DuplicateGroup
from photosieve.hasher import calculate_sha256
from photosieve.scanner import ImageInfo


class ActionKind(StrEnum):
    MOVE = "move"
    DELETE = "delete"


@dataclass
class PlannedAction:
    kept: ImageInfo
    target: ImageInfo
    destination: Path | None  # None quando a ação é DELETE
    exact: bool = True  # False: apenas semelhante (sem igualdade de bytes)
    similarity_percent: float | None = None


@dataclass
class ActionFailure:
    path: str
    message: str


@dataclass
class ActionReport:
    kind: ActionKind
    applied: bool
    actions: list[PlannedAction] = field(default_factory=list)
    processed: list[PlannedAction] = field(default_factory=list)
    failures: list[ActionFailure] = field(default_factory=list)

    @property
    def bytes_affected(self) -> int:
        source = self.processed if self.applied else self.actions
        return sum(action.target.size_bytes for action in source)


def image_quality_key(image: ImageInfo) -> tuple:
    """Maior resolução, depois maior arquivo, depois caminho mais curto."""
    return (image.width * image.height, image.size_bytes, -len(image.path))


def choose_best_quality(images: list[ImageInfo]) -> ImageInfo:
    """Escolhe a imagem de melhor qualidade de forma determinística."""
    return max(
        sorted(images, key=lambda image: image.path),
        key=image_quality_key,
    )


def choose_image_to_keep(group: DuplicateGroup) -> ImageInfo:
    """
    Escolhe a cópia a preservar de forma determinística:
    caminho mais curto e, em seguida, ordem alfabética.
    """
    return min(group.images, key=lambda image: (len(image.path), image.path))


def default_quarantine_directory(root_directory: str | Path) -> Path:
    """Pasta irmã do diretório varrido, para não ser reanalisada depois."""
    root = Path(root_directory).resolve()
    return root.parent / f"{root.name}_photosieve_duplicates"


def plan_duplicate_actions(
    groups: list[DuplicateGroup],
    root_directory: str | Path,
    kind: ActionKind = ActionKind.MOVE,
    quarantine_directory: str | Path | None = None,
) -> list[PlannedAction]:
    """Gera o plano de ações sem tocar em nenhum arquivo."""
    root = Path(root_directory).resolve()
    quarantine = (
        Path(quarantine_directory).expanduser().resolve()
        if quarantine_directory
        else default_quarantine_directory(root)
    )

    if kind is ActionKind.MOVE and (
        quarantine == root or root in quarantine.parents
    ):
        raise ValueError(
            "A pasta de quarentena não pode ficar dentro do diretório analisado."
        )

    actions = []

    for group in groups:
        kept = choose_image_to_keep(group)

        for image in sorted(group.images, key=lambda item: item.path):
            if image is kept:
                continue

            destination = None

            if kind is ActionKind.MOVE:
                destination = quarantine / Path(image.path).resolve().relative_to(root)

            actions.append(
                PlannedAction(kept=kept, target=image, destination=destination)
            )

    return actions


def plan_similar_actions(
    comparisons: list[HybridComparison],
    root_directory: str | Path,
    quarantine_directory: str | Path | None = None,
    minimum_score: float = 0.90,
) -> list[PlannedAction]:
    """
    Planeja a quarentena de imagens semelhantes, mantendo a de maior qualidade.

    Usa agrupamento em estrela: cada imagem mantida só remove imagens que
    têm um par DIRETO com ela acima de `minimum_score`. Isso evita
    encadeamento (A≈B e B≈C não implica A≈C).
    """
    if not 0.0 <= minimum_score <= 1.0:
        raise ValueError("Minimum score must be between 0.0 and 1.0.")

    root = Path(root_directory).resolve()
    quarantine = (
        Path(quarantine_directory).expanduser().resolve()
        if quarantine_directory
        else default_quarantine_directory(root)
    )

    if quarantine == root or root in quarantine.parents:
        raise ValueError(
            "A pasta de quarentena não pode ficar dentro do diretório analisado."
        )

    images: dict[str, ImageInfo] = {}
    neighbors: dict[str, dict[str, HybridComparison]] = {}

    for comparison in comparisons:
        if not (
            comparison.is_exact_duplicate
            or comparison.similarity_score >= minimum_score
        ):
            continue

        for image, other in (
            (comparison.image_a, comparison.image_b),
            (comparison.image_b, comparison.image_a),
        ):
            images[image.path] = image
            neighbors.setdefault(image.path, {})[other.path] = comparison

    ordered = sorted(
        images.values(),
        key=lambda image: (tuple(-v for v in image_quality_key(image)), image.path),
    )

    handled: set[str] = set()
    actions = []

    for keeper in ordered:
        # Uma imagem já destinada à quarentena nunca pode ser representante
        # de outra: isso encadearia remoções (A≈B≈C) e poderia eliminar
        # todas as cópias de C.
        if keeper.path in handled:
            continue

        # Todas as imagens anteriores já foram tratadas, então qualquer
        # vizinho ainda livre tem qualidade menor ou igual à do keeper.
        handled.add(keeper.path)

        for other_path, comparison in sorted(neighbors[keeper.path].items()):
            if other_path in handled:
                continue

            handled.add(other_path)
            target = images[other_path]

            actions.append(
                PlannedAction(
                    kept=keeper,
                    target=target,
                    destination=quarantine / Path(target.path).resolve().relative_to(root),
                    exact=comparison.is_exact_duplicate,
                    similarity_percent=comparison.similarity_percent,
                )
            )

    return actions


def execute_actions(
    actions: list[PlannedAction],
    kind: ActionKind = ActionKind.MOVE,
    apply: bool = False,
) -> ActionReport:
    """
    Executa (ou simula) o plano.

    Com `apply=False` nenhum arquivo é alterado. Cada ação aplicada é
    precedida da reverificação do SHA-256 da cópia mantida e da alvo;
    se divergirem, a ação é registrada como falha e ignorada.
    """
    if kind is ActionKind.DELETE and any(not a.exact for a in actions):
        raise ValueError(
            "Imagens apenas semelhantes não podem ser excluídas; use a quarentena."
        )

    report = ActionReport(kind=kind, applied=apply, actions=list(actions))

    if not apply:
        return report

    for action in actions:
        target_path = Path(action.target.path)

        try:
            # Reverifica sem cache: o arquivo pode ter mudado desde a varredura.
            if action.exact:
                if (
                    calculate_sha256(action.kept.path)
                    != calculate_sha256(target_path)
                ):
                    raise RuntimeError("Os arquivos não são mais idênticos.")

            elif (
                Path(action.kept.path).stat().st_size != action.kept.size_bytes
                or target_path.stat().st_size != action.target.size_bytes
            ):
                raise RuntimeError("O arquivo mudou desde a análise.")

            if kind is ActionKind.DELETE:
                target_path.unlink()

            else:
                destination = action.destination

                if destination is None:
                    raise RuntimeError("Destino da quarentena não definido.")

                if destination.exists():
                    raise FileExistsError(
                        f"Destino já existe: {destination}"
                    )

                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(target_path), str(destination))

            report.processed.append(action)

        except (OSError, RuntimeError) as error:
            report.failures.append(
                ActionFailure(path=str(target_path), message=str(error))
            )

    return report
