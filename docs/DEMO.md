# Live Demo & Verification Script — Role D

> Owner: **Role D (DevOps & Azure)**
> Reference: [PLAN.md §9 & §13](PLAN.md) · [PRESENTATION.md (Slide 5)](PRESENTATION.md#slide-5--outcome) · [API.md](API.md)

This document contains the step-by-step script for the **1-minute live demo** during the first presentation (Slide 5), the instructions for recording the **backup video**, and the automated **smoke test** procedure.

---

## 1. Pre-Presentation Preparation (15 minutes before start)

1. Copy the environment configuration if not already present:
   ```bash
   cp -n .env.example .env
   ```
2. Start all services in Docker Compose and verify they are healthy:
   ```bash
   docker compose up -d --build
   docker compose ps
   ```
3. Run the automated smoke test **twice in a row** to confirm everything works end-to-end:
   ```bash
   ./scripts/smoke_test.sh
   ./scripts/smoke_test.sh
   ```
4. Open two browser tabs ready for screen sharing:
   - **Tab 1:** `https://localhost` (Web App UI)
   - **Tab 2:** `https://localhost/api/docs` (FastAPI Swagger UI — fallback if frontend is unavailable)
5. Keep a sample file ready on the Desktop (e.g. `sample-photo.jpg` or `project-notes.pdf`, ~1–2 MB).
6. Keep the **backup screen recording** (`demo-backup.mp4` / `.mov`) open in QuickTime Player in the background, paused at `0:00`. If anything fails during the live presentation, switch to the video immediately.

---

## 2. Live Demo Script (~60 seconds — Slide 5)

| Time | Action on Screen | What to Say (EN) | Cosa dire / Spiegazione (IT) |
| :--- | :--- | :--- | :--- |
| **0:00 – 0:15** | Show terminal or browser typing `http://localhost` → automatically redirects to `https://localhost` with TLS lock icon. | *"All traffic goes through our Caddy reverse proxy over HTTPS. Plain HTTP requests are automatically redirected to HTTPS."* | Mostrare che digitando `http://localhost` il proxy Caddy reindirizza automaticamente a `https://localhost` cifrato. |
| **0:15 – 0:35** | Click **Upload**, select `sample-photo.jpg` from Desktop, and submit. | *"We upload a file from the browser. The API streams it in 4 MiB chunks directly to Azurite Blob Storage and stores its metadata and SHA-256 hash in PostgreSQL."* | Selezionare un file e caricarlo. L'API lo invia in streaming su Azurite e salva i metadati su PostgreSQL. |
| **0:35 – 0:45** | Point to the updated file list showing the file name, size (`size_bytes`), and version `v1`. | *"The file immediately appears in the list with version 1, its size, and timestamp."* | Il file appare subito nella lista con versione 1, dimensione e data. |
| **0:45 – 1:00** | Click **Download** on the file row and open the downloaded file (or show Azure Storage Explorer connected to Azurite on port `10000`). | *"Downloading streams the blob back through the API with identical bytes. Moving this stack to Azure requires only changing the environment configuration."* | Cliccare su Download per scaricare il file integro passando dall'API. |

---

## 3. Automated Smoke Test (`scripts/smoke_test.sh`)

We use the same scripted smoke test locally (against `https://localhost`) and in the cloud (against Azure):

```bash
# Run against local Docker Compose (default: https://localhost)
./scripts/smoke_test.sh

# Run against Azure deployment (Phase 4 & Phase 6)
BASE_URL="https://<your-azure-static-web-app-or-container-app>" ./scripts/smoke_test.sh
```

What the script checks automatically:
1. **HTTPS Redirect (M2):** `http://localhost` returns `308 Permanent Redirect` to `https://localhost/`.
2. **Upload (`POST /api/files`):** Creates a temporary test file, computes its local SHA-256 hash, and uploads it via `multipart/form-data`.
3. **List (`GET /api/files`):** Verifies the newly created file `id` is present in `items`.
4. **Download (`GET /api/files/{id}/download`):** Downloads the file and verifies that its SHA-256 hash matches the original file byte-for-byte.

---

## 4. How to Record the Backup Video on macOS (By P−2)

1. Start the environment (`docker compose up -d`).
2. Press **`Cmd + Shift + 5`** on your Mac to open the native screen recorder.
3. Choose **Record Selected Portion** (or Entire Screen) and record the 45–60 second flow in Section 2 (`http://localhost` redirect → Upload → List → Download).
4. Save the video as `demo-backup.mp4` (or `.mov`) in a shared team folder (Google Drive / OneDrive / Teams) so every team member has access to it during the presentation.
