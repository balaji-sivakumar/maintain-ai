"""Railway cron entrypoint: run the daily maintenance check once, then exit.

Railway cron services must terminate after doing their work — see
docs.railway.com/cron-jobs. This is intentionally a plain script, not the
FastAPI app, since a cron service isn't meant to stay listening.

Usage (Railway service Start Command):
    python scripts/cron_check.py
"""

from dotenv import load_dotenv

load_dotenv()

from agents.orchestrator import build_orchestrator
from confirmations import persist_if_interrupted
from runtime import build_notifier, build_storage, build_vector_store, setup_telemetry


def main() -> None:
    telemetry = setup_telemetry()
    storage = build_storage()
    vector_store = build_vector_store()
    notifier = build_notifier()
    agent = build_orchestrator(storage, vector_store=vector_store, notifier=notifier)

    # agent()'s default callback_handler already streams the response to
    # stdout (visible in Railway's cron logs) — don't print the returned
    # AgentResult too, or the final text shows up twice.
    result = agent("Check if any of my appliances need maintenance.")

    # submit_maintenance_request is gated behind human approval (Day 6): a
    # due appliance's repair/replace request pauses the run here rather than
    # recording anything. This process exits right after, so the pending
    # confirmation is persisted to storage — a later, separate request (the
    # dashboard's Approve/Deny click) resumes it on a fresh Agent instance
    # via resume_confirmation().
    confirmation = persist_if_interrupted(storage, agent, result)
    if confirmation:
        appliance_ids = [r.get("appliance_id") for r in confirmation["requests"]]
        print(f"Awaiting human approval for maintenance requests on: {appliance_ids}")

    if telemetry:
        # BatchSpanProcessor flushes on a background timer; this process
        # exits right after the line above, so without an explicit flush
        # the last batch of spans would be dropped before they're sent.
        telemetry.tracer_provider.force_flush()


if __name__ == "__main__":
    main()
