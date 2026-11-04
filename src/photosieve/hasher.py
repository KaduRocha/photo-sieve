
import hashlib
from pathlib import Path

CHUNK_SIZE = 1024 * 1024  # 1 MB


def calculate_sha256(file_path: str | Path) -> str:
    """
    Calculate the SHA-256 hash of a file using incremental reading.

    The file is read in chunks to minimize memory consumption.
    """

    path = Path(file_path)

    initial_stat = path.stat()
    sha256 = hashlib.sha256()

    with path.open("rb") as file:
        while chunk := file.read(CHUNK_SIZE):
            sha256.update(chunk)

    final_stat = path.stat()

    if (
        initial_stat.st_size != final_stat.st_size
        or initial_stat.st_mtime_ns != final_stat.st_mtime_ns
    ):
        raise RuntimeError(f"File changed during hashing: {path}")

    return sha256.hexdigest()
