# Maintain-AI

A quiet background agent that predicts home appliance maintenance and tells you whether to repair or replace, before something breaks.

Built for the **Agents for Humans Hackathon** (AWS, hosted on Devpost) — Everyday Agents track.

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
5. Notifies the user only when a decision is actually needed

**Why it fits the track:** This is background, judgment-heavy busywork — the kind of task people let slide because checking manually is tedious. The agent removes the tracking burden and adds a decision layer (cost tradeoff) that a plain reminder app doesn't provide.

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
| Notifications | Console log (Stage A) → SMTP/Resend (deployed) | Sends reminder + cost-recommendation alerts to the user |
| Compute/hosting | Railway | Hosts the FastAPI service (agent runtime + manual add/update API) and the daily cron trigger |
| Observability | Strands built-in tracing | Shows agent decision path in the demo video |
| Live judging UI | Next.js on Vercel + WebSocket (FastAPI) | Streams tool-execution events live for judges (stretch, demo polish) |

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full interface contracts and the AWS-native reference option.

---

## Repo layout

```
backend/    Strands agents, tools, Storage/Model interfaces (Python)
frontend/   Live tool-trace judging UI — Next.js on Vercel (not yet scaffolded)
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

---

## Submission requirements checklist

- [ ] Text description (problem, audience, how it works)
- [ ] Public code repo (MIT or Apache license, README, setup instructions)
- [ ] Architecture diagram
- [ ] Demo video (max 5 min): problem, who it's for, why it matters
- [ ] AWS Builder ID
- [ ] Optional live demo link
- [ ] (Bonus) Build story published on builder.aws.com, titled with "Agents for Humans"
