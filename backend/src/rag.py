"""RAG extraction: turn retrieved manual excerpts into the same structured
shape as backend/data/appliances.json, so a RAG hit can be cached back into
Storage and treated identically to a structured-table hit on every later
lookup (Day 4).
"""

from pydantic import BaseModel, Field
from strands import Agent

from model import get_model

EXTRACTION_SYSTEM_PROMPT = """You extract structured appliance maintenance data from \
manufacturer manual excerpts. Only use information present in the excerpts — never \
invent numbers. If the excerpts don't mention a field, make your best reasonable estimate \
and say so in the notes field, but prefer leaving cost/lifespan fields as null over guessing \
wildly.
"""


class ApplianceReferenceExtraction(BaseModel):
    display_name: str = Field(description="Human-readable appliance name")
    service_interval_months: int | None = Field(description="Recommended service interval, in months")
    typical_lifespan_years: float | None = Field(description="Typical lifespan before replacement, in years")
    repair_cost_range_usd: list[float] = Field(description="[low, high] typical repair cost in USD")
    replacement_cost_range_usd: list[float] = Field(description="[low, high] typical replacement cost in USD")
    notes: str = Field(description="One-sentence summary of the key maintenance guidance")


def extract_reference_data(appliance_type: str, manual_excerpts: list[str]) -> dict | None:
    """Extract reference-table-shaped data from retrieved manual excerpts.

    Returns None if no excerpts were provided, or the model fails to
    produce a usable extraction.
    """
    if not manual_excerpts:
        return None

    agent = Agent(model=get_model(), system_prompt=EXTRACTION_SYSTEM_PROMPT)
    excerpts_text = "\n\n---\n\n".join(manual_excerpts)

    result = agent(
        f"Appliance type: {appliance_type}\n\nManual excerpts:\n\n{excerpts_text}\n\n"
        "Extract the structured maintenance data.",
        structured_output_model=ApplianceReferenceExtraction,
    )

    if not result.structured_output:
        return None

    extracted = result.structured_output.model_dump()
    extracted["category"] = "RAG"
    return extracted
