# Maintain-AI — Architecture

This document is the source of truth for the agent design and data flow. Those are **firm** — they don't change based on infrastructure choice. The underlying stack (AWS-native vs. Railway/Chroma) is an **open decision** below, resolved by a Day 4 checkpoint based on AWS credit/account availability.

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

| Interface | Responsibility | AWS-native impl | Railway/Chroma impl |
|---|---|---|---|
| **Model** | Agent reasoning + tool-use | `BedrockModel` (Claude) | `OpenAIModel` |
| **Storage** | Appliance state, structured interval/cost table, RAG cache | DynamoDB | Railway Postgres (or SQLite for local dev) |
| **VectorStore** | Embeddings over appliance manuals for RAG fallback | Bedrock Knowledge Base + OpenSearch Serverless | Chroma (self-hosted or Chroma Cloud) |
| **Notifier** | Delivers reminders/recommendations | SES / SNS | SMTP / Resend, or console log for local dev |
| **Trigger** | Fires the daily maintenance check | EventBridge | Railway cron |
| **API surface** | Manual add/update from the user | API Gateway + Lambda | Railway-hosted FastAPI service |

---

## Deployment options

### Option A — AWS-native

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

Strengthens Technical Implementation score per the hackathon rubric ("Deploying with Amazon Bedrock AgentCore... will strengthen your Technical Implementation score, but it's not required"). Cost/setup risk: AWS Builder ID, credit approval, and Bedrock Knowledge Base sync time — see risk note below.

### Option B — Railway + Chroma

```
User (web/CLI)
      |
      v
+---------------------------- Railway ----------------------------+
|                                                                   |
|   FastAPI service        Railway cron                            |
|   (add/update)           (daily trigger)                         |
|        \                       /                                 |
|         v                     v                                  |
|          Agent runtime (long-running process)                    |
|          Strands agents on OpenAI                                |
|        /            |                  \                         |
|       v              v                   v                        |
|  Postgres         SMTP/Resend        Chroma                      |
|  (appliance       (notifications     (vector store over          |
|   state)           out)               appliance manuals)         |
+-------------------------------------------------------------------+
                         |
                         v
                  User (email alert)
```

No AWS account/credit dependency at all. Fully within the hackathon's hard requirement (Strands Agents SDK) since AWS usage is optional, not required, per the rules.

---

## Decision point

**Checkpoint: Day 4 (Sep 12).** If AWS account/credits/Bedrock Knowledge Base access isn't in place by then, default to **Option B** for the rest of the build and the submission demo, rather than losing time to AWS setup friction. Either option satisfies every hard submission requirement; Option A only adds rubric points on Technical Implementation, and a working Option B demo beats a stalled Option A integration on every other judged axis (Design, Impact, Creativity, Presentation).

Because agent/tool code is written against the interfaces above, this decision does not require rewriting the orchestrator, the Cost Estimator sub-agent, or any tool logic — only the concrete Model/Storage/VectorStore/Notifier/Trigger implementations passed in at startup.
