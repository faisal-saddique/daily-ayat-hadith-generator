"""Quick test for OpenRouter fallback with updated model ID."""

import os
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.openrouter import OpenRouterModel
from pydantic_ai.providers.openrouter import OpenRouterProvider

load_dotenv()

class TestOutput(BaseModel):
    result: str = Field(description="Short answer")

def test_model(model_name: str, api_key: str):
    print(f"\nTesting: {model_name}")
    try:
        model = OpenRouterModel(model_name, provider=OpenRouterProvider(api_key=api_key))
        agent = Agent(model, output_type=TestOutput, instructions="Answer briefly.")
        result = agent.run_sync(
            "Translate 'بسم الله' to English in one phrase.",
            model_settings={"max_tokens": 256}
        )
        print(f"  ✓ Success: {result.output.result}")
        return True
    except Exception as e:
        print(f"  ✗ Failed: {e}")
        return False

if __name__ == "__main__":
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("ERROR: OPENROUTER_API_KEY not set in .env")
        exit(1)

    print(f"OpenRouter key loaded: {api_key[:8]}...")

    models = [
        "anthropic/claude-sonnet-4-5",
    ]

    results = {m: test_model(m, api_key) for m in models}

    print("\n--- Summary ---")
    for m, ok in results.items():
        status = "✓" if ok else "✗"
        print(f"  {status} {m}")
