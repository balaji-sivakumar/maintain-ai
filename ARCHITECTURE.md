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
5. `draft_service_reminder()` composes an informational message; the orchestrator calls `send_notification()` freely — **Notifier** delivers it unconditionally, since it's just telling the household something needs attention.
6. For every due/overdue appliance, the orchestrator also calls `submit_maintenance_request()` — the actual decision to act on the Cost Estimator's recommendation. This one is gated behind human approval (see "Human-in-the-loop confirmations" below): nothing is recorded as requested until a person approves it.
7. `log_completed_service()` updates **Storage** once the user marks a service done.

The agent only speaks up in steps 5–6 when step 2 or 4 actually found something due — silence is the default state.

---

## System interfaces (firm contracts, pluggable implementations)

These four seams are where the stack choice lives. Agent and tool code is written against the interface, never the concrete implementation, so swapping a backing service is a config change.

| Interface | Responsibility | AWS-native impl | Railway/Neon/Chroma impl |
|---|---|---|---|
| **Model** | Agent reasoning + tool-use | `BedrockModel` (Claude) | `OpenAIModel` |
| **Storage** | Appliance state, structured interval/cost table, RAG cache | DynamoDB | Neon Postgres (serverless; `LocalJsonStorage`/SQLite for local dev) |
| **VectorStore** | Embeddings over appliance manuals for RAG fallback | Bedrock Knowledge Base + OpenSearch Serverless | Chroma Cloud (local `PersistentClient` fallback when no Chroma Cloud credentials are set, e.g. local dev) |
| **Notifier** | Delivers reminders/recommendations | SES / SNS | Resend (sandbox sender), or console log for local dev |
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

## Human-in-the-loop confirmations (enforced, not advisory)

"Advisory only" describes the Cost Estimator's repair-vs-replace output — the agent only recommends. The consequential step is *acting* on that recommendation: `submit_maintenance_request()` is what records the household's decision to actually proceed with a repair or replacement. That's the one gated behind human approval, using Strands' built-in `HumanInTheLoop` intervention handler (`strands.vended_interventions.hitl`) — `send_notification` (informational only: "your HVAC is due") runs freely and always fires when something's due, decoupled entirely from the approval gate.

`build_orchestrator()` registers `HumanInTheLoop(allowed_tools=["*", "!submit_maintenance_request"])` on the Agent. The orchestrator calls `submit_maintenance_request` once per due/overdue appliance (not bundled into one call). When it does this several times in the same turn, Strands pauses with *every* one of them as a separate pending interrupt at once — verified directly against the SDK, not assumed from docs — so a single pause can represent several independent per-appliance decisions.

The pause has to survive past the request that raised it: the approval click always arrives as a *separate* HTTP request, potentially after the WebSocket that streamed the original check has closed, or after an unattended cron run has already exited. `backend/src/confirmations.py` bridges this using Strands' `Snapshot` API:

1. `persist_if_interrupted()` — when a run's `AgentResult.stop_reason == "interrupt"`, pairs every pending interrupt with the structured tool-call input that raised it (appliance_id/action/notes, read off the paused assistant message rather than parsed from `HumanInTheLoop`'s human-readable prompt string), and snapshots the paused agent (`agent.take_snapshot(preset="session")`). The whole batch — one confirmation id, a `requests` list with one entry per appliance, and the snapshot — is saved to **Storage**'s `confirmations` table/file.
2. `resume_confirmation()` — given a confirmation id and the list of appliance ids the household approved, loads the snapshot onto a **freshly-built** orchestrator Agent (`load_snapshot()`) and resumes it with one `interruptResponse` per pending request in a *single* call — approved appliances get `response: true`, every other appliance in the batch gets `response: false`. `HumanInTheLoop` re-evaluates each independently on resume: approved ones actually call `submit_maintenance_request` (recording the decision in Storage), denied ones cancel with no record made.

Both the multi-interrupt pause and the cross-instance resume were verified empirically against the real SDK (not assumed from docs): approving a subset of a 3-appliance batch executes exactly those, denies the rest, and a fresh `Agent` instance (simulating a separate request/process) resumes the snapshot correctly.

**Surfaces:**
- `/check` (cron path) and `/ws/check` (live trace) both persist a pending confirmation instead of silently completing when the run pauses; the cron script prints a note to its logs so it's visible even though nothing calls it back.
- `GET /confirmations` lists everything pending, one `requests` entry per due appliance. `POST /confirmations/{id}/respond` (`{"approved_appliance_ids": [...]}`) resolves the whole batch in one round trip — appliances not listed are denied — chaining into another persisted confirmation if the resumed run hits a further gate.
- The dashboard's "Pending approvals" panel is the actual control: one card per pause, a checkbox per appliance (all checked by default), one "Submit decisions" action. The live tool trace shows the pause inline (`confirmation_required` event, listing every pending appliance) but defers the actual decision to that panel, since the WebSocket that surfaced it may no longer be open by the time a human responds.

**Scope boundary — what "submit" actually means.** `submit_maintenance_request()` records that the household approved acting on a recommendation (`requested_action`, `request_notes`, and a `status` on the appliance) — it does not book a contractor, place an order, or contact a vendor. In reality, fulfillment is appliance-specific and heterogeneous: an HVAC repair goes through a contractor, a water heater replacement through a plumber or retailer, an EV charger issue through the utility or manufacturer — each with its own real-world channel, credentials, and API (or no API at all). Building those integrations is a separate, much larger project and explicitly out of scope here.

This follows the same pattern already used elsewhere in this build: `ResendNotifier` sends through a sandbox sender rather than a production mail system, and the manuals under `data/manuals/` are mock excerpts standing in for real manufacturer PDFs. The Storage/VectorStore/Notifier interfaces exist precisely so a concrete implementation can be swapped in without touching agent/tool code — `submit_maintenance_request` is the same kind of seam: it's the boundary where the agent's job (recommend, get explicit human sign-off, record the decision) ends and a real fulfillment integration would begin. The demo's claim is narrower and fully true: a human decided, and that decision was durably recorded — not that a technician has been dispatched.

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
|               Resend                |
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
