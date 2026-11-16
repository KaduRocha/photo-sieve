"""
Armazenamento persistente (SQLite) dos resultados de análise.

Cada entrada é identificada por (caminho resolvido, tamanho, mtime_ns,
feature). Se o arquivo mudar, a chave muda e o valor antigo deixa de ser
usado, portanto o cache nunca devolve resultado de um arquivo alterado.
"""

import sqlite3
from pathlib import Path
from threading import Lock
from typing import Self

SCHEMA_VERSION = 1

DEFAULT_CACHE_PATH = Path.home() / ".cache" / "photosieve" / "cache.db"


class PersistentStore:
    """Cache chave-valor em SQLite, seguro para uso por várias threads."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser()
        self.path.parent.mkdir(parents=True, exist_ok=True)

        self._lock = Lock()
        self._connection = sqlite3.connect(
            self.path,
            check_same_thread=False,
        )
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._initialize()

    def _initialize(self) -> None:
        with self._lock, self._connection:
            self._connection.execute(
                "CREATE TABLE IF NOT EXISTS meta "
                "(key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )

            row = self._connection.execute(
                "SELECT value FROM meta WHERE key = 'schema_version'"
            ).fetchone()

            if row is not None and int(row[0]) != SCHEMA_VERSION:
                # Cache é descartável: esquema incompatível é recriado.
                self._connection.execute("DROP TABLE IF EXISTS analysis")

            self._connection.execute(
                "INSERT OR REPLACE INTO meta (key, value) "
                "VALUES ('schema_version', ?)",
                (str(SCHEMA_VERSION),),
            )
            self._connection.execute(
                "CREATE TABLE IF NOT EXISTS analysis ("
                "path TEXT NOT NULL, size INTEGER NOT NULL, "
                "mtime_ns INTEGER NOT NULL, feature TEXT NOT NULL, "
                "value TEXT NOT NULL, "
                "PRIMARY KEY (path, size, mtime_ns, feature))"
            )

    def get(self, key: tuple, feature: str) -> str | None:
        path, size, mtime_ns = key

        with self._lock:
            row = self._connection.execute(
                "SELECT value FROM analysis "
                "WHERE path = ? AND size = ? AND mtime_ns = ? AND feature = ?",
                (path, size, mtime_ns, feature),
            ).fetchone()

        return row[0] if row else None

    def put(self, key: tuple, feature: str, value: str) -> None:
        path, size, mtime_ns = key

        with self._lock, self._connection:
            # Remove versões antigas do mesmo arquivo/feature (mtime/size
            # diferentes) para o banco não crescer a cada modificação.
            self._connection.execute(
                "DELETE FROM analysis WHERE path = ? AND feature = ? "
                "AND (size != ? OR mtime_ns != ?)",
                (path, feature, size, mtime_ns),
            )
            self._connection.execute(
                "INSERT OR REPLACE INTO analysis "
                "(path, size, mtime_ns, feature, value) VALUES (?, ?, ?, ?, ?)",
                (path, size, mtime_ns, feature, value),
            )

    def count(self) -> int:
        with self._lock:
            return self._connection.execute(
                "SELECT COUNT(*) FROM analysis"
            ).fetchone()[0]

    def clear(self) -> None:
        with self._lock, self._connection:
            self._connection.execute("DELETE FROM analysis")

    def close(self) -> None:
        with self._lock:
            self._connection.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()
