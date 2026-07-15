"""Encrypted credential storage.

Provides :class:`CredentialVault` — a small key-value store where the
values are encrypted at rest using Fernet (AES-128-CBC + HMAC-SHA256)
with a master key derived from a passphrase via PBKDF2.

Design:
- The master key is **never** persisted. It is derived at startup
  from a passphrase or read from an env var.
- All credential values are stored encrypted. Decryption happens only
  on explicit :meth:`CredentialVault.get` call.
- The vault supports both a file-backed SQLite store and an in-memory
  store (for tests).
- Key rotation: changing the master key requires re-encrypting all
  stored credentials. :meth:`CredentialVault.rotate_key` does this
  atomically.

Usage:
    >>> vault = CredentialVault.from_passphrase("my-secret-passphrase")
    >>> vault.set("openai", "sk-abc123...")
    >>> vault.get("openai")
    'sk-abc123...'
    >>> vault.rotate_key("new-passphrase")
"""

from directo.vault.credentials import CredentialVault, CredentialNotFound

__all__ = ["CredentialVault", "CredentialNotFound"]
