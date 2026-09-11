# Maintain-AI

A quiet background agent that predicts home appliance maintenance and tells you whether to repair or replace, before something breaks.

Built for the **Agents for Humans Hackathon** (AWS, hosted on Devpost) — Everyday Agents track.

**Live:** [maintain-ai-dashboard.vercel.app](https://maintain-ai-dashboard.vercel.app) — dashboard with demo data, a scenario simulator, and a live view of the orchestrator's tool calls. Backend API: [web-production-91b0a.up.railway.app](https://web-production-91b0a.up.railway.app).

---

## Overview

Every household has appliances that need periodic servicing — HVAC filters, water heater flushes, smoke detector batteries — but most people only think about maintenance after something breaks. By then, the choice is often reactive and expensive: an emergency repair, a rushed replacement, or living with a failure that could have been prevented.

Maintain-AI runs quietly in the background. It tracks a household's appliances, knows when maintenance is due, and only surfaces when there's a real decision to make. When something is overdue or approaching end-of-life, it goes a step further than a simple reminder: it estimates repair vs. replacement cost and recommends which makes more sense.

---

## Use case

**Track:** Everyday Agents

**Problem:** Homeowners react to appliance failures instead of anticipating them, leading to avoidable emergency costs and preventable breakdowns.

**Solution:** An agent that:
1. Tracks registered appliances (brand, model, install date)
2. Checks maintenance intervals against a structured dataset, falling back to a document-based knowledge base for anything not covered
3. Stays silent when nothing is due
4. When something is due or overdue, delegates to a Cost Estimator sub-agent to recommend repair vs. replace
5. Notifies the user whenever something needs attention, and — separately — lets the household approve or deny each appliance's repair/replace request before it's ever recorded as submitted, not just advisory in name

**Why it fits the track:** This is background, judgment-heavy busywork — the kind of task people let slide because checking manually is tedious. The agent removes the tracking burden and adds a decision layer (cost tradeoff) that a plain reminder app doesn't provide. The human-in-the-loop approval gate (see ARCHITECTURE.md) keeps a background agent from ever submitting a repair/replace request on the household's behalf without a person deciding first — one screen, one decision per appliance.

**Scope note:** "submitting a request" means recording the household's decision (what, and whether to proceed) — not booking a contractor or placing an order. Real fulfillment is appliance-specific (an HVAC repair, a plumber for a water heater, a utility for an EV charger) and intentionally out of scope; see ARCHITECTURE.md's "Scope boundary" for why, and how it follows the same pluggable-interface pattern as the rest of this build.

---

## Architecture

The agent design (Agent-as-Tool pattern, tools, data flow) is firm and stack-independent. **Stack decision: Railway + Neon + Chroma is committed** (AWS credits aren't available for this build; an AWS-native path is kept in ARCHITECTURE.md as a documented reference only). See **[ARCHITECTURE.md](ARCHITECTURE.md)** for the full agent design, data flow, pluggable interfaces, and both deployment diagrams.

---

## Tech stack

| Layer | Component | Purpose |
|---|---|---|
| Agent framework | Strands Agents SDK (Python) | Orchestrator + Cost Estimator agents, Agent-as-Tool pattern (hackathon's hard requirement) |
| Model | OpenAI | Reasoning/tool-use for both agents, via `MODEL_PROVIDER` |
| State store | Local JSON (Stage A) → Neon Postgres (deployed) | Appliance list, install dates, last-serviced dates, cached lookups |
| RAG fallback | Chroma | Vector search over appliance manuals when the structured table has no match |
| Notifications | Console log (Stage A) → Resend (deployed) | Sends reminder + cost-recommendation alerts to the user |
| Compute/hosting | Railway | Hosts the FastAPI service (agent runtime + manual add/update API) and the daily cron trigger |
| Observability | Strands' built-in OTel spans → Honeycomb (OTLP) | Engineering-grade trace: per-tool timing, token usage, latency — distinct from the judging UI's simplified narrative feed |
| Live judging UI | Next.js on Vercel + WebSocket (FastAPI) | Streams tool-execution events live for judges — [deployed](https://maintain-ai-dashboard.vercel.app) |

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full interface contracts and the AWS-native reference option.

---

## Repo layout

```
backend/    Strands agents, tools, Storage/Model interfaces (Python) — deployed to Railway
frontend/   Live tool-trace judging UI — Next.js, deployed to Vercel
```

## Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env   # then fill in OPENAI_API_KEY (or set MODEL_PROVIDER=bedrock)
pytest tests/
```

The structured appliance reference table lives at `backend/data/appliances.json`; tracked household appliances persist locally to `backend/data/local_state.json` (gitignored) via `LocalJsonStorage`.

```bash
cd frontend
npm install
cp .env.example .env.local   # points at the deployed Railway backend by default
npm run dev
```

See `backend/DEPLOY.md` and `frontend/README.md` for the full deployment setup (Railway, Neon, Chroma Cloud, Vercel).

---

## License

MIT — see [LICENSE](LICENSE).

---

## Submission requirements checklist

Per the [hackathon rules](https://agentsforhumans.devpost.com/rules):

- [x] Built with the Strands Agents SDK (the one hard technical requirement)
- [x] Public code repo (GitHub), MIT license visible at the repo root, README, setup instructions
- [x] Architecture diagram — see [ARCHITECTURE.md](ARCHITECTURE.md)
- [x] Project runs consistently and does real end-to-end work (tracks appliances, delegates to a real Cost Estimator sub-agent, sends real email notifications, gates repair/replace request submission behind human approval) — not just chat
- [x] Optional live demo link — https://maintain-ai-dashboard.vercel.app
- [ ] Text description (problem, audience, how it works) — draft ready, needs pasting into the Devpost form
- [ ] Demo video (max 5 min, uploaded to YouTube/Vimeo, public): problem, audience, why it matters, working end-to-end walkthrough
- [ ] AWS account (signin.aws.amazon.com) — separate "How to Enter" step
- [ ] AWS Builder ID — separate submission-form requirement
- [ ] Select track on the Devpost form (Everyday Agents)
- [ ] Submit on Devpost before Sep 14, 2026, 5:00pm PT
- [ ] (Bonus, up to 0.6 pts) Build story published on builder.aws.com, titled with "Agents for Humans"
