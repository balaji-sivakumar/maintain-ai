# Deploying Maintain-AI (Railway + Neon + Chroma)

Status: Neon is set up and tested live. Chroma Cloud and Railway need your
account/login to finish — everything on the repo side is ready.

---

## 1. Neon — done

`DATABASE_URL` is already in `backend/.env` (gitignored) and verified against
the live database — `NeonPostgresStorage` auto-creates its tables and seeds
the 20-appliance reference table on first connect. Nothing further needed
here unless you want to reset/rotate the password from the Neon dashboard.

## 2. Chroma Cloud — needs your account

`ChromaVectorStore` now uses Chroma Cloud when `CHROMA_API_KEY` is set,
falling back to a local `PersistentClient` (writes to `data/chroma/`) only
when it isn't — so local dev/tests still work with no Chroma Cloud account,
but the deployed services need one.

1. Sign up at trychroma.com
2. Create a database (a default tenant/database is created for you)
3. From the dashboard, get:
   - **API key**
   - **Tenant** (UUID or slug shown in the dashboard)
   - **Database** name
4. Put these in `backend/.env` for local testing against Chroma Cloud:
   ```
   CHROMA_API_KEY=...
   CHROMA_TENANT=...
   CHROMA_DATABASE=...
   ```
5. Once set, run `python scripts/ingest_manuals.py` once (locally or from
   Railway) to populate the cloud collection — after that it persists
   independently of Railway's filesystem, so no Volume is needed.

## 3. Railway — needs your account

1. Sign up at railway.app, connect GitHub
2. **New Project → Deploy from GitHub repo** → `balaji-sivakumar/maintain-ai`
3. This repo is a monorepo (backend/frontend), so for **every** service you
   create from it: Settings → **Root Directory** → `backend`
4. Create **two services** from the same repo:

   **Web service** (handles add/update + manual checks)
   - Root Directory: `backend`
   - Settings → Config-as-code Path: `railway.toml` (already in the repo —
     sets the start command to `uvicorn api:app --host 0.0.0.0 --port $PORT`
     and a `/health` healthcheck)

   **Cron service** (daily maintenance check)
   - Root Directory: `backend`
   - Settings → Config-as-code Path: `railway.cron.toml` (sets the start
     command to `python scripts/cron_check.py` and `cronSchedule = "0 13 * * *"`
     — 1pm UTC daily; edit the cron expression there if you want a different
     time)

   Two separate config files because Railway's config-as-code always
   overrides dashboard-set Start Commands — pointing each service at its own
   file is the supported way to run two different commands from one repo.

5. Environment variables — set these on **both** services:

   | Variable | Value |
   |---|---|
   | `MODEL_PROVIDER` | `openai` |
   | `OPENAI_API_KEY` | your key |
   | `DATABASE_URL` | the Neon connection string from `backend/.env` |
   | `CHROMA_API_KEY` | from trychroma.com dashboard |
   | `CHROMA_TENANT` | from trychroma.com dashboard |
   | `CHROMA_DATABASE` | from trychroma.com dashboard |

   No Volume needed now that Chroma Cloud is doing the persisting.

6. Deploy. Check the web service's `/health` endpoint once it's up.

## Not yet wired

- **Notifications (SMTP/Resend):** `/check` and the cron job currently just
  produce the agent's text response — there's no email/SMS delivery yet.
  Say the word if you want this wired before the demo; it needs its own
  credential (Resend API key, or SMTP host/user/pass).
- Real manufacturer manuals — `data/manuals/*.txt` are mock excerpts I wrote,
  not curated PDFs. Fine for proving the pipeline; swap them before the
  actual demo if you have real ones.
