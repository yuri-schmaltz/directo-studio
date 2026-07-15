"""Encrypted credential vault backed by SQLite.

The vault stores arbitrary key/value strings with the values encrypted
at rest. The master key is derived from a passphrase via PBKDF2-HMAC-SHA256
or supplied directly as a base64url-encoded 32-byte key.

Typical lifecycle:
1. ``vault = CredentialVault.from_passphrase("...")`` (or
   ``CredentialVault.from_env("MAESTRO_VAULT_KEY")``)
2. ``vault.set("openai_api_key", "sk-...")``
3. ``vault.get("openai_api_key")`` → returns the plaintext, decrypts on
   demand, and never logs it
4. ``vault.rotate_key("new-passphrase")`` to re-encrypt everything
   atomically.
"""

from __future__ import annotations

import base64
import json
import os
import sqlite3
import threading
from pathlib import Path
from typing import Any, Iterator

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from directo.observability import get_logger

log = get_logger("directo.vault")

_PBKDF2_ITERATIONS = 600_000  # OWASP 2023 recommendation


class CredentialNotFound(KeyError):
    """Raised when a credential key does not exist in the vault."""


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    """Derive a 32-byte Fernet key from a passphrase + salt."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=_PBKDF2_ITERATIONS,
    )
    raw = kdf.derive(passphrase.encode("utf-8"))
    return base64.urlsafe_b64encode(raw)


class CredentialVault:
    """Encrypted credential store.

    :param db_path: path to SQLite database. Use ``":memory:"`` for tests.
    :param key: 32-byte Fernet key (base64url-encoded). If not provided,
        the vault is opened in "uninitialized" state — you must call
        :meth:`initialize` or use one of the ``from_*`` factories.
    """

    def __init__(self, db_path: str | Path, key: bytes | None = None) -> None:
        self._db_path = str(db_path)
        self._lock = threading.RLock()
        # SQLite with autocommit isolation for thread-safety.
        self._conn = sqlite3.connect(
            self._db_path,
            check_same_thread=False,
            isolation_level=None,  # autocommit
        )
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.row_factory = sqlite3.Row

        self._fernet: Fernet | None = None
        if key is not None:
            self._fernet = Fernet(key)

        self._migrate()

    # ----------------- Schema -----------------

    def _migrate(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS vault_meta (
                    id      INTEGER PRIMARY KEY CHECK (id = 1),
                    salt    BLOB NOT NULL,
                    kdf_it  INTEGER NOT NULL
                );

                CREATE TABLE IF NOT EXISTS vault_secrets (
                    name        TEXT PRIMARY KEY,
                    ciphertext  BLOB NOT NULL,
                    metadata    TEXT NOT NULL DEFAULT '{}',
                    created_at  REAL NOT NULL DEFAULT (unixepoch('now')),
                    updated_at  REAL NOT NULL DEFAULT (unixepoch('now')),
                    version     INTEGER NOT NULL DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS vault_audit (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts         REAL NOT NULL DEFAULT (unixepoch('now')),
                    event      TEXT NOT NULL,   -- set|get|delete|rotate|init
                    name       TEXT,
                    success    INTEGER NOT NULL
                );
                """
            )

    # ----------------- Factories -----------------

    @classmethod
    def from_passphrase(cls, passphrase: str, db_path: str | Path = ":memory:") -> "CredentialVault":
        """Open or initialize a vault from a passphrase.

        The salt is persisted in the database on first use and reused
        thereafter — changing the passphrase on an existing vault
        requires :meth:`rotate_key`.
        """
        vault = cls(db_path)
        row = vault._conn.execute("SELECT salt FROM vault_meta WHERE id = 1").fetchone()
        if row is None:
            salt = os.urandom(16)
            vault._conn.execute(
                "INSERT INTO vault_meta (id, salt, kdf_it) VALUES (1, ?, ?)",
                (salt, _PBKDF2_ITERATIONS),
            )
        else:
            salt = row["salt"]
        key = _derive_key(passphrase, salt)
        vault._fernet = Fernet(key)
        vault._audit("init", None, True)
        return vault

    @classmethod
    def from_env(cls, env_var: str = "MAESTRO_VAULT_KEY", db_path: str | Path = ":memory:") -> "CredentialVault":
        """Open a vault using a base64url-encoded key from an env var.

        Useful in containerized deployments where the key is supplied
        via a secret manager (Vault, AWS Secrets Manager, etc.).
        """
        raw = os.environ.get(env_var)
        if not raw:
            raise RuntimeError(
                f"Env var {env_var!r} is not set. "
                "Generate a key with `python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'`."
            )
        return cls(db_path, key=raw.encode("utf-8"))

    @classmethod
    def generate_key(cls) -> str:
        """Generate a fresh Fernet key (base64url string)."""
        return Fernet.generate_key().decode("utf-8")

    # ----------------- CRUD -----------------

    def set(self, name: str, value: str, **metadata: Any) -> None:
        """Encrypt and store a credential. Overwrites if it exists."""
        if self._fernet is None:
            raise RuntimeError("Vault not initialized. Use from_passphrase or pass a key.")
        if not isinstance(value, str):
            raise TypeError("Credential value must be a string")
        if not name or not isinstance(name, str):
            raise ValueError("Credential name must be a non-empty string")

        with self._lock:
            token = self._fernet.encrypt(value.encode("utf-8"))
            meta_json = json.dumps(metadata, default=str)
            cur = self._conn.execute(
                "SELECT version FROM vault_secrets WHERE name = ?", (name,)
            ).fetchone()
            if cur is None:
                self._conn.execute(
                    "INSERT INTO vault_secrets (name, ciphertext, metadata) "
                    "VALUES (?, ?, ?)",
                    (name, token, meta_json),
                )
            else:
                self._conn.execute(
                    "UPDATE vault_secrets "
                    "SET ciphertext = ?, metadata = ?, version = version + 1, "
                    "    updated_at = unixepoch('now') "
                    "WHERE name = ?",
                    (token, meta_json, name),
                )
            self._audit("set", name, True)

    def get(self, name: str) -> str:
        """Decrypt and return a credential. Raises :class:`CredentialNotFound`."""
        if self._fernet is None:
            raise RuntimeError("Vault not initialized.")
        with self._lock:
            row = self._conn.execute(
                "SELECT ciphertext FROM vault_secrets WHERE name = ?", (name,)
            ).fetchone()
            if row is None:
                self._audit("get", name, False)
                raise CredentialNotFound(f"Credential {name!r} not found in vault")
            try:
                value = self._fernet.decrypt(row["ciphertext"]).decode("utf-8")
            except InvalidToken as exc:
                self._audit("get", name, False)
                raise RuntimeError(
                    f"Failed to decrypt {name!r}. Master key may have changed."
                ) from exc
            self._audit("get", name, True)
            return value

    def delete(self, name: str) -> bool:
        """Delete a credential. Returns True if it existed."""
        with self._lock:
            cur = self._conn.execute("DELETE FROM vault_secrets WHERE name = ?", (name,))
            deleted = cur.rowcount > 0
            self._audit("delete", name, deleted)
            return deleted

    def list_names(self) -> list[str]:
        """Return the names of all stored credentials (never the values)."""
        with self._lock:
            return [
                r["name"]
                for r in self._conn.execute("SELECT name FROM vault_secrets ORDER BY name").fetchall()
            ]

    def has(self, name: str) -> bool:
        with self._lock:
            return self._conn.execute(
                "SELECT 1 FROM vault_secrets WHERE name = ?", (name,)
            ).fetchone() is not None

    def get_metadata(self, name: str) -> dict[str, Any]:
        with self._lock:
            row = self._conn.execute(
                "SELECT metadata FROM vault_secrets WHERE name = ?", (name,)
            ).fetchone()
            if row is None:
                raise CredentialNotFound(name)
            return json.loads(row["metadata"])

    # ----------------- Key rotation -----------------

    def rotate_key(self, new_passphrase: str) -> None:
        """Re-encrypt every credential under a new master key.

        Atomic: if anything fails, the old key still works and the DB
        is unchanged.
        """
        if self._fernet is None:
            raise RuntimeError("Vault not initialized.")

        new_salt = os.urandom(16)
        new_key = _derive_key(new_passphrase, new_salt)
        new_fernet = Fernet(new_key)

        with self._lock:
            rows = self._conn.execute("SELECT name, ciphertext FROM vault_secrets").fetchall()
            reencrypted: list[tuple[str, bytes]] = []
            for row in rows:
                try:
                    plaintext = self._fernet.decrypt(row["ciphertext"])
                except InvalidToken as exc:
                    raise RuntimeError(
                        f"Cannot rotate: existing credential {row['name']!r} cannot be "
                        f"decrypted with the current key."
                    ) from exc
                reencrypted.append((row["name"], new_fernet.encrypt(plaintext)))

            # All decrypts succeeded — commit the new state.
            self._conn.execute("BEGIN")
            try:
                for name, token in reencrypted:
                    self._conn.execute(
                        "UPDATE vault_secrets SET ciphertext = ?, updated_at = unixepoch('now') WHERE name = ?",
                        (token, name),
                    )
                self._conn.execute(
                    "UPDATE vault_meta SET salt = ?, kdf_it = ? WHERE id = 1",
                    (new_salt, _PBKDF2_ITERATIONS),
                )
                self._conn.execute("COMMIT")
            except Exception:
                self._conn.execute("ROLLBACK")
                raise

            self._fernet = new_fernet
            self._audit("rotate", None, True)
            log.info("vault key rotated; {} credentials re-encrypted", len(reencrypted))

    # ----------------- Audit -----------------

    def _audit(self, event: str, name: str | None, success: bool) -> None:
        try:
            self._conn.execute(
                "INSERT INTO vault_audit (event, name, success) VALUES (?, ?, ?)",
                (event, name, 1 if success else 0),
            )
        except sqlite3.Error:  # pragma: no cover — best-effort audit
            log.warning("failed to write vault audit row")

    def get_audit_log(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT ts, event, name, success FROM vault_audit "
                "ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    # ----------------- Context mgmt -----------------

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self) -> "CredentialVault":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
