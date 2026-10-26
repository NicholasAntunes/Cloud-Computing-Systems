# Role D — DevOps & Azure

> Member: _TBD_
> Plan: [PLAN.md](../PLAN.md) · Presentation: [PRESENTATION.md](../PRESENTATION.md) · Other roles: [A](A-backend-security.md) · [B](B-storage-versioning.md) · [C](C-frontend.md)

You own the environment everyone else works in: repository, Docker, HTTPS, CI and Azure. You also run the live demo.

## Sprint to the first presentation

Days are counted back from the presentation day (P). Your Day 1 and P−5 tasks block everyone else, so do them first.

| When | Task | Done when |
|---|---|---|
| Day 1 | Protect `main` (pull requests with one review); GitHub Projects board with the tasks from all four role files | Board shared with the team |
| Day 1 | Fix `.gitignore`: add `!.env.example`, `__pycache__/`, `.venv/`, `.pytest_cache/` ([PLAN §9](../PLAN.md#known-pitfalls)); add `.env.example` | Committed |
| By P−5 | `docker-compose.yml` (Azurite, PostgreSQL, API, web, Caddy) and `Caddyfile` with `tls internal` ([PLAN §9](../PLAN.md#9-local-environment)) | All four members run `docker compose up` and open `https://localhost` |
| By P−3 | GitHub Actions: lint + tests, with PostgreSQL and Azurite as service containers | CI runs on every pull request |
| By P−3 | Azure for Students subscription and a budget alert | Alert e-mail configured |
| By P−3 | Export the slide 4 Mermaid diagram as an image | Image in the deck |
| By P−2 | End-to-end demo: upload → list → download over `https://localhost`; check `http://` is redirected | Demo script written down, works twice in a row |
| By P−2 | Backup screen recording of the demo | Video saved where the whole team can reach it |
| P−1 | Update slide 5 with what actually works; timed run-through with the team | — |

## Presentation

| Slides | Topic | Time |
|---|---|---|
| 4 | Approach (architecture) | 1:30 |
| 5 | Outcome + live demo | 1:00 + ~1:00 demo |
| 13 | Measures of success | 1:00 |
| 14 | Schedule and team | 0:30 |

Total 4:00 plus the demo. You take over from **B** after slide 3, hand over to **C** for slide 6, then come back after **A** for slides 13–14 and close.

Have the demo running **before** the presentation starts. If anything fails, switch to the recording straight away.

In Q&A, take questions on: Docker, HTTPS, CI, Azure services, cost, the migration plan.

## After the presentation

| Phase | Your part |
|---|---|
| 2–3 | Keep Compose and CI working as tables and migrations are added; Alembic migrations run on start-up |
| 4 — Trial Azure deployment (lead) | Deploy the current state with [PLAN §11](../PLAN.md#11-azure-migration-steps); write down every local / cloud difference; scale to zero and stop PostgreSQL afterwards |
| 6 — Final migration (lead) | Repeatable script in `infra/` (Bicep or az CLI); managed identity for Blob access; secrets in Key Vault; Application Insights; same scripted smoke test on Azure as locally |
| 7 — Report | Cloud provider and deployment chapters; delete or scale down Azure resources after grading |
| Ongoing | Watch Azure costs; keep the "who did what" log in `docs/report/` |

## Works with

- **A** and **B:** environment variables, storage auth mode, database.
- **C:** web container and Caddy routing.
- Review **C**'s pull requests, and anyone's that change Docker, CI or `infra/`.
