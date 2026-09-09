"""Model provider factory.

Swaps between OpenAI (Stage A / Option B) and Bedrock (Stage B / Option A)
based on MODEL_PROVIDER, so agent and tool code never imports a concrete
model class directly.
"""

import os


def get_model():
    provider = os.environ.get("MODEL_PROVIDER", "openai").lower()

    if provider == "openai":
        from strands.models.openai import OpenAIModel

        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required when MODEL_PROVIDER=openai")
        return OpenAIModel(
            client_args={"api_key": api_key},
            model_id="gpt-4o",
        )

    if provider == "bedrock":
        from strands.models import BedrockModel

        return BedrockModel(
            model_id="anthropic.claude-3-5-sonnet-20241022-v2:0",
            region_name=os.environ.get("AWS_REGION", "us-east-1"),
        )

    raise ValueError(f"Unknown MODEL_PROVIDER: {provider!r} (expected 'openai' or 'bedrock')")
