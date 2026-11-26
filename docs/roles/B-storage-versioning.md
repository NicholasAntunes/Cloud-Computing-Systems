# Role B — Storage & version control

> Member: _TBD_
> Plan: [PLAN.md](../PLAN.md) · Presentation: [PRESENTATION.md](../PRESENTATION.md) · Other roles: [A](A-backend-security.md) · [C](C-frontend.md) · [D](D-devops-azure.md)

You own everything that touches Blob Storage, and the two "data" features: version control and the LogBook.

## Sprint to the first presentation

Days are counted back from the presentation day (P).

| When | Task | Done when |
|---|---|---|
| Day 1 | Agree the `app/storage` function signatures with **A** | Signatures in a short comment or issue that both of you approve |
| Day 1 | Install Azure Storage Explorer and connect it to Azurite | You can see the `files` container |
| By P−5 | `api/app/storage/` package: create the container, streamed upload, streamed download, list. Build the client from `STORAGE_AUTH` (connection string locally, managed identity on Azure, [PLAN §9](../PLAN.md#9-local-environment)) | Works against Azurite from inside Compose (host `azurite`, not `127.0.0.1`) |
| By P−3 | Wire `app/storage` into A's endpoints. Blob names are `{file_id}/{version_no}`, never the user's file name | Upload through the API shows up in Storage Explorer |
| By P−3 | Small Azurite test that shows blob versioning is **not** supported | Script and its output saved — evidence for slide 6 |
| By P−2 | Test: upload → download returns identical bytes (same SHA-256) | Test passes in D's CI |
| P−1 | Timed run-through with the team | — |

## Presentation

| Slides | Topic | Time |
|---|---|---|
| 1 | Title | 0:30 |
| 2 | Problem statement / idea | 1:30 |
| 3 | Challenge | 1:30 |

Total 3:30. You open the presentation and hand over to **D** for slide 4.

Slide 3 points 2 and 3 (version control, Azurite vs Azure) are your design, so explain why versioning is in our own code. Also help **D** check the storage part of the demo.

In Q&A, take questions on: Blob Storage, Azurite, versioning design, simultaneous uploads.

## After presentation 1

Dates, the day-1 agreements and the full checklist: [PLAN §10](../PLAN.md#10-schedule).

| When | Your part |
|---|---|
| Until presentation 2 (Mon 30 Nov) | Day-1 agreements with **A** (`log_event()` signature, LogBook entry shape, migration order); `logbook` table and `log_event()` service, recording IP, user agent and failures (failure entries committed in their own session); your slides |
| Until Sun 6 Dec — users, rights & LogBook (LogBook lead) | `GET /api/logbook` with filters and pagination; CSV and JSON export, with formula-injection escaping in CSV; admin endpoints to create / list / deactivate users (deactivating revokes the user's refresh tokens); test: N scripted operations → exactly N entries |
| W9–W10 (7–20 Dec) — version control (lead) | `POST /api/files/{id}/versions` with `SELECT … FOR UPDATE` + retry on conflict; SHA-256 while streaming; list versions, download by version, restore (copy to a new version); tests: 3 uploads → versions 1–3, v1 hash matches, parallel uploads get unique numbers |
| W11 (4–10 Jan) | Fix storage and versioning issues found on Azure; check the LogBook after the Azure smoke test; your slides for presentation 3 |
| After presentation 3 (11–25 Jan) | Load check: 100 MB upload, list of 1,000 files; cleanup of orphan blobs; report: storage, version control and LogBook chapters |

## Works with

- **A:** `app/storage` interface; A's permission dependency on your endpoints; A calls your `log_event()`.
- **C:** version history panel, LogBook and user admin pages.
- **D:** Azurite in Compose and CI; managed identity and storage account on Azure.
- Review **A**'s pull requests.
