"""SQLite database connection helper with concurrent-safe defaults.

Configures connection defaults for SQLite under high concurrency:
- Enables Write-Ahead Logging (WAL mode)
- Sets busy_timeout to prevent 'database is locked' errors
- Sets synchronous=NORMAL for optimal SSD performance
- Enables foreign key enforcement
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Union

PathLike = Union[str, Path]


def get_db_connection(
    db_path: PathLike,
    *,
    timeout: float = 10.0,
    check_same_thread: bool = False,
    isolation_level: Any = None,
) -> sqlite3.Connection:
    """Create and configure a resilient SQLite connection.

    :param db_path: Path to the SQLite database file or ":memory:"
    :param timeout: Wait timeout in seconds for locked tables before raising OperationalError
    :param check_same_thread: SQLite threading check flag
    :param isolation_level: Isolation level (None for autocommit / explicit transaction control)
    :return: Configured sqlite3.Connection instance
    """
    path_str = str(db_path)
    conn = sqlite3.connect(
        path_str,
        timeout=timeout,
        check_same_thread=check_same_thread,
        isolation_level=isolation_level,  # type: ignore[arg-type]
    )
    conn.row_factory = sqlite3.Row

    # PRAGMAs for WAL concurrency and performance
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")

    return conn
