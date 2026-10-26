# Role C — Frontend

> Member: _TBD_
> Plan: [PLAN.md](../PLAN.md) · Presentation: [PRESENTATION.md](../PRESENTATION.md) · Other roles: [A](A-backend-security.md) · [B](B-storage-versioning.md) · [D](D-devops-azure.md)

You own the web app that users see on computer, tablet and phone, the slide deck, and the screenshots for the user guide.

## Sprint to the first presentation

Days are counted back from the presentation day (P).

| When | Task | Done when |
|---|---|---|
| Day 1 | Agree the JSON shapes of the file endpoints with **A** ([PLAN §7](../PLAN.md#7-rest-api)) | Example responses in an issue |
| Day 1 | Start the shared slide deck from [PRESENTATION.md](../PRESENTATION.md): one template, each speaker fills their own slides | Deck shared with the team |
| By P−5 | `web/`: Vite + React + TypeScript scaffold and `web/Dockerfile`; page with file list, upload button and download links, built against a fake API | Page works with mocked data |
| By P−3 | Connect the page to the real API through `https://localhost` | Upload → list → download works in the browser |
| By P−3 | Responsive layout | Usable at phone width (375 px) in browser dev tools |
| By P−3 | Re-check the vendor figures on slides 7–8 (Dropbox, OneDrive, Nextcloud, Google Drive) | Figures and check date updated in PRESENTATION.md |
| By P−2 | Screenshots of the working page for slide 5 and the user guide | Saved in `docs/report/screenshots/` |
| P−1 | Timed run-through with the team | — |

## Presentation

| Slides | Topic | Time |
|---|---|---|
| 6 | Research | 1:00 |
| 7 | Related work | 1:30 |
| 8 | Detailed comparison of the three most similar solutions | 2:00 |

Total 4:30, the longest part. You take over from **D** after the demo and hand over to **A** for slide 9. If the run-through goes over time, cut slides 7–8 first.

In Q&A, take questions on: competing products, why we chose these three, the user interface, device support.

## After the presentation

| Phase | Your part |
|---|---|
| 2 — Auth & authorization | Login page, logout button, token handling (refresh cookie + access token), hide actions the user has no right to, share dialog |
| 3 — LogBook | Admin LogBook page with filters and CSV / JSON export buttons |
| 5 — Version control | Version history panel (version, date, size, uploader) with Download and Restore |
| 6 — Hardening | Device testing on computer, tablet and smartphone for all six functions; `npm audit` |
| 7 — Report | User guide with screenshots (collect them after every feature); final presentation deck |

## Works with

- **A:** API contract, login and token flow.
- **B:** version history and LogBook endpoints.
- **D:** web container, Caddy routing, Static Web Apps deployment.
- Review **D**'s pull requests.
