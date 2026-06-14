"""
Module: test_cost_estimator
Purpose: Unit tests for the cost estimator SDK module.
Part of: NeuralWatch - AI Fleet Observatory for Splunk
Hackathon: Splunk Agentic Ops 2026

Dependencies:
  - pytest
"""

from neuralwatch_sdk.cost_estimator import estimate_cost

def test_known_models_return_correct_costs():
    # gpt-4o: $0.005/1k input, $0.015/1k output
    # 1000 input, 1000 output = 0.005 + 0.015 = 0.02
    cost = estimate_cost("gpt-4o", 1000, 1000)
    assert cost == 0.020000

    # gpt-4o-mini: $0.00015/1k input, $0.0006/1k output
    # 2000 input, 1000 output = 0.0003 + 0.0006 = 0.0009
    cost = estimate_cost("gpt-4o-mini", 2000, 1000)
    assert cost == 0.000900

def test_unknown_model_returns_default_cost():
    # unknown: $0.01/1k input, $0.03/1k output
    cost = estimate_cost("my-weird-custom-model", 1000, 1000)
    assert cost == 0.040000

def test_zero_tokens_returns_zero_cost():
    cost = estimate_cost("gpt-4o", 0, 0)
    assert cost == 0.0
