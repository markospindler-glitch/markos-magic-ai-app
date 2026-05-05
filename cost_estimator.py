"""Simple estimated API cost tracking for the current job."""

from __future__ import annotations


INPUT_PRICE_PER_1M = 5.00
OUTPUT_PRICE_PER_1M = 30.00
TOKENS_PER_WORD = 1.3


def estimate_tokens(text: str) -> int:
    """Estimate token count from words."""
    words = len((text or "").split())
    return round(words * TOKENS_PER_WORD)


def estimate_cost(input_text: str, output_text: str = "") -> dict[str, float]:
    """Estimate input/output tokens and cost."""
    input_tokens = estimate_tokens(input_text)
    output_tokens = estimate_tokens(output_text)
    input_cost = input_tokens / 1_000_000 * INPUT_PRICE_PER_1M
    output_cost = output_tokens / 1_000_000 * OUTPUT_PRICE_PER_1M
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost": input_cost + output_cost,
    }


def new_cost_entry(step: str, input_text: str, output_text: str = "") -> dict[str, str | int | float]:
    """Create one cost entry for display in Streamlit."""
    estimate = estimate_cost(input_text, output_text)
    return {
        "Step": step,
        "Input tokens": estimate["input_tokens"],
        "Output tokens": estimate["output_tokens"],
        "Estimated cost (EUR)": round(estimate["cost"], 4),
    }


def total_cost(entries: list[dict]) -> float:
    """Return total estimated cost for a job."""
    return round(sum(float(entry.get("Estimated cost (EUR)", entry.get("Estimated cost", 0))) for entry in entries), 4)
