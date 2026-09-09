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

### Agent design (Agent-as-Tool pattern)

**Home Maintenance Agent (orchestrator)**
- `add_appliance(name, brand, model, install_date)`
- `check_due_maintenance()`
- `lookup_maintenance_interval(brand, model)` — structured table first, RAG fallback second
- `draft_service_reminder(appliance)`
- `log_completed_service(appliance)`
- `estimate_cost(appliance_issue)` — invokes the Cost Estimator Agent

**Cost Estimator Agent (sub-agent)**
- `estimate_repair_cost(appliance, issue)`
- `estimate_replacement_cost(appliance)`
- `recommend_repair_or_replace(appliance, age, repair_cost, replacement_cost)`

### Deployment architecture (AWS)

```
User (web/CLI)
      |
      v
+-------------------------- AWS cloud --------------------------+
|                                                                 |
|   API Gateway         EventBridge                              |
|   (add/update)        (daily trigger)                          |
|        \                    /                                  |
|         v                  v                                   |
|          Agent runtime (Lambda)                                |
|          Strands agents on Bedrock                              |
|        /            |              \                           |
|       v              v               v                          |
|  DynamoDB        SES / SNS       Knowledge base                |
|  (appliance      (notifications  (OpenSearch vectors)          |
|   state)          out)                ^                         |
|                       |                |                         |
|                       |           S3 bucket                     |
|                       |          (appliance manuals)            |
+-----------------------|--------------------------------------- +
                         v
                  User (email/SMS alert)
```

**Query path:** Lambda checks DynamoDB first (fast path). On a miss, it calls the Bedrock Knowledge Base, which does vector search over ingested manuals and generates a grounded answer. Successful RAG lookups are cached back into DynamoDB so future lookups for the same appliance skip the vector search entirely.

**Ingestion path (separate from the query path):** Appliance manuals are uploaded to S3 and synced into the Knowledge Base — an occasional admin action, not part of the real-time request cycle.

---

## Tech stack

| Layer | Component | Purpose |
|---|---|---|
| Agent framework | Strands Agents SDK (Python) | Orchestrator + Cost Estimator agents, Agent-as-Tool pattern |
| Model | Amazon Bedrock (Claude) | Reasoning/tool-use for both agents |
| Compute | AWS Lambda | Hosts the agent runtime |
| Trigger (automatic) | Amazon EventBridge | Daily schedule to run maintenance checks |
| Trigger (manual) | Amazon API Gateway | Add/update appliance, mark service done |
| State store | DynamoDB | Appliance list, install dates, last-serviced dates, cached lookups |
| RAG fallback | Bedrock Knowledge Base + OpenSearch Serverless | Vector search over appliance manuals when DynamoDB has no match |
| Document store | Amazon S3 | Curated manufacturer manuals/spec sheets, source for Knowledge Base ingestion |
| Notifications | SES / SNS | Sends reminder + cost-recommendation alerts to the user |
| Interface | Lightweight web form or CLI (Flask/FastAPI) | Manual appliance entry, optional live demo |
| Observability | Strands built-in tracing | Shows agent decision path in the demo video |

---

## Submission requirements checklist

- [ ] Text description (problem, audience, how it works)
- [ ] Public code repo (MIT or Apache license, README, setup instructions)
- [ ] Architecture diagram
- [ ] Demo video (max 5 min): problem, who it's for, why it matters
- [ ] AWS Builder ID
- [ ] Optional live demo link
- [ ] (Bonus) Build story published on builder.aws.com, titled with "Agents for Humans"
