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
from runtime import build_storage, build_vector_store


def main() -> None:
    storage = build_storage()
    vector_store = build_vector_store()
    agent = build_orchestrator(storage, vector_store=vector_store)

    # agent()'s default callback_handler already streams the response to
    # stdout (visible in Railway's cron logs) — don't print the returned
    # AgentResult too, or the final text shows up twice.
    agent("Check if any of my appliances need maintenance.")


if __name__ == "__main__":
    main()
