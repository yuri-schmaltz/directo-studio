"""Backup and restore utilities for Directo SQLite databases.

Backups are critical because Directo's entire state lives in SQLite
files. The :class:`BackupManager` provides:

- Online backups via SQLite's built-in backup API (safe even while
  other processes are writing).
- Multiple formats: single-file (``.db``), timestamped (``.db.YYYYMMDD-HHMMSS``),
  and compressed (``.db.gz``).
- Restore from any of those formats.
- Verification (PRAGMA integrity_check) on restore.
- Retention policy: keep the N most recent backups, prune older.

The manager is intentionally simple — Directo is multi-DB (queue,
gallery, vault, history, etc.) and each DB is its own backup target.
Use :class:`MultiBackup` to back up several DBs in one operation.
"""

from __future__ import annotations

import gzip
import shutil
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path

from directo.observability import get_logger

log = get_logger("directo.platform.backup")


@dataclass
class BackupResult:
    path: Path
    size_bytes: int
    duration_ms: float
    verified: bool
    error: str | None = None


class BackupManager:
    """Backup and restore for a single SQLite database."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(f"database not found: {self.db_path}")

    # ----------------- Backup -----------------

    def backup(
        self,
        output_dir: str | Path | None = None,
        *,
        timestamped: bool = True,
        compress: bool = True,
    ) -> BackupResult:
        """Create a backup of the database.

        :param output_dir: directory to write the backup. Default: same dir as the DB.
        :param timestamped: include timestamp in the filename.
        :param compress: gzip the backup.
        :return: :class:`BackupResult` with metadata.
        """
        start = time.perf_counter()
        if output_dir is None:
            output_dir = self.db_path.parent
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        stem = self.db_path.stem
        suffix = self.db_path.suffix or ".db"
        # Add microseconds to make each backup uniquely named within a second
        ts = time.strftime("%Y%m%d-%H%M%S") if timestamped else ""
        if timestamped:
            ts = f"{ts}-{int(time.time() * 1000) % 100000:05d}"
        name = f"{stem}.{ts}{suffix}" if ts else f"{stem}.backup{suffix}"
        out_path = output_dir / name

        # SQLite online backup (safe with concurrent writers)
        try:
            src = sqlite3.connect(str(self.db_path))
            dst = sqlite3.connect(str(out_path))
            with dst:
                src.backup(dst)
            src.close()
            dst.close()
        except Exception as exc:  # noqa: BLE001
            log.error(f"backup failed: {exc}")
            return BackupResult(
                path=out_path, size_bytes=0, duration_ms=0,
                verified=False, error=str(exc),
            )

        # Optionally compress
        if compress:
            gz_path = out_path.with_suffix(out_path.suffix + ".gz")
            with open(out_path, "rb") as f_in, gzip.open(gz_path, "wb", compresslevel=6) as f_out:
                shutil.copyfileobj(f_in, f_out)
            out_path.unlink()
            out_path = gz_path

        # Verify
        verified = self._verify(out_path)
        duration = (time.perf_counter() - start) * 1000
        result = BackupResult(
            path=out_path,
            size_bytes=out_path.stat().st_size,
            duration_ms=duration,
            verified=verified,
        )
        log.info(
            f"backup created: {out_path.name} ({out_path.stat().st_size:,} bytes, "
            f"verified={verified})"
        )
        return result

    # ----------------- Restore -----------------

    def restore(
        self,
        backup_path: str | Path,
        *,
        target_path: str | Path | None = None,
        verify_before: bool = True,
    ) -> BackupResult:
        """Restore from a backup file.

        :param backup_path: path to the backup file (compressed or not)
        :param target_path: where to write the restored DB. Default: original
            ``db_path``. The original is overwritten.
        :param verify_before: run PRAGMA integrity_check before restoring.
        """
        backup_path = Path(backup_path)
        if not backup_path.exists():
            return BackupResult(
                path=backup_path, size_bytes=0, duration_ms=0,
                verified=False, error=f"backup not found: {backup_path}",
            )
        target = Path(target_path) if target_path else self.db_path
        start = time.perf_counter()

        # Decompress if needed
        if backup_path.suffix == ".gz":
            decompressed = backup_path.with_suffix("")
            with gzip.open(backup_path, "rb") as f_in, open(decompressed, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
            work_path = decompressed
        else:
            work_path = backup_path

        if verify_before and not self._verify(work_path):
            return BackupResult(
                path=work_path, size_bytes=0, duration_ms=0,
                verified=False, error="backup failed integrity check",
            )

        # Atomic replace
        if target.exists():
            backup_of_target = target.with_suffix(target.suffix + ".pre-restore")
            shutil.copy2(target, backup_of_target)
            log.info(f"existing DB moved to {backup_of_target.name} for safety")
        shutil.copy2(work_path, target)
        if work_path != backup_path:
            work_path.unlink()  # cleanup decompressed temp
        duration = (time.perf_counter() - start) * 1000
        result = BackupResult(
            path=target,
            size_bytes=target.stat().st_size,
            duration_ms=duration,
            verified=True,
        )
        log.info(f"restored from {backup_path.name} → {target.name}")
        return result

    # ----------------- List / prune -----------------

    def list_backups(self, directory: str | Path | None = None) -> list[Path]:
        """List all backups of this DB in a directory (default: same dir as DB)."""
        directory = Path(directory) if directory else self.db_path.parent
        stem = self.db_path.stem
        backups: list[Path] = []
        for p in directory.iterdir():
            if not p.is_file():
                continue
            if p.name.startswith(stem + ".") and (p.suffix == ".gz" or p.suffix in (".db", ".sqlite", ".sqlite3")):
                backups.append(p)
        return sorted(backups, key=lambda p: p.stat().st_mtime, reverse=True)

    def prune(self, keep: int = 5, directory: str | Path | None = None) -> int:
        """Keep only the N most recent backups. Returns count pruned."""
        backups = self.list_backups(directory)
        # Exclude the source DB itself
        backups = [b for b in backups if b.resolve() != self.db_path.resolve()]
        if len(backups) <= keep:
            return 0
        to_delete = backups[keep:]
        for p in to_delete:
            p.unlink()
            log.info(f"pruned old backup: {p.name}")
        return len(to_delete)

    # ----------------- Internals -----------------

    def _verify(self, path: Path) -> bool:
        try:
            # Decompress on the fly if needed
            if path.suffix == ".gz":
                import gzip
                import tempfile
                with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
                    tmp.write(gzip.decompress(path.read_bytes()))
                    tmp_path = Path(tmp.name)
                try:
                    conn = sqlite3.connect(str(tmp_path))
                    cur = conn.execute("PRAGMA integrity_check")
                    row = cur.fetchone()
                    conn.close()
                    return row is not None and row[0] == "ok"
                finally:
                    tmp_path.unlink()
            conn = sqlite3.connect(str(path))
            cur = conn.execute("PRAGMA integrity_check")
            row = cur.fetchone()
            conn.close()
            return row is not None and row[0] == "ok"
        except Exception as exc:  # noqa: BLE001
            log.warning(f"verify failed for {path}: {exc}")
            return False


class MultiBackup:
    """Backup/restore multiple databases atomically (best-effort)."""

    def __init__(self, db_paths: dict[str, str | Path]) -> None:
        """``db_paths`` maps logical name to DB path (e.g. {"queue": "q.db", "gallery": "g.db"})."""
        self.db_paths = {k: Path(v) for k, v in db_paths.items()}

    def backup_all(
        self,
        output_dir: str | Path,
        *,
        timestamped: bool = True,
        compress: bool = True,
    ) -> dict[str, BackupResult]:
        results: dict[str, BackupResult] = {}
        for name, db_path in self.db_paths.items():
            mgr = BackupManager(db_path)
            results[name] = mgr.backup(output_dir, timestamped=timestamped, compress=compress)
        log.info(f"multi-backup complete: {len(results)} databases")
        return results

    def restore_all(
        self,
        backup_dir: str | Path,
        *,
        match_timestamp: str | None = None,
    ) -> dict[str, BackupResult]:
        """Restore all DBs from a single backup directory.

        If ``match_timestamp`` is given, only restore files matching that
        timestamp (e.g. ``"20250715-103000"``).
        """
        backup_dir = Path(backup_dir)
        results: dict[str, BackupResult] = {}
        for name, db_path in self.db_paths.items():
            stem = db_path.stem
            # Find matching backup
            candidates = list(backup_dir.glob(f"{stem}.*{db_path.suffix}*"))
            if match_timestamp:
                candidates = [c for c in candidates if match_timestamp in c.name]
            if not candidates:
                results[name] = BackupResult(
                    path=db_path, size_bytes=0, duration_ms=0, verified=False,
                    error="no matching backup found",
                )
                continue
            # Use the most recent matching
            candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            mgr = BackupManager(db_path)
            results[name] = mgr.restore(candidates[0])
        log.info(f"multi-restore complete: {len(results)} databases")
        return results
