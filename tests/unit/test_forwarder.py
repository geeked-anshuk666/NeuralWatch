"""
Module: test_forwarder
Purpose: Unit tests for the async HEC forwarder SDK module.
Part of: NeuralWatch — AI Fleet Observatory for Splunk
Hackathon: Splunk Agentic Ops 2026

Dependencies:
  - requests_mock
"""

import requests_mock
from neuralwatch_sdk.forwarder import configure, _send_hec_request

def test_hec_success_path():
    hec_url = "https://localhost:8088/services/collector/event"
    hec_token = "test-token"
    
    with requests_mock.Mocker() as m:
        m.post(hec_url, json={"text": "Success", "code": 0}, status_code=200)
        
        configure(hec_url, hec_token, verify_ssl=False)
        result = _send_hec_request("neuralwatch_ai_calls", {"model": "test-model"})
        
        assert result is True
        assert m.called
        assert m.last_request.headers["Authorization"] == f"Splunk {hec_token}"

def test_hec_failure_retries_and_drops():
    hec_url = "https://localhost:8088/services/collector/event"
    hec_token = "test-token"
    
    with requests_mock.Mocker() as m:
        m.post(hec_url, status_code=500)
        
        configure(hec_url, hec_token, verify_ssl=False)
        
        # Override RETRY_DELAYS in module temporarily to keep test fast
        import neuralwatch_sdk.forwarder as f
        original_delays = f.RETRY_DELAYS
        f.RETRY_DELAYS = [0.01, 0.01, 0.01]
        
        try:
            result = _send_hec_request("neuralwatch_ai_calls", {"model": "test-model"})
            assert result is False
            # Should retry 3 times
            assert m.call_count == 3
        finally:
            f.RETRY_DELAYS = original_delays
