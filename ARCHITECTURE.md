# Maintain-AI — Architecture

This document is the source of truth for the agent design and data flow. Those are **firm** — they don't change based on infrastructure choice.

**Stack decision: Option B (Railway + Neon + Chroma) is committed.** AWS credits aren't available for this build, so Option A (AWS-native) below is kept only as a documented reference — it's not being pursued. This was resolved ahead of the original Day 4 checkpoint since the credit question is settled.

---

## Agent design (Agent-as-Tool pattern)

Built on the **Strands Agents SDK** — this is the hackathon's one hard requirement and doesn't change regardless of stack.

**Home Maintenance Agent (orchestrator)**
- `add_appliance(name, brand, model, install_date)`
- `check_due_maintenance()`
- `lookup_maintenance_interval(brand, model)` — structured table first, RAG fallback second
- `draft_service_reminder(appliance)`
- `log_completed_service(appliance)`
- `estimate_cost(appliance_issue)` — invokes the Cost Estimator Agent

**Cost Estimator Agent (sub-agent, invoked as a tool)**
- `estimate_repair_cost(appliance, issue)`
- `estimate_replacement_cost(appliance)`
- `recommend_repair_or_replace(appliance, age, repair_cost, replacement_cost)`

---

## Logical data flow

1. **Trigger** (daily schedule, or a manual add/update) invokes the orchestrator.
2. `check_due_maintenance()` queries **Storage** for appliances due or overdue.
3. `lookup_maintenance_interval()` checks the structured table in **Storage** first. On a miss, it falls back to **VectorStore** RAG (retrieve manual excerpts → generate an answer via **Model**), then caches the result back into **Storage** so the same lookup skips RAG next time.
4. If something is due/overdue, the orchestrator calls the Cost Estimator sub-agent (Agent-as-Tool) to get a repair-vs-replace recommendation.
5. `draft_service_reminder()` composes the message; **Notifier** delivers it to the user.
6. `log_completed_service()` updates **Storage** once the user marks a service done.

The agent only speaks up in step 5 when step 2 or 4 actually found something due — silence is the default state.

---

## System interfaces (firm contracts, pluggable implementations)

These four seams are where the stack choice lives. Agent and tool code is written against the interface, never the concrete implementation, so swapping a backing service is a config change.

| Interface | Responsibility | AWS-native impl | Railway/Neon/Chroma impl |
|---|---|---|---|
| **Model** | Agent reasoning + tool-use | `BedrockModel` (Claude) | `OpenAIModel` |
| **Storage** | Appliance state, structured interval/cost table, RAG cache | DynamoDB | Neon Postgres (serverless; `LocalJsonStorage`/SQLite for local dev) |
| **VectorStore** | Embeddings over appliance manuals for RAG fallback | Bedrock Knowledge Base + OpenSearch Serverless | Chroma Cloud (local `PersistentClient` fallback when no Chroma Cloud credentials are set, e.g. local dev) |
| **Notifier** | Delivers reminders/recommendations | SES / SNS | SMTP / Resend, or console log for local dev |
| **Trigger** | Fires the daily maintenance check | EventBridge | Railway cron |
| **API surface** | Manual add/update from the user | API Gateway + Lambda | Railway-hosted FastAPI service |
| **EventStream** | Streams tool-execution events out to the live trace frontend | API Gateway WebSocket API | FastAPI WebSocket endpoint (same Railway service) |

---

## Live tool trace (judging UI)

Strands emits tool-use events natively via async-iterator streaming or callback handlers as the orchestrator runs — no custom tracing needed, just a subscriber. The **EventStream** interface (above) forwards those events to a small **Next.js frontend deployed on Vercel**, which renders the agent's decision path live: `check_due_maintenance → found HVAC due → estimate_cost → Cost Estimator invoked → recommend_repair_or_replace: repair`.

The frontend is stack-independent by design, though with Option B committed it only needs to point at the Railway FastAPI WebSocket endpoint.

This is presentation polish, not a functional requirement — it strengthens the Design/Presentation judging criteria (visualizing "silent until it matters" instead of only narrating it) but is explicitly sequenced *after* the core agent loop (Day 2–3) works, so it never blocks the functional build.

**Status: built and deployed.** [maintain-ai-dashboard.vercel.app](https://maintain-ai-dashboard.vercel.app) — the `/ws/check` endpoint reduces Strands' raw event stream (which includes token-by-token deltas of tool-call arguments) to `tool_call`/`tool_result`/`text_delta`/`done` events (`backend/src/live_trace.py`), correlated by `tool_use_id` rather than name so repeated calls to the same tool (e.g. `draft_service_reminder` once per due appliance) don't get mismatched.

---

## Deployment options

### Option A — AWS-native (reference only, not pursued)

```
User (web/CLI)      Judge / demo viewer
      |                     |
      v                     v
+---------------- AWS cloud -------------+   +------------------+
|                                         |   |  Next.js on      |
|   API Gateway         EventBridge      |   |  Vercel          |
|   (add/update)        (daily trigger)  |   |  (live tool      |
|        \                    /          |   |   trace UI)      |
|         v                  v           |   +--------^---------+
|          Agent runtime (Lambda)        |            |
|          Strands agents on Bedrock     |----WebSocket API------
|        /            |              \   |
|       v              v               v |
|  DynamoDB        SES / SNS       Knowledge base
|  (appliance      (notifications  (OpenSearch vectors)
|   state)          out)                ^
|                       |                |
|                       |           S3 bucket
|                       |          (appliance manuals)
+-----------------------|----------------+
                         v
                  User (email/SMS alert)
```

Would have strengthened the Technical Implementation score per the hackathon rubric ("Deploying with Amazon Bedrock AgentCore... will strengthen your Technical Implementation score, but it's not required"). Not pursued: AWS credits aren't available for this build.

### Option B — Railway + Neon + Chroma (committed)

```
User (web/CLI)      Judge / demo viewer
      |                     |
      v                     v
+-------------- Railway --------------+   +------------------+
|                                      |   |  Next.js on      |
|   FastAPI service    Railway cron   |   |  Vercel          |
|   (add/update)       (daily trig.)  |   |  (live tool      |
|        \                  /         |   |   trace UI)      |
|         v                v          |   +--------^---------+
|      Agent runtime (long-running)   |            |
|      Strands agents on OpenAI       |----WebSocket (FastAPI)--
|                  |                  |
|                  v                  |
|             SMTP/Resend             |
|            (notifications)          |
+------------------|-------------------+
                    v
             User (email alert)

External services (outside Railway, called over the network):
  - Chroma Cloud    — vector store over appliance manuals
  - Neon Postgres   — appliance state, structured table, RAG cache
```

No AWS account/credit dependency at all. Fully within the hackathon's hard requirement (Strands Agents SDK) since AWS usage is optional, not required, per the rules. **This is the path being built.**

---

## Decision point (resolved)

AWS credits aren't available for this build, so **Option B is committed** rather than a fallback. Option A satisfies every hard submission requirement too and only adds rubric points on Technical Implementation — a working Option B demo beats a stalled AWS integration on every other judged axis (Design, Impact, Creativity, Presentation).

Because agent/tool code is written against the interfaces above, this decision did not require rewriting the orchestrator, the Cost Estimator sub-agent, or any tool logic — only the concrete Storage/VectorStore/Notifier/Trigger/EventStream implementations. Note: the **AWS Builder ID account is still needed** — it's a fixed submission-form requirement per the hackathon rules, independent of whether AWS services are actually used.
