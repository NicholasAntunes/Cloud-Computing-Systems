# API Contract — Cloud File Exchange System

> The JSON shapes and rules the web client (role C) builds against. Owner: role A.
> Endpoint list and rights: [PLAN.md §7](PLAN.md#7-rest-api). If the code and this file disagree, the code is a bug; change both in the same pull request.

## General rules

| Rule | Value |
|---|---|
| Base path | `/api`, always called **relative** (`fetch('/api/files')`). The web app and the API share one origin behind Caddy, so no CORS and the refresh cookie just works |
| Format | JSON, `snake_case` field names (except uploads and downloads) |
| Dates | ISO 8601 in UTC with `Z`, to the second, e.g. `"2026-11-02T14:05:31Z"` |
| IDs | Files: UUID string. Users: integer |
| Sizes | Bytes, as integers (`size_bytes`) |
| Auth (from Phase 2) | `Authorization: Bearer <access_token>` on every request except login, refresh and the health check |
| Live spec | Swagger UI at `https://localhost/api/docs` once the API runs |
| Health check | `GET /api/health` → `200 {"status": "ok"}`, no token. It only shows the API process is up; it doesn't check the database or storage |

## Objects

### File

Returned by the list, upload and file detail endpoints.

```json
{
  "id": "6f1c2a9e-3b7d-4e0a-9c51-2d8f0b7a4e13",
  "name": "holiday.jpg",
  "content_type": "image/jpeg",
  "size_bytes": 2483021,
  "current_version": 3,
  "created_at": "2026-11-02T14:05:31Z",
  "updated_at": "2026-11-04T09:12:00Z",
  "owner":      { "id": 2, "username": "alice" },
  "updated_by": { "id": 3, "username": "bob" },
  "permissions": {
    "can_read": true,
    "can_update": true,
    "can_share": false,
    "can_delete": false
  }
}
```

- `size_bytes`, `updated_at` and `updated_by` describe the **current version**.
- `permissions` is what **the logged-in user** may do with **this file**. Use it to show or hide Download / New version / Restore / Share / Delete. Don't work rights out from `role` in the client; the server decides.
- Phase 1 (no login yet): every file belongs to the seeded admin user and every permission is `true`. The shape doesn't change later.

### User

Returned by login, refresh, `GET /api/auth/me` and the [user endpoints](#users-admin-only).

```json
{
  "id": 2,
  "username": "alice",
  "email": "alice@example.com",
  "role": "user",
  "is_active": true,
  "created_at": "2026-11-02T14:05:31Z",
  "capabilities": {
    "upload": true,
    "manage_users": false,
    "view_logbook": false
  }
}
```

- `role` is `viewer`, `user` or `admin`; show it as a label only.
- `capabilities` drives the global UI: `upload` → upload button; `manage_users` / `view_logbook` → admin pages.
- `is_active` and `created_at` are for the admin user list. For the logged-in user, `is_active` is always `true`.

### Version (Phase 5)

```json
{
  "version_no": 2,
  "size_bytes": 2480112,
  "sha256": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
  "uploaded_at": "2026-11-03T18:40:02Z",
  "uploaded_by": { "id": 2, "username": "alice" }
}
```

### LogEntry

One LogBook row. Returned by `GET /api/logbook` and the JSON export; the CSV export has the same fields as columns, in the same order.

```json
{
  "id": 1042,
  "ts": "2026-11-30T09:15:02Z",
  "user_id": 2,
  "username": "alice",
  "action": "DOWNLOAD",
  "success": true,
  "file_id": "6f1c2a9e-3b7d-4e0a-9c51-2d8f0b7a4e13",
  "version_no": 3,
  "ip": "192.0.2.10",
  "user_agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) …",
  "details": null
}
```

- Flat on purpose, so the list, the JSON export and the CSV columns are the same fields.
- `user_id` is `null` only for a `LOGIN_FAILED` with an unknown username; `username` is then the name that was typed.
- `file_id` and `version_no` are `null` when the action isn't about one file. `file_id` can name a file that doesn't exist: ID-guessing attempts are recorded too.
- `ip` is the client's address (Caddy passes it on; see D's `FORWARDED_ALLOW_IPS`). `user_agent` is cut to 512 characters.

| `action` | Written by |
|---|---|
| `LOGIN` / `LOGIN_FAILED` | `POST /api/auth/login`. `LOGIN_FAILED` is always `success: false`: wrong username or password, deactivated account, or rate-limited |
| `LOGOUT` | `POST /api/auth/logout` |
| `LIST` | `GET /api/files` |
| `UPLOAD` | `POST /api/files` |
| `UPDATE` | `POST /api/files/{id}/versions` (new version) |
| `DOWNLOAD` | `GET /api/files/{id}/download` |
| `RESTORE` | `POST /api/files/{id}/versions/{n}/restore` |
| `SHARE` | `PUT /api/files/{id}/permissions` |
| `DELETE` | `DELETE /api/files/{id}` |
| `USER_CREATE` | `POST /api/users` |
| `USER_DEACTIVATE` | `POST /api/users/{id}/deactivate` |

**One request, one entry.** Once the user is known, every request to one of these endpoints writes exactly one entry: `success: true` if it answers 2xx, otherwise `success: false`. A request turned away with `401` before the user is known (no token, expired token) writes nothing. Login is the exception: it always writes `LOGIN` or `LOGIN_FAILED`. A `DOWNLOAD` is recorded when the download starts; a connection dropped half-way isn't recorded as a failure.

`details` is `null` or one of:

| When | `details` |
|---|---|
| Any `success: false` | `{"error": "NOT_FOUND"}`: the error `code` the client got |
| `USER_CREATE`, `USER_DEACTIVATE` | `{"target_user_id": 5, "target_username": "bob"}` |
| `SHARE` | `{"target_user_id": 3, "can_read": true, "can_update": false}` |
| `RESTORE` | `{"from_version": 2}` |

## Files (Phase 1)

### List — `GET /api/files?limit=100&offset=0`

Returns only files the user may read, newest `updated_at` first. `limit` defaults to 100 and must be 1–1000; `offset` defaults to 0. Out of range or not a number → `400` `VALIDATION_ERROR`.

```json
200 OK
{ "items": [ /* File */ ], "total": 42 }
```

### Upload — `POST /api/files`

`multipart/form-data` with one field named **`file`**. Don't set the `Content-Type` header yourself; the browser adds the boundary.

```js
const form = new FormData();
form.append('file', input.files[0]);
await apiFetch('/api/files', { method: 'POST', body: form });
```

| Result | Response |
|---|---|
| Success | `201 Created`, body: File (with `current_version: 1`) |
| No `file` field / empty file / file name empty or over 255 characters | `400` `VALIDATION_ERROR` |
| Over 100 MB (`MAX_UPLOAD_MB`; 1 MB = 1024 × 1024 bytes) | `413` `FILE_TOO_LARGE` |
| No WRITE right (Phase 2) | `403` `FORBIDDEN` |

- Any file type is accepted. `content_type` is the type the browser sends with the file, or `application/octet-stream` if it is missing or not a valid header value.
- Uploading a name that already exists creates a **new, separate file** with a new `id`. New versions of a file come in Phase 5 (`POST /api/files/{id}/versions`).

`fetch` has no upload progress; use `XMLHttpRequest` (`xhr.upload.onprogress`) if you want a progress bar. Check the size on the client too (`file.size > 100 * 1024 * 1024`), so users don't wait to be told 413.

### Download — `GET /api/files/{id}/download[?version=n]`

**Direct stream** from the API, not a temporary URL. Reasons: Azurite doesn't support user-delegation SAS, files must only be reachable through the API (NFR7), and every download must be written to the LogBook.

- Response: the file bytes with `Content-Type`, `Content-Length` (usable for a progress bar), `Content-Disposition: attachment; filename="holiday.jpg"` and `X-Content-Type-Options: nosniff`. Always an attachment, whatever the type, so the browser saves the file and never renders it.
- `filename` is an ASCII fallback (other characters, `"` and `\` become `_`); the exact name is in `filename*=UTF-8''…` and in the File's `name`.
- Without `version` you get the current version.
- Unknown or deleted file, or no such version → `404` `NOT_FOUND`. `version` below 1 or not a number → `400` `VALIDATION_ERROR`.
- From Phase 2 a plain `<a href>` can't send the Bearer header, so download with `fetch` → `blob()` → object URL:

```js
const res = await apiFetch(`/api/files/${id}/download`);
const url = URL.createObjectURL(await res.blob());
const a = Object.assign(document.createElement('a'), { href: url, download: file.name });
a.click();
URL.revokeObjectURL(url);
```

Build it this way from Phase 1 so nothing changes later.

### File detail — `GET /api/files/{id}`

`200` File. Used to refresh one row after an action. Unknown, deleted or malformed ID → `404` `NOT_FOUND`.

## Authentication (Phase 2)

### Login — `POST /api/auth/login`

```json
{ "username": "alice", "password": "…" }
```

```json
200 OK
Set-Cookie: refresh_token=…; HttpOnly; Secure; SameSite=Strict; Path=/api/auth; Max-Age=604800

{
  "access_token": "eyJhbGciOi…",
  "token_type": "bearer",
  "expires_in": 900,
  "user": { /* User */ }
}
```

| Result | Response |
|---|---|
| Wrong username **or** password, or account deactivated | `401` `INVALID_CREDENTIALS` (same message for all, so usernames can't be guessed) |
| Too many attempts | `429` `RATE_LIMITED` with a `Retry-After` header (seconds) |

The username is matched case-insensitively: usernames are stored in lower case and login lowercases what was typed, so a phone keyboard that capitalises the first letter doesn't break login.

### Tokens

- **Access token:** JWT, 15 min, sent as `Authorization: Bearer <token>`. Keep it **in memory only** (React state / a module variable), not `localStorage`, so XSS can't steal it.
- **Refresh token:** 7 days, `HttpOnly` cookie. The client never reads it; the browser sends it to `/api/auth/*` automatically.

### Refresh — `POST /api/auth/refresh`

No body. `200` with the same body as login and a new refresh cookie (rotated). `401` → show the login page.

Call it:
1. **On page load**, to get an access token after a reload (if it returns 401, the user isn't logged in).
2. **When any request returns 401** `TOKEN_EXPIRED`: refresh once, then retry the original request once. If refresh fails, go to login.

### Logout — `POST /api/auth/logout`

`204 No Content`. Revokes the refresh token and clears the cookie. Then drop the access token from memory.

### Current user — `GET /api/auth/me`

`200` User.

## Users (admin only)

Every endpoint here needs `role = admin`; anyone else gets `403` `FORBIDDEN`.

### List — `GET /api/users?limit=100&offset=0`

`200 { "items": [User], "total": n }`, sorted by username, deactivated users included. `limit` and `offset` work as for the file list.

### Create — `POST /api/users`

```json
{ "username": "bob", "email": "bob@example.com", "password": "…", "role": "user" }
```

`201` User. Invalid input → `400` `VALIDATION_ERROR` with `details` per field.

| Field | Rule |
|---|---|
| `username` | 3–50 characters: lower-case letters, digits, `.`, `_`, `-`. Already taken → `VALIDATION_ERROR` on `username` |
| `email` | Contains `@`, at most 254 characters |
| `password` | 12–128 characters, no other rules (NIST SP 800-63B: length matters, composition rules don't). Stored only as an Argon2id hash |
| `role` | `viewer`, `user` or `admin` |

### Deactivate — `POST /api/users/{id}/deactivate`

`200` User with `"is_active": false`. One transaction sets `is_active = false`, revokes every refresh token of that user and writes the `USER_DEACTIVATE` entry.

- It takes effect at once, not after the 15-minute access token runs out: `current_user` reads the user from the database on every request, so the user's next request gets `401` `TOKEN_EXPIRED`, the refresh fails, and the client shows the login page. Logging in again gives `401` `INVALID_CREDENTIALS`.
- The user's files and LogBook entries stay.
- Already deactivated → `200`, nothing changes.
- Your own account → `400` `VALIDATION_ERROR`, so an admin can't lock themselves out.
- Unknown ID → `404` `NOT_FOUND`.
- There is no reactivate endpoint.

## LogBook (admin only)

Every endpoint here needs `role = admin`; anyone else gets `403` `FORBIDDEN`. Entries: [LogEntry](#logentry).

### List — `GET /api/logbook?user=&action=&success=&from=&to=&limit=100&offset=0`

`200 { "items": [LogEntry], "total": n }`, newest first. Every filter is optional; an invalid value → `400` `VALIDATION_ERROR`.

| Parameter | Meaning |
|---|---|
| `user` | Username, case-insensitive. Also finds `LOGIN_FAILED` entries for a name that was typed |
| `action` | One action from the [LogEntry](#logentry) table |
| `success` | `true` or `false` |
| `from`, `to` | ISO 8601 in UTC; `from` included, `to` excluded |
| `limit`, `offset` | As for the file list (`limit` 1–1000) |

### Export — `GET /api/logbook/export?format=csv|json` (plus the same filters)

Every matching entry, no paging, newest first, as a download: `Content-Disposition: attachment; filename="logbook-20261130T091502Z.csv"` (or `.json`). Download it with the same `fetch` → `blob()` pattern as files.

- **JSON:** an array of LogEntry.
- **CSV:** UTF-8 with a byte-order mark (so Excel shows non-ASCII names correctly) and one header row. Columns, in this order: `id,ts,user_id,username,action,success,file_id,version_no,ip,user_agent,details`. `null` is an empty cell, `success` is `true` / `false`, `details` is compact JSON.
- **Formula injection:** a cell that starts with `=`, `+`, `-`, `@`, a tab or a carriage return gets a leading `'`, so a spreadsheet shows it as text instead of running it. `username` and `user_agent` come straight from the client, so this is a real risk.

## Errors

Every error has the same body:

```json
{
  "error": {
    "code": "FILE_TOO_LARGE",
    "message": "The file is larger than the 100 MB limit.",
    "details": null
  }
}
```

- `code` is stable; branch on it in the UI.
- `message` is safe to show to users. It never contains stack traces or internal details.
- `details` is only set for `VALIDATION_ERROR`: a list of `{ "field": "file", "message": "…" }`.

| Status | `code` | When |
|---|---|---|
| 400 | `VALIDATION_ERROR` | Missing or invalid input |
| 401 | `NOT_AUTHENTICATED` | No token |
| 401 | `TOKEN_EXPIRED` | Access token expired or invalid → refresh and retry |
| 401 | `INVALID_CREDENTIALS` | Login failed |
| 403 | `FORBIDDEN` | The user can see the file but lacks this right (e.g. UPDATE); a `viewer` tries to upload; a non-admin calls an admin endpoint |
| 404 | `NOT_FOUND` | The file doesn't exist **or the user may not read it**. We don't reveal that a file exists. Also for a malformed ID and an unknown route |
| 405 | `METHOD_NOT_ALLOWED` | The route exists, but not with this HTTP method |
| 409 | `CONFLICT` | Simultaneous new versions; retry |
| 413 | `FILE_TOO_LARGE` | Over `MAX_UPLOAD_MB` |
| 429 | `RATE_LIMITED` | Too many login attempts |
| 500 | `INTERNAL_ERROR` | Anything unexpected; generic message |
| 503 | `STORAGE_UNAVAILABLE` | Blob Storage can't be reached or failed; retry later |

Successful responses use `200 OK`, `201 Created` (upload, new version, restore) and `204 No Content` (logout, delete).

## Suggested client wrapper

One function that every call goes through, so Phase 2 only changes this file:

```ts
let accessToken: string | null = null;

// Login, refresh and logout must never trigger a refresh-and-retry themselves.
const NO_RETRY = ['/api/auth/login', '/api/auth/refresh', '/api/auth/logout'];

export async function login(username: string, password: string): Promise<User> {
  const res = await apiFetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  const body = await res.json();
  accessToken = body.access_token;
  return body.user;
}

// Call on page load too: returns the user if the refresh cookie is still valid, otherwise null.
export async function refresh(): Promise<User | null> {
  const res = await fetch('/api/auth/refresh', { method: 'POST' });
  if (!res.ok) {
    accessToken = null;
    return null;
  }
  const body = await res.json();
  accessToken = body.access_token;
  return body.user;
}

export async function logout(): Promise<void> {
  await apiFetch('/api/auth/logout', { method: 'POST' }).catch(() => {});
  accessToken = null;
}

export async function apiFetch(path: string, init: RequestInit = {}, retried = false): Promise<Response> {
  const headers = new Headers(init.headers);
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`);
  const res = await fetch(path, { ...init, headers });

  if (res.status === 401 && !retried && !NO_RETRY.includes(path)) {
    if (await refresh()) return apiFetch(path, init, true);
  }
  if (!res.ok) throw await res.json().then(b => b.error).catch(() => ({ code: 'INTERNAL_ERROR', message: res.statusText }));
  return res;
}
```

## Later phases (shapes only, details follow)

| Endpoint | Request | Response |
|---|---|---|
| `GET /api/files/{id}/versions` | — | `200 { "items": [Version] }`, newest first |
| `POST /api/files/{id}/versions` | multipart, field `file` | `201` File |
| `POST /api/files/{id}/versions/{n}/restore` | — | `201` File (new version = current + 1) |
| `PUT /api/files/{id}/permissions` | `{ "user_id": 3, "can_read": true, "can_update": false }` | `200` |
| `DELETE /api/files/{id}` | — | `204` |

## Backend interfaces (A ↔ B)

Python interfaces inside the API, agreed on day 1 of the presentation 2 block. They aren't HTTP, so C can skip this section.

### LogBook service — `app/logbook/` (B)

```python
class Action(StrEnum):
    LOGIN = "LOGIN"
    LOGIN_FAILED = "LOGIN_FAILED"
    ...  # every action in the LogEntry table


async def log_event(
    session: AsyncSession,
    request: Request,
    action: Action,
    user: User,
    *,
    file_id: uuid.UUID | None = None,
    version_no: int | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Add a success=true entry to ``session``; the caller's commit writes it."""


async def log_failure(
    request: Request,
    action: Action,
    error: str,
    *,
    user: User | None = None,
    username: str | None = None,
    file_id: uuid.UUID | None = None,
    version_no: int | None = None,
) -> None:
    """Write a success=false entry with details={"error": error} in its own
    session and commit it at once. Never raises."""


def logged(action: Action) -> params.Depends:
    """Route dependency that records the route's action in ``request.state``,
    so the error handlers know which failure to write."""


def logged_action(request: Request) -> Action | None:
    """The action ``logged`` recorded for this request, or None. The error
    handlers read it here instead of from request.state directly."""
```

- **Successes go into the caller's transaction**, next to the change they record: `UPLOAD` with the `files` + `file_versions` insert, `LOGIN` with the new refresh token, `USER_DEACTIVATE` with the update. If that transaction rolls back, the entry goes with it, so the LogBook never says "uploaded" for an upload that didn't happen. If the LogBook insert fails, the operation fails too: nothing happens without its entry.
- **Failures get their own session** (`request.app.state.sessionmaker`), because the caller's transaction is usually being rolled back at that moment and would take the entry with it. If the database is down, `log_failure` writes to the server log instead of raising, so it never hides the original error.
- IP from `request.client.host`, user agent from the `User-Agent` header. `username` (from `user`, or the typed one for `LOGIN_FAILED`) is cut to 50 characters, the user agent to 512.
- **Who writes what:** every logged route declares `dependencies=[logged(Action.X)]` and calls `log_event()` on success. Failures are written in one place: every error handler in `app/errors.py` (A) calls `log_failure()` when the route has an action and the user is known (`request.state.user`). So no endpoint can forget its failure entry. Login is the exception: it writes `LOGIN` / `LOGIN_FAILED` itself, because no user is known yet and it needs the typed username.

### Auth dependencies — `app/auth/` (A)

```python
class Right(StrEnum):
    READ = "READ"
    WRITE = "WRITE"
    UPDATE = "UPDATE"


@dataclass(frozen=True)
class FileAccess:
    user: User
    file: File
    permissions: Permissions  # the same object the File JSON returns


async def current_user(request: Request) -> User: ...
def require(right: Right) -> params.Depends: ...  # Right.READ or Right.UPDATE
async def require_write(user: CurrentUser) -> User: ...
async def require_admin(user: CurrentUser) -> User: ...
```

| Dependency | Use on | Returns | Refuses with |
|---|---|---|---|
| `current_user` | Every route except login, refresh and health (already on the files router) | `User`, detached and read-only; also stored in `request.state.user` | `401` `NOT_AUTHENTICATED`: no token. `401` `TOKEN_EXPIRED`: token invalid or expired, or the user is deactivated |
| `require(Right.READ)`, `require(Right.UPDATE)` | Routes with a `{file_id}` path parameter (the name matters) | `FileAccess`, so the route doesn't load the file again | `404` `NOT_FOUND`: missing, deleted or not readable. `403` `FORBIDDEN`: readable, but the right is missing |
| `require_write` | `POST /api/files` | `User` | `403` `FORBIDDEN` for a `viewer` |
| `require_admin` | `/api/users…`, `/api/logbook…` | `User` | `403` `FORBIDDEN` |

- The rules live in one pure function in `app/auth/rights.py` that works out a user's `Permissions` on a file. `require()` and the `permissions` in the File JSON both use it, so the UI and the server can't disagree.
- `current_user` and `require()` use their own short session, as `current_user` does today, so no database connection stays open while a file streams.
- **Until A's login pull request lands**, stubs with the final names and signatures are on `main`: `current_user` returns the admin, `require()` returns the file (404 if missing or deleted) with every permission `true`, and `require_write` / `require_admin` return the admin. Build against these now.

Example, B's new-version route:

```python
@router.post("/{file_id}/versions", status_code=201, dependencies=[logged(Action.UPDATE)])
async def new_version(
    request: Request,
    access: Annotated[FileAccess, Depends(require(Right.UPDATE))],
    session: DbSession,
) -> FileOut:
    ...  # stream the blob first, outside any transaction
    async with session.begin():
        ...  # SELECT … FOR UPDATE, insert file_versions, bump files.current_version
        await log_event(session, request, Action.UPDATE, access.user,
                        file_id=access.file.id, version_no=new_no)
```

### Migration order

```
59eb015ba1ea  users, files, file_versions       on main
  └─ A        refresh_tokens, file_permissions  A's first PR, merged by Fri 27 Nov
       └─ B   logbook                           down_revision = A's revision ID
```

- A's first pull request holds only the two tables, their migration, the dependency stubs above and a test that Alembic has exactly one head. Login and tokens follow in a second pull request, so B doesn't wait for them.
- B sets `down_revision` to the revision ID from A's pull request and merges `main` before opening the LogBook pull request.
- Why the test: the tests build the schema from `Base.metadata`, not from the migrations. Without it, two heads would pass CI and only break when the API container runs `alembic upgrade head` at startup.
- For every later migration: merge `main` first; `alembic heads` must print one line.

**`logbook` table (B):** no foreign keys, because it records attempts on files and users that may not exist and must never fail because of them. Columns as in [PLAN §6](PLAN.md#6-data-model): `ts timestamptz` default `now()`, `username varchar(50)`, `action varchar(20)`, `ip varchar(45)`, `user_agent varchar(512)`, `details jsonb`. Indexes on `ts`, `(username, action, ts)` and `(ip, action, ts)`; the last two serve the login rate limit.

**Revoking a user's refresh tokens (B's deactivate):** `UPDATE refresh_tokens SET revoked_at = now() WHERE user_id = :id AND revoked_at IS NULL`, in the same transaction as `is_active = false`.
