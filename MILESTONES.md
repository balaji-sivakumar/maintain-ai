# Maintain-AI — Milestones

Build window: **Sep 9 – Sep 14, 2026, 5:00pm PDT** (Agents for Humans Hackathon deadline)

**Stack decision: Option B (Railway + Neon + Chroma) is committed** — AWS credits aren't available for this build, so the AWS-native path (Option A in [ARCHITECTURE.md](ARCHITECTURE.md)) is kept only as a documented reference and isn't being pursued. This was resolved ahead of the original Day 4 checkpoint. The AWS Builder ID account is still needed since it's a fixed submission-form requirement, independent of whether AWS services are used.

Build is still split into two stages: **Stage A** is local development against `LocalJsonStorage` + OpenAI, zero external services created. **Stage B** swaps those local pieces for their Railway/Neon/Chroma equivalents — same code, different config — per the interface table in ARCHITECTURE.md.

---

## Stage A — Local build (Day 1–3)

### Day 1 — Sep 9

- [x] Finalize use case: home maintenance predictor with cost estimator sub-agent
- [x] Finalize architecture (agent design + deployment options)
- [x] Scaffold Strands project locally (`backend/pyproject.toml`, `backend/src`, `Storage`/`Model` interfaces, `LocalJsonStorage` impl, smoke tests passing)
- [x] Define structured JSON table — 20 common appliances with service intervals and repair/replacement cost ranges (`backend/data/appliances.json`)
- [x] Separate repo into `backend/` and `frontend/`
- [ ] *(parallel, non-blocking)* Set up AWS account / AWS Builder ID — still required for the submission form
- [x] ~~Request $50 AWS credits~~ — not pursued, AWS credits are out of the picture

### Day 2 — Sep 10

- [x] Build `add_appliance`, `check_due_maintenance`, `log_completed_service`, `lookup_maintenance_interval`, `draft_service_reminder` tools against `LocalJsonStorage` (`backend/src/tools/appliance_tools.py`)
- [x] Wire orchestrator agent against structured table only, no RAG yet (`backend/src/agents/orchestrator.py`), model calls via `OpenAIModel`
- [x] Test end-to-end locally with mock appliance data — deterministic tool-level tests in `backend/tests/test_appliance_tools.py` (due-date math, no LLM required)
- [x] Verify "silent when nothing due, speaks up when due" behavior — covered by the same tests; `backend/scripts/demo_day2.py` runs the real orchestrator end-to-end against OpenAI for a live check (needs `OPENAI_API_KEY` in `backend/.env`, not run automatically)

### Day 3 — Sep 11

- [x] Build Cost Estimator sub-agent (`backend/src/agents/cost_estimator.py`)
- [x] Add `estimate_repair_cost`, `estimate_replacement_cost`, `recommend_repair_or_replace` (structured data only, deterministic "50% rule" + end-of-life heuristic — `backend/src/tools/cost_tools.py`)
- [x] Wire Agent-as-Tool call from orchestrator to Cost Estimator (`estimate_cost` tool in `appliance_tools.py`)
- [x] Test the full loop: overdue appliance → cost estimate → repair/replace recommendation — deterministic heuristic tests in `backend/tests/test_cost_tools.py`; `backend/scripts/demo_day3.py` exercises the real two-agent loop against OpenAI
- [ ] *(stretch, demo polish — only once the loop above works)* Expose Strands' native tool-execution event stream over a FastAPI WebSocket endpoint

---

## Stage B — Railway + Neon + Chroma integration & deployment (Day 4–6)

### Day 4 — Sep 12

