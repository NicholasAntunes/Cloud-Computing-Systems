"""Authentication: password hashing, the first admin and the current user.

Phase 1 has no login: ``current_user`` always returns the admin created at
startup, so every file belongs to that admin. Phase 2 adds login, tokens and
``require(right)`` here (docs/PLAN.md §5); only ``current_user`` changes, the
endpoints that depend on it don't.

Package layout:
    passwords.py  hash_password (Argon2id)
    users.py      ensure_admin, current_user
"""

from .passwords import hash_password
from .users import current_user, ensure_admin

__all__ = ["hash_password", "ensure_admin", "current_user"]
