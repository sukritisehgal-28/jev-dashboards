# Jev Dashboards app

Upload a CSV or JSON file, connect a Google Sheet, or load the sample. Jev decides what every
column means; the backend parses, filters and aggregates in code; the frontend draws the dashboard.

| Part | Stack | Where |
| --- | --- | --- |
| Backend | FastAPI, pandas, httpx | `app/backend/jevdash/` |
| Frontend | Next.js 15, React 19, Tailwind 4, Recharts | `app/web/` |

## Run

```bash
# backend (first time)
cd app/backend && python3 -m venv .venv && .venv/bin/pip install -e ../../eval -e ".[dev]"
.venv/bin/uvicorn jevdash.api:app --port 8000          # real Jev; key read from eval/.env
JEV_MOCK=1 .venv/bin/uvicorn jevdash.api:app --port 8000  # free: rules tier answers instead

# frontend (first time: npm install)
cd app/web && npm run dev                               # http://localhost:3000, proxies /api to :8000
```

In the Claude desktop app, `.claude/launch.json` has `backend`, `backend-mock` and `web` configs.

## How Jev is used

| Call | Questions | Why |
| --- | --- | --- |
| One per column | type (Choice), role (Choice), cents (Noul), filter (Noul) | A column alone is enough to type it |
| One per table | is each money column in cents? (Noul each) | Units need context: `amount` scored 0.46 alone, 0.94 with the table |

- Answers between 0.2 and 0.8 on units show a "Jev is unsure" banner; the user's Yes/No is stored and wins.
- Boolean columns with filter probability ≥ 0.8 (e.g. `paid`) restrict revenue totals.
- Decisions are stored per dataset. A live Google Sheet re-reads every 30 s and only asks Jev
  about new columns, so refreshing costs nothing.

## Credit safety

- Every real call is recorded in `app/backend/storage/ledger.json`.
- Calls are refused once the cap is reached: `JEV_BUDGET_USD`, default $1.00.
- Loading the sample costs about $0.0007 (16 calls).

## API

| Method | Path | Does |
| --- | --- | --- |
| POST | `/api/datasets/upload` | multipart file (CSV/JSON) → dashboard |
| POST | `/api/datasets/sheets` | `{url}` → dashboard (live) |
| POST | `/api/datasets/sample` | sample payments → dashboard |
| GET | `/api/datasets/{id}?refresh=true` | dashboard; refresh re-reads a sheet |
| POST | `/api/datasets/{id}/confirm` | `{column, cents}` answers an unsure units question |
| DELETE | `/api/datasets/{id}` | remove |
| GET | `/api/datasets`, `/api/budget`, `/api/health` | list, spend, mode |

## Not yet

- Neon connector (the file store in `store.py` is the seam).
- Claude: the "ask the dashboard" agent and generated layouts (needs an Anthropic key).
- The "ask twice" rule for misleading headers (eval: 95% → 78% accuracy when headers lie).