- [x] Curate a handful of appliance manuals for appliance types not in the structured table (`backend/data/manuals/{ev_charger,wine_cooler,pool_pump}.txt` — mock excerpts standing in for real curated PDFs; swap in real manufacturer manuals before the actual demo if time allows)
- [x] Set up Chroma, self-hosted via `chromadb`'s local `PersistentClient` (`backend/src/impl/chroma_vector_store.py`, `backend/scripts/ingest_manuals.py`)
- [x] Wire a `retrieve()` RAG fallback, shared by `lookup_maintenance_interval`, `check_due_maintenance`, and `draft_service_reminder` via an internal `_lookup_reference` helper (`backend/src/tools/appliance_tools.py`) — retrieves from Chroma, extracts structured fields via a Strands `structured_output_model` call (`backend/src/rag.py`)
- [x] Add cache-back to `Storage` on a successful RAG lookup — same `cache_reference_data` used by the structured table, so a RAG hit is indistinguishable from a seeded entry on the next lookup (including for `estimate_cost`'s Cost Estimator tools, which read the same cache)
- [x] **Risk checkpoint resolved:** local Chroma ingestion is fast (no AWS-style sync wait), so this didn't become a time sink; the mock-manual curation shortcut above is the fallback if real manuals aren't sourced in time
- [x] Tests: `backend/tests/test_rag_fallback.py` covers the fallback wiring deterministically via a `FakeVectorStore` + stub extractor (no live Chroma/OpenAI calls); `backend/scripts/demo_day4.py` exercises the real pipeline end-to-end

### Day 5 — Sep 13

- [x] Provision a Neon Postgres database and add a `NeonPostgresStorage` implementation of the `Storage` interface (`backend/src/impl/neon_postgres_storage.py`) — live-tested against the real database (schema creation, seed-on-empty, JSONB round-trip, full FastAPI request cycle)
- [x] Wrap the agent runtime + manual add/update API in a FastAPI service (`backend/src/api.py`: `/health`, `/appliances`, `/appliances/{id}/service`, `/check`) — live-tested end-to-end with `TestClient` against real Neon + OpenAI
- [x] `backend/scripts/cron_check.py` — the daily-check entrypoint that runs and exits (Railway cron's requirement), sharing storage/vector-store construction with the API via `backend/src/runtime.py`
- [x] `backend/railway.toml` (web service) and `backend/railway.cron.toml` (cron service, separate config-as-code path since Railway's code config overrides dashboard Start Commands) — see `backend/DEPLOY.md` for the full setup walkthrough
- [x] Switched `ChromaVectorStore` to Chroma Cloud (`CHROMA_API_KEY`/`CHROMA_TENANT`/`CHROMA_DATABASE`), falling back to the Day 4 local `PersistentClient` only when those aren't set — so it persists independently of Railway's ephemeral filesystem with no Volume needed
- [ ] *(needs your accounts)* Sign up for Chroma Cloud and create the Railway project + two services per `backend/DEPLOY.md`, set env vars, deploy
- [ ] Wire notifications via SMTP/Resend (swap out the plain-text `/check` response used so far) — needs its own credential, not yet requested
- [ ] Write README, add MIT/Apache license, confirm setup instructions run clean
- [ ] Finalize architecture diagram for submission
- [ ] *(stretch, demo polish)* Build the live tool-trace frontend (Next.js), deploy to Vercel, point it at the Railway WebSocket endpoint
- [ ] Record demo video (problem, audience, why it matters, live walkthrough — feature the live trace UI if it's ready)

**Packaging bug caught and fixed along the way:** the flat `src/` layout's standalone modules (`dates.py`, `model.py`, `rag.py`, `runtime.py`, `api.py`) were silently excluded from the actual built wheel — `pip install -e .` (editable) masked this since it works differently, so it only surfaced when testing a real `pip install .` in a fresh venv, which is what Railway's build does. Fixed via `force-include` in `pyproject.toml`. Also fixed: `DEFAULT_REFERENCE_PATH`/`DEFAULT_STATE_PATH`/`DEFAULT_PERSIST_PATH` were computed from `__file__`, which resolves inside `site-packages` for an installed wheel instead of the actual `backend/data/` — switched to `Path.cwd()`-relative, verified by simulating a Railway-style install + working directory.

### Day 6 — Sep 14 (deadline 5:00pm PDT)

- [ ] Final end-to-end testing against the deployed Railway stack
- [ ] Set up live demo link, if time permits
- [ ] Submit on Devpost: text description, repo link, architecture diagram, demo video, AWS Builder ID
- [ ] *(Bonus)* Publish build story on builder.aws.com with "Agents for Humans" in the title

---

## Notes

- A fully working structured-table core loop is a safer fallback than a broken RAG integration if time runs short.
- Because `Storage`/`VectorStore`/`Notifier`/`Trigger`/`EventStream` sit behind interfaces from Day 1, Stage B is mostly wiring new implementations, not rewriting agent/tool logic.
- Chroma has no equivalent risk to the old Bedrock Knowledge Base sync time — ingestion is local/fast — but manual curation (finding/prepping the source PDFs) is still a real time cost, hence the Day 4 risk checkpoint.
- The live tool-trace frontend (Vercel + WebSocket) is presentation polish, not a submission requirement — it's explicitly sequenced after the core agent loop works (Day 3) so it never displaces functional build time.
- Per the hackathon rules, only the Strands Agents SDK is a hard requirement; AWS usage (including AWS Builder ID beyond the submission form) is optional and only affects the Technical Implementation score, not eligibility.
