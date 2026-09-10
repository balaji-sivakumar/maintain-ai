# Maintain-AI — Dashboard

Live view of the orchestrator's tool trace, tracked appliance data, and a
scenario simulator. Talks directly to the deployed Railway backend — no
server-side code of its own beyond static hosting.

## What it does

- **Tracked appliances** — lists what's in the backend's Storage, with
  quick actions to mark serviced or delete.
- **Simulator** — add an appliance with a pick-a-date-range shortcut
  (recent / 2yr overdue / 12yr near end-of-life) to set up demo scenarios,
  including appliance types that only exist via the Day 4 RAG fallback
  (`ev_charger`, `wine_cooler`, `pool_pump` — not in `appliances.json`).
- **Seed demo data / Reset** — one click to load 4 pre-built scenarios
  (overdue repair, near-end-of-life replace, RAG-only appliance, and one
  already serviced so it stays quiet) or clear everything.
- **Live tool trace** — opens the backend's `/ws/check` WebSocket and
  streams the orchestrator's tool calls (`check_due_maintenance`,
  `draft_service_reminder`, `estimate_cost`, ...) as they execute, each
  with its input/output, followed by the final synthesized response.

## Local development

```bash
npm install
cp .env.example .env.local   # points at the deployed Railway backend by default
npm run dev
```

## Configuration

| Variable | Purpose |
|---|---|
| `NEXT_PUBLIC_API_BASE` | Base URL of the backend (Railway `web` service). The `/ws/check` WebSocket URL is derived from this (`http`→`ws`). |

## Deploying

Deployed on Vercel. `NEXT_PUBLIC_API_BASE` must be set as a Vercel project
environment variable (Production + Preview) — see the root `MILESTONES.md`
and `backend/DEPLOY.md` for the backend side.

Note: the backend has no auth and permissive CORS (`allow_origins=["*"]`) —
fine for a hackathon demo, not something to reuse as-is beyond that.
