"""
Module: conftest
Purpose: Pytest configuration and shared test fixtures for NeuralWatch SDK.
Part of: NeuralWatch - AI Fleet Observatory for Splunk
Hackathon: Splunk Agentic Ops 2026

Dependencies:
  - pytest: test runner framework
"""

import pytest


class MockUsage:
    def __init__(self, prompt_tokens: int, completion_tokens: int):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens

class MockChoice:
    def __init__(self, finish_reason: str = "stop"):
        self.finish_reason = finish_reason

class MockCompletion:
    def __init__(self, model: str = "gpt-4o", prompt_tokens: int = 100, completion_tokens: int = 50, finish_reason: str = "stop"):
        self.model = model
        self.usage = MockUsage(prompt_tokens, completion_tokens)
        self.choices = [MockChoice(finish_reason)]

@pytest.fixture
def sample_openai_response() -> MockCompletion:
    """Fixture providing a mock OpenAI API completion response structure."""
    return MockCompletion(model="gpt-4o", prompt_tokens=512, completion_tokens=128)
