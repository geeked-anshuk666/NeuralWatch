"""
Package: neuralwatch_sdk
Purpose: Main SDK init file, exposing public API.
Part of: NeuralWatch — AI Fleet Observatory for Splunk
Hackathon: Splunk Agentic Ops 2026

Dependencies:
  - None (exposes APIs from submodules)

Usage:
  import neuralwatch_sdk
  neuralwatch_sdk.instrument(...)
"""

from neuralwatch_sdk.instrumentor import (
    instrument,
    auto_instrument,
    set_session_id,
    get_session_id,
    trace_context
)

__all__ = ["instrument", "auto_instrument", "set_session_id", "get_session_id", "trace_context"]

