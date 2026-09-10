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

Project `maintain-ai`, two services, **not** GitHub-connected (see below for
why) — deployed via CLI upload from the repo root:

| Service | Dockerfile | Purpose |
|---|---|---|
| `web` | `Dockerfile` (CMD: `uvicorn api:app --host 0.0.0.0 --port $PORT`) | `/health`, `/appliances`, `/appliances/{id}/service`, `/check`, `/ws/check`, `/demo/seed`, `/demo/reset` |
| `cron` | `Dockerfile.cron` (CMD: `python scripts/cron_check.py`) | Runs once daily at 13:00 UTC, exits |

Env vars (`MODEL_PROVIDER`, `OPENAI_API_KEY`, `DATABASE_URL`, `CHROMA_API_KEY`,
`CHROMA_TENANT`, `CHROMA_DATABASE`, `RESEND_API_KEY`, `NOTIFY_EMAIL`) are set
on both services.

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
`backend/railway.toml` / `backend/railway.cron.toml` are now just
**reference documentation** of intent, not what's actually driving either
service.

I also tried connecting both services to the GitHub repo (`source.repo` +
`rootDirectory: "/backend"`, both settable via the same API) to get
auto-deploy on push. That didn't work — no webhook ever fired on a real
push, and worse, it **broke CLI deploys**: with `rootDirectory` persisted to
`/backend` and `railway up backend --path-as-root` *also* scoping the upload
to `backend/`, Railway ended up looking for `backend/backend/Dockerfile`
inside the archive and failed silently at the "scheduling build" stage with
no useful log output. Fixed by disconnecting the source
(`railway service source disconnect`) and clearing `rootDirectory` back to
`""` (not `null` — that's a no-op for this field) on both services. **Don't
reconnect a GitHub source to either service** unless you're prepared to
also stop using `--path-as-root` for CLI deploys, or re-verify this doesn't
regress.

### Redeploying after a code change

```bash
cd /path/to/maintain-ai   # repo root — railway up resolves the linked
                          # project from wherever `railway init` was run,
                          # not necessarily your shell's cwd
railway up backend --path-as-root --service web
railway up backend --path-as-root --service cron
```

## For the frontend

Base URL: `https://web-production-91b0a.up.railway.app`
WebSocket: `wss://web-production-91b0a.up.railway.app/ws/check`

CORS is wide open (`allow_origins=["*"]`) since there's no auth on this API
at all — anyone with the URL can add/delete appliances or trigger a check.
Fine for a hackathon demo; not something to reuse as-is beyond that.

## Notifications — done

`Notifier` interface (`interfaces/notifier.py`) with `ConsoleNotifier` (local
dev, no credential) and `ResendNotifier` (`impl/resend_notifier.py`,
`RESEND_API_KEY`/`NOTIFY_EMAIL`, both in `backend/.env` and set on both
Railway services). Uses Resend's sandbox sender (`onboarding@resend.dev`),
which can only deliver to the Resend account's own signup email — fine for
a single-household demo, would need a verified custom domain for real
multi-recipient use.

The orchestrator gets a `send_notification` tool and calls it once, only
when `check_due_maintenance` actually found something due — verified live
via the `/ws/check` trace (`send_notification` fires and returns `success`
when something's due; never called on a silent check).

## Not yet wired

- Real manufacturer manuals — `data/manuals/*.txt` are mock excerpts I wrote,
  not curated PDFs. Fine for proving the pipeline; swap them before the
  actual demo if you have real ones.
