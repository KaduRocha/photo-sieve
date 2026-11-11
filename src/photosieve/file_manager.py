"""
Ações sobre duplicatas exatas: mover para quarentena ou excluir.

Princípios de segurança:
- Apenas duplicatas EXATAS (SHA-256 idêntico) são tratadas.
- Sempre existe uma cópia preservada por grupo.
- O SHA-256 é reverificado imediatamente antes de qualquer ação.
- Por padrão nada é alterado (dry-run); o chamador precisa pedir `apply`.
- A ação padrão é mover para quarentena (reversível), não excluir.
"""

import shutil
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

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
    report = ActionReport(kind=kind, applied=apply, actions=list(actions))

    if not apply:
        return report

    for action in actions:
        target_path = Path(action.target.path)

        try:
            # Reverifica sem cache: o arquivo pode ter mudado desde a varredura.
            if (
                calculate_sha256(action.kept.path)
                != calculate_sha256(target_path)
            ):
                raise RuntimeError("Os arquivos não são mais idênticos.")

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
