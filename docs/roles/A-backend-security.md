# Role A — Backend & security

> Member: _TBD_
> Plan: [PLAN.md](../PLAN.md) · Presentation: [PRESENTATION.md](../PRESENTATION.md) · Other roles: [B](B-storage-versioning.md) · [C](C-frontend.md) · [D](D-devops-azure.md)

You own the REST API and everything to do with who may do what: login, tokens, rights and the security review.

## Sprint to the first presentation

Days are counted back from the presentation day (P).

| When | Task | Done when |
|---|---|---|
| Day 1 | Confirm the backend stack with the team (FastAPI by default, [PLAN §15](../PLAN.md#15-open-decisions)) | Decision written in PLAN.md |
| Day 1 | Agree the `storage.py` function signatures with **B** | Signatures in a short comment or issue that both of you approve |
| Day 1 | Agree the JSON shapes of the file endpoints with **C** ([PLAN §7](../PLAN.md#7-rest-api)) | Example responses in an issue, so C can build against a fake API |
| By P−5 | FastAPI skeleton: `api/app/main.py`, `config.py` (all settings from environment variables), `db.py`, minimal `files` table, `api/Dockerfile`, `pyproject.toml` | `docker compose up` starts the API; `/docs` loads |
| By P−3 | `POST /api/files`, `GET /api/files`, `GET /api/files/{id}/download` using B's `storage.py` | Upload → list → download works through Swagger UI |
| By P−3 | Enforce `MAX_UPLOAD_MB` while streaming; never read the whole file into memory | A file over the limit gets `413`, and memory stays flat |
| By P−2 | Smoke tests (pytest + httpx) for the three endpoints | Tests pass in D's CI |
| P−1 | Timed run-through with the team | — |

## Presentation

| Slides | Topic | Time |
|---|---|---|
| 9 | Objectives and limits, including the rights model | 1:30 |
| 10 | Sources | 0:30 |
| 11 | Tools and technologies | 1:00 |
| 12 | Risks | 1:00 |

Total 4:00. You take over from **C** after slide 8 and hand over to **D** for slide 13.

Also on you: fill in the team names, supervisor and date on the slides and in both team tables.

In Q&A, take questions on: authentication, JWT and logout, rights, password hashing, OWASP, the API design.

## After the presentation

| Phase | Your part |
|---|---|
| 2 — Auth & authorization (lead) | `users` table + Alembic; Argon2id hashing; login, access + refresh tokens, refresh endpoint; logout revokes the refresh token; roles + `file_permissions`; one `require(right)` dependency on every endpoint; admin create / deactivate users; login rate limiting; tests for every role × operation, ID guessing, expired / revoked tokens |
| 3 — LogBook | Call B's `log_event()` from every auth endpoint (`LOGIN`, `LOGIN_FAILED`, `LOGOUT`, `USER_CREATE`) |
| 5 — Version control | Rights checks (`READ` / `UPDATE`) on B's version endpoints |
| 6 — Hardening (lead on security) | Security review against OWASP ASVS: HSTS and security headers, CORS limited to our origin, generic error messages, `pip-audit` |
| 7 — Report | Security chapter |

## Works with

- **B:** `storage.py` interface; B's endpoints reuse your permission dependency.
- **C:** API contract, token handling in the browser.
- **D:** environment variables, CI, Key Vault secrets.
- Review **B**'s and **C**'s pull requests that touch the API.
