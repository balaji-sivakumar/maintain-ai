# Maintain-AI — Milestones

Build window: **Sep 9 – Sep 14, 2026, 5:00pm PDT** (Agents for Humans Hackathon deadline)

Build is split into two stages: everything in **Stage A** runs entirely on your machine against local AWS-equivalents (LocalStack + SAM), with zero real AWS resources created. **Stage B** swaps those local endpoints for real AWS services one at a time — same code, different config — so deployment never blocks on local development being "done."

| AWS service | Local equivalent used in Stage A |
|---|---|
| DynamoDB | LocalStack (`dynamodb`) |
| S3 | LocalStack (`s3`) |
| SNS / SES | LocalStack (`sns`, `ses`) |
| EventBridge | LocalStack (`events`) or a local scheduler script |
| Lambda / API Gateway | AWS SAM CLI (`sam local invoke` / `sam local start-api`) |
| Bedrock (model + Knowledge Base) | OpenAI (`strands.models.openai.OpenAIModel`) as the model substitute for agent reasoning/tool-use; no substitute exists for the Knowledge Base itself (Stage B) |

Strands' model provider is a swappable object (`Agent(model=..., tools=[...])`), so Stage A runs the orchestrator and Cost Estimator agents against an OpenAI key and Stage B swaps in `BedrockModel` — no agent/tool code changes required. The Bedrock Knowledge Base RAG fallback (Day 4) has no local or OpenAI substitute and always needs real AWS.

---

## Stage A — Local build (Day 1–3)

### Day 1 — Sep 9 (today)

- [x] Finalize use case: home maintenance predictor with cost estimator sub-agent
- [x] Finalize architecture (agent design + AWS deployment)
- [x] Scaffold Strands project locally (`pyproject.toml`, `src/maintain_ai`, `Storage`/`Model` interfaces, `LocalJsonStorage` impl, smoke tests passing)
- [ ] Set up LocalStack via Docker for local DynamoDB/S3/SNS/EventBridge *(deferred — only needed if Option A/AWS is picked at the Day 4 checkpoint)*
- [x] Define structured JSON table — 20 common appliances with service intervals and repair/replacement cost ranges (`data/appliances.json`)
- [ ] *(parallel, non-blocking)* Set up AWS account / AWS Builder ID
- [ ] *(parallel, non-blocking)* Request $50 AWS credits (Resources tab on Devpost hackathon page)

### Day 2 — Sep 10

- [ ] Stand up local DynamoDB table via LocalStack (boto3 `endpoint_url=http://localhost:4566`)
- [ ] Build `add_appliance`, `check_due_maintenance`, `log_completed_service` tools against local DynamoDB
- [ ] Wire orchestrator agent against structured table only (no RAG yet); model calls via `OpenAIModel` (swap to `BedrockModel` once AWS access is ready — same agent code)
- [ ] Test end-to-end locally with mock appliance data
- [ ] Verify "silent when nothing due, speaks up when due" behavior

### Day 3 — Sep 11

- [ ] Build Cost Estimator sub-agent
- [ ] Add `estimate_repair_cost`, `estimate_replacement_cost`, `recommend_repair_or_replace` (structured data only)
- [ ] Wire Agent-as-Tool call from orchestrator to Cost Estimator
- [ ] Test the full loop: overdue appliance → cost estimate → repair/replace recommendation
- [ ] Still fully local — no real AWS resources created yet
- [ ] *(stretch, demo polish — only once the loop above works)* Expose Strands' native tool-execution event stream over a FastAPI WebSocket endpoint

---

## Stage B — AWS integration & deployment (Day 4–6)

### Day 4 — Sep 12

- [ ] Create real S3 bucket, upload curated appliance manuals
- [ ] Create real Bedrock Knowledge Base + OpenSearch Serverless, run first ingestion sync
- [ ] Wire `retrieve_and_generate()` as RAG fallback in `lookup_maintenance_interval` and cost estimation tools — swap stubbed model calls for real Bedrock
- [ ] Add DynamoDB cache-back on successful RAG lookup — swap LocalStack endpoint for real AWS (same boto3 code, config-only change)
- [ ] **Risk checkpoint:** if Knowledge Base sync is delayed, fall back to structured-table-only for the demo

### Day 5 — Sep 13

- [ ] Package Lambda handler wrapping the same agent code used in Stage A
- [ ] `sam local invoke` / `sam local start-api` to verify the handler before deploying
- [ ] Deploy agent runtime to real Lambda
- [ ] Wire EventBridge (daily trigger) and API Gateway (manual add/update)
- [ ] Wire SES/SNS notifications (real)
- [ ] Write README, add MIT/Apache license, confirm setup instructions run clean
- [ ] Finalize architecture diagram for submission
- [ ] *(stretch, demo polish)* Build the live tool-trace frontend (Next.js), deploy to Vercel, point it at the live WebSocket endpoint
- [ ] Record demo video (problem, audience, why it matters, live walkthrough — feature the live trace UI if it's ready)

### Day 6 — Sep 14 (deadline 5:00pm PDT)

- [ ] Final end-to-end testing against the real deployed stack
- [ ] Set up live demo link, if time permits
- [ ] Submit on Devpost: text description, repo link, architecture diagram, demo video, AWS Builder ID
- [ ] *(Bonus)* Publish build story on builder.aws.com with "Agents for Humans" in the title

---

## Notes

- Day 4 (Knowledge Base setup) is the highest-risk day — AWS sync/indexing can take longer than expected.
- A fully working structured-table core loop is a safer fallback than a broken RAG integration if time runs short.
- Because storage (LocalStack → real AWS) and the model provider (OpenAI → Bedrock) sit behind thin interfaces from Day 1, Stage B is mostly config swaps, not rewrites — deployment can slip a day without threatening Stage A's demo-ability.
- The Bedrock Knowledge Base (RAG over manuals) has no local or OpenAI substitute — it's real AWS regardless of which model provider is used for agent reasoning.
- The live tool-trace frontend (Vercel + WebSocket) is presentation polish, not a submission requirement — it's explicitly sequenced after the core agent loop works (Day 3) so it never displaces functional build time, and it's stack-independent (works the same against Option A or Option B's backend).
