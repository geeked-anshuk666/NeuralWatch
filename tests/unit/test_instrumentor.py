"""
Module: test_instrumentor
Purpose: Unit tests for the SDK patching/instrumentation module.
Part of: NeuralWatch — AI Fleet Observatory for Splunk
Hackathon: Splunk Agentic Ops 2026

Dependencies:
  - unittest.mock
"""

import sys
from unittest.mock import MagicMock

def test_instrumentation_openai_monkey_patch():
    # Mock Completion and openai library to simulate discovery without real import failures
    mock_completions_cls = MagicMock()
    original_create = mock_completions_cls.create
    
    # We patch completions class import in instrumentor
    sys.modules['openai'] = MagicMock()
    sys.modules['openai.resources.chat.completions'] = MagicMock()
    sys.modules['openai.resources.chat.completions'].Completions = mock_completions_cls
    
    from neuralwatch_sdk.instrumentor import instrument
    import neuralwatch_sdk.instrumentor as inst
    inst._instrumented = False
    inst._original_openai_create = None
    
    # Call instrument
    instrument(
        service="test-service",
        team="test-team",
        splunk_hec_url="https://localhost:8088/services/collector/event",
        splunk_hec_token="test-token"
    )
    
    # Verify the Completions.create method was patched (wrapped)
    assert mock_completions_cls.create != original_create
