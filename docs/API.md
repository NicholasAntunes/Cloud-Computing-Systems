# API Contract — Cloud File Exchange System

> The JSON shapes and rules the web client (role C) builds against. Owner: role A.
> Endpoint list and rights: [PLAN.md §7](PLAN.md#7-rest-api). If the code and this file disagree, the code is a bug; change both in the same pull request.

## General rules

| Rule | Value |
|---|---|
| Base path | `/api`, always called **relative** (`fetch('/api/files')`). The web app and the API share one origin behind Caddy, so no CORS and the refresh cookie just works |
| Format | JSON, `snake_case` field names (except uploads and downloads) |
| Dates | ISO 8601 in UTC with `Z`, e.g. `"2026-11-02T14:05:31Z"` |
| IDs | Files: UUID string. Users: integer |
| Sizes | Bytes, as integers (`size_bytes`) |
| Auth (from Phase 2) | `Authorization: Bearer <access_token>` on every request except login and refresh |
| Live spec | Swagger UI at `https://localhost/api/docs` once the API runs |

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

Returned by login, refresh and `GET /api/auth/me`.

```json
{
  "id": 2,
  "username": "alice",
  "email": "alice@example.com",
  "role": "user",
  "capabilities": {
    "upload": true,
    "manage_users": false,
    "view_logbook": false
  }
}
```

- `role` is `viewer`, `user` or `admin`; show it as a label only.
- `capabilities` drives the global UI: `upload` → upload button; `manage_users` / `view_logbook` → admin pages.

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

## Files (Phase 1)

### List — `GET /api/files?limit=100&offset=0`

Returns only files the user may read, newest `updated_at` first. `limit` defaults to 100 (max 1000).

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
| No `file` field / empty file | `400` `VALIDATION_ERROR` |
| Over 100 MB | `413` `FILE_TOO_LARGE` |
| No WRITE right (Phase 2) | `403` `FORBIDDEN` |

`fetch` has no upload progress; use `XMLHttpRequest` (`xhr.upload.onprogress`) if you want a progress bar. Check the size on the client too, so users don't wait to be told 413.

### Download — `GET /api/files/{id}/download[?version=n]`

**Direct stream** from the API, not a temporary URL. Reasons: Azurite doesn't support user-delegation SAS, files must only be reachable through the API (NFR7), and every download must be written to the LogBook.

- Response: the file bytes with `Content-Type` and `Content-Disposition: attachment; filename="holiday.jpg"` (UTF-8 names via `filename*=`).
- Without `version` you get the current version.
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

`200` File. Used to refresh one row after an action.

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
| 403 | `FORBIDDEN` | The user can see the file but lacks this right (e.g. UPDATE) |
| 404 | `NOT_FOUND` | The file doesn't exist **or the user may not read it**. We don't reveal that a file exists |
| 409 | `CONFLICT` | Simultaneous new versions; retry |
| 413 | `FILE_TOO_LARGE` | Over `MAX_UPLOAD_MB` |
| 429 | `RATE_LIMITED` | Too many login attempts |
| 500 | `INTERNAL_ERROR` | Anything unexpected; generic message |

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
| `GET /api/logbook?user=&action=&from=&to=&limit=&offset=` | — | `200 { "items": [...], "total": n }` |
| `GET /api/logbook/export?format=csv\|json` | — | file download (same `fetch` → blob pattern) |
| `POST /api/users` | `{ "username", "email", "password", "role" }` | `201` User |
