"""Password hashing with Argon2id (argon2-cffi).

argon2-cffi's defaults are Argon2id with the RFC 9106 low-memory profile (64 MiB,
3 passes, 4 lanes) and a random 16-byte salt. The hash is a PHC string
(``$argon2id$v=19$m=65536,t=3,p=4$<salt>$<hash>``) that carries its own salt and
parameters, so the parameters can be raised later without breaking old hashes.
"""

from __future__ import annotations

import asyncio

from argon2 import PasswordHasher

_hasher = PasswordHasher()


async def hash_password(password: str) -> str:
    """Hash ``password`` for ``users.password_hash``.

    Argon2 is slow on purpose (about 50–100 ms of CPU and 64 MiB of memory), so
    it runs in a worker thread instead of blocking every other request.
    """
    return await asyncio.to_thread(_hasher.hash, password)
