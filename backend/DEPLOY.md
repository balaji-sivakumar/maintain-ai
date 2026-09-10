# Deploying Maintain-AI (Railway + Neon + Chroma)

**Status: fully deployed and live.**

- Web service: https://web-production-91b0a.up.railway.app (`/health` returns `{"status":"ok"}`)
- Cron service: runs `scripts/cron_check.py` daily at 13:00 UTC, confirmed to run-and-exit correctly (not a persistent process)
- Both verified end-to-end against real Neon Postgres, Chroma Cloud, and OpenAI — not just health checks

---

## 1. Neon — done

`DATABASE_URL` is in `backend/.env` (gitignored) and set as an env var on
both Railway services. `NeonPostgresStorage` auto-creates its tables and
seeds the 20-appliance reference table on first connect.

## 2. Chroma Cloud — done

`ChromaVectorStore` uses Chroma Cloud (`CHROMA_API_KEY`/`CHROMA_TENANT`/`CHROMA_DATABASE`,
also in `backend/.env` and set on both Railway services), falling back to a
local `PersistentClient` only when those aren't set (local dev without a
Chroma Cloud account). `scripts/ingest_manuals.py` has already been run
against the real Chroma Cloud instance — the `appliance_manuals` collection
has all 3 manuals.

## 3. Railway — done

Project `maintain-ai`, two services, both connected to
`balaji-sivakumar/maintain-ai` on GitHub with Root Directory `/backend`:

| Service | Dockerfile | Purpose |
|---|---|---|
| `web` | `Dockerfile` (CMD: `uvicorn api:app --host 0.0.0.0 --port $PORT`) | `/health`, `/appliances`, `/appliances/{id}/service`, `/check` |
| `cron` | `Dockerfile.cron` (CMD: `python scripts/cron_check.py`) | Runs once daily at 13:00 UTC, exits |

Env vars (`MODEL_PROVIDER`, `OPENAI_API_KEY`, `DATABASE_URL`, `CHROMA_API_KEY`,
`CHROMA_TENANT`, `CHROMA_DATABASE`) are set on both services.

### How this was actually done (important for future redeploys)

The original plan was two `railway.toml`-style config-as-code files, one per
service, each set as that service's "Config-as-code Path" in the dashboard.
That path turned out to be blocked — Railway now rejects new attempts to set
a per-service config file path (`railwayConfigFile`), since config-as-code
(`railway.json`/`railway.toml`) is being phased out in favor of
`.railway/railway.ts` (which doesn't yet support cron schedules, so it
wasn't usable here either).

What worked instead: **two separate Dockerfiles** (`Dockerfile` for the web
service, `Dockerfile.cron` for the cron service — the only difference is the
`CMD`), with each service's `dockerfilePath`, `cronSchedule`, and
`restartPolicyType` **persisted directly via Railway's GraphQL API**
(`serviceInstanceUpdate`), rather than read from a config file per deploy.
This matters because it means:

- `backend/railway.toml` / `backend/railway.cron.toml` are now just
  **reference documentation** of intent — they're not what's actually
  driving either service's settings. They still work as config-as-code for
  a plain `railway up` (with a deprecation warning), but the services'
  *persisted* settings are what take effect either way.
- **Future redeploys just work** — either `git push` to `main` (both
  services are GitHub-connected) or `railway up backend --path-as-root --service <web|cron>`
  from the repo root will rebuild using the correct Dockerfile per service,
  without needing to repeat any of the swap-file or API steps above.
- If you ever need to change the cron schedule, restart policy, or health
  check path, do it the same way: `railway api` with a `serviceInstanceUpdate`
  mutation (or ask me to) — editing `railway.cron.toml` alone won't do
  anything for these two services anymore.

### Redeploying after a code change

```bash
cd backend
railway up --service web    # or: git push, once GitHub auto-deploy is confirmed working
railway up --service cron
```

(Run from the repo root with `railway up backend --path-as-root --service <name>`
if not already linked/cd'd appropriately — see `railway status` to check the
current link.)

## Not yet wired

- **Notifications (SMTP/Resend):** `/check` and the cron job currently just
  produce the agent's text response — there's no email/SMS delivery yet.
  Say the word if you want this wired; it needs its own credential (Resend
  API key, or SMTP host/user/pass).
- Real manufacturer manuals — `data/manuals/*.txt` are mock excerpts I wrote,
  not curated PDFs. Fine for proving the pipeline; swap them before the
  actual demo if you have real ones.
