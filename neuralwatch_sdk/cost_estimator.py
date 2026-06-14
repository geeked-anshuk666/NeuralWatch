"""
Module: cost_estimator
Purpose: Estimates the USD cost of LLM calls based on tokens and model.
Part of: NeuralWatch - AI Fleet Observatory for Splunk
Hackathon: Splunk Agentic Ops 2026

Dependencies:
  - None (standard library only)

Usage:
  from neuralwatch_sdk.cost_estimator import estimate_cost
  cost = estimate_cost("gpt-4o", 1000, 500)
"""

# Per-model cost model matching neuralwatch_cost_model.csv
# Key: model_name, Value: (input_cost_per_1k, output_cost_per_1k)
COST_TABLE: dict[str, tuple[float, float]] = {
    "gpt-4o": (0.005, 0.015),
    "gpt-4o-mini": (0.00015, 0.0006),
    "gpt-4-turbo": (0.01, 0.03),
    "claude-3-5-sonnet-20241022": (0.003, 0.015),
    "claude-3-5-haiku-20241022": (0.0008, 0.004),
    "claude-3-opus-20240229": (0.015, 0.075),
    "claude-sonnet-4-6": (0.003, 0.015),
    "unknown": (0.01, 0.03)
}

def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """
    Estimate the USD cost of an AI API call.

    Uses the neuralwatch_cost_model lookup table.
    Falls back to unknown model pricing ($0.01/1K input and $0.03/1K output) for unknown models.

    Args:
        model: Model name string (e.g. "gpt-4o", "claude-3-5-sonnet-20241022")
        input_tokens: Number of prompt tokens consumed
        output_tokens: Number of completion tokens generated

    Returns:
        Estimated cost in USD as float, rounded to 6 decimal places.
        Returns 0.0 on any error (never raises).

    Example:
        >>> estimate_cost("gpt-4o", 1000, 500)
        0.0125
    """
    try:
        # Fetch pricing details, fallback to 'unknown' model if not found
        in_cost, out_cost = COST_TABLE.get(model, COST_TABLE["unknown"])
        
        # Calculate cost based on per-1k-tokens pricing
        cost = (input_tokens / 1000.0 * in_cost) + (output_tokens / 1000.0 * out_cost)
        return round(cost, 6)
    except Exception:
        # Never crash the parent application; return 0.0 on any estimate calculation error
        return 0.0
