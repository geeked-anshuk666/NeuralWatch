"""
Module: instrumentor
Purpose: Monkey-patches OpenAI and Anthropic SDKs to automatically capture telemetry and prompt text.
Part of: NeuralWatch - AI Fleet Observatory for Splunk
Hackathon: Splunk Agentic Ops 2026

Dependencies:
  - openai: to patch client completions
  - anthropic: to patch client messages
  - hashlib: for prompt hashing
  - json: for loading local config files
  - os, path: for finding configs

Usage:
  from neuralwatch_sdk.instrumentor import instrument, auto_instrument
  instrument("checkout-service", "payments-engineering", "https://localhost:8088", "token")
"""

import os
import time
import uuid
import hashlib
import json
import logging
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Optional, Any
from neuralwatch_sdk.cost_estimator import estimate_cost
from neuralwatch_sdk.forwarder import configure, send_event

logger = logging.getLogger("neuralwatch")

# Global variables tracking configuration
_service: str = ""
_team: str = ""
_capture_prompts: bool = True
_instrumented: bool = False

# Thread-local tracing context
_context = threading.local()

def set_session_id(session_id: Optional[str]) -> None:
    """Set the session ID for the current thread tracing context."""
    _context.session_id = session_id

def get_session_id() -> Optional[str]:
    """Retrieve the session ID for the current thread tracing context."""
    return getattr(_context, "session_id", None)

@contextmanager
def trace_context(session_id: Optional[str]):
    """Context manager to trace a block of AI calls with a scoped session ID."""
    old_session_id = get_session_id()
    set_session_id(session_id)
    try:
        yield
    finally:
        set_session_id(old_session_id)
# Saved original methods to prevent infinite loops / multiple patches

_original_openai_create: Any = None
_original_anthropic_create: Any = None

@dataclass
class AICallEvent:
    """Represents a single AI API call captured by the instrumentor."""
    call_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    service: str = ""
    team: str = ""
    model: str = ""
    provider: str = ""
    model_version: str = ""
    latency_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    status: str = "success"
    error: Optional[str] = None
    finish_reason: str = "stop"
    prompt_hash: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        """Convert dataclass to standard telemetry dictionary."""
        return {
            "call_id": self.call_id,
            "service": self.service,
            "team": self.team,
            "model": self.model,
            "provider": self.provider,
            "model_version": self.model_version,
            "latency_ms": self.latency_ms,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_usd": self.cost_usd,
            "status": self.status,
            "error": self.error,
            "finish_reason": self.finish_reason,
            "prompt_hash": self.prompt_hash,
            "timestamp": self.timestamp,
            "sourcetype": "nw:ai_call"
        }

@dataclass
class PromptEvent:
    """Prompt text captured for injection analysis - stored separately."""
    call_id: str
    service: str
    team: str
    prompt_text: str  # truncated to 2000 chars
    session_id: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        """Convert prompt event to dictionary format."""
        return {
            "call_id": self.call_id,
            "service": self.service,
            "team": self.team,
            "prompt_text": self.prompt_text[:2000],
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "sourcetype": "nw:prompt"
        }

def _get_prompt_text(kwargs: dict, provider: str) -> str:
    """Extract prompt text from API call parameters based on provider style."""
    try:
        if provider == "openai":
            messages = kwargs.get("messages", [])
            if messages and isinstance(messages, list):
                # Join the contents of all messages
                prompt_parts = []
                for msg in messages:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    if isinstance(content, str):
                        prompt_parts.append(f"{role}: {content}")
                return "\n".join(prompt_parts)
        elif provider == "anthropic":
            messages = kwargs.get("messages", [])
            system = kwargs.get("system", "")
            prompt_parts = []
            if system:
                prompt_parts.append(f"system: {system}")
            if messages and isinstance(messages, list):
                for msg in messages:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    if isinstance(content, str):
                        prompt_parts.append(f"{role}: {content}")
                    elif isinstance(content, list):
                        # Extract text blocks
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                prompt_parts.append(f"{role}: {block.get('text', '')}")
            return "\n".join(prompt_parts)
    except Exception as e:
        logger.warning(f"[NeuralWatch] Error extracting prompt text: {e}")
    return ""

def _hash_prompt(prompt: str) -> str:
    """Compute truncated SHA256 of the prompt text for core tracking."""
    if not prompt:
        return ""
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]

def _wrap_openai_create(original_method: Any) -> Any:
    """Create a wrapper for openai.chat.completions.create."""
    def patched_create(*args, **kwargs):
        # 1. NeuralWatch Pre-Call Setup
        start_time = time.time()
        call_id = str(uuid.uuid4())
        model = kwargs.get("model", "unknown")
        
        prompt_text = ""
        prompt_hash = ""
        session_id = kwargs.pop("session_id", None)  # Extract custom session_id if supplied
        if session_id is None:
            session_id = get_session_id()


        try:
            # Extract prompt details
            prompt_text = _get_prompt_text(kwargs, "openai")
            prompt_hash = _hash_prompt(prompt_text)

            # Send prompt to injections index if enabled
            if _capture_prompts and prompt_text:
                pe = PromptEvent(
                    call_id=call_id,
                    service=_service,
                    team=_team,
                    prompt_text=prompt_text,
                    session_id=session_id
                )
                send_event("neuralwatch_injections", pe.to_dict())
        except Exception as e:
            logger.warning(f"[NeuralWatch] Pre-call instrumentation warning: {e}")

        # 2. Invoke Original API Call
        try:
            result = original_method(*args, **kwargs)
        except Exception as e:
            # Re-raise the user application's error, but log it to Splunk first
            try:
                latency = int((time.time() - start_time) * 1000)
                event = AICallEvent(
                    call_id=call_id,
                    service=_service,
                    team=_team,
                    model=model,
                    provider="openai",
                    latency_ms=latency,
                    status="error",
                    error=str(e),
                    finish_reason="error",
                    prompt_hash=prompt_hash
                )
                send_event("neuralwatch_ai_calls", event.to_dict())
            except Exception:
                pass
            raise e  # Enforce re-raise of parent application error

        # 3. NeuralWatch Post-Call Success Processing
        try:
            latency = int((time.time() - start_time) * 1000)
            
            # Extract usage and tokens
            input_tokens = 0
            output_tokens = 0
            model_version = ""
            finish_reason = "stop"

            if hasattr(result, "usage") and result.usage:
                input_tokens = getattr(result.usage, "prompt_tokens", 0)
                output_tokens = getattr(result.usage, "completion_tokens", 0)
            
            if hasattr(result, "model"):
                model_version = getattr(result, "model", "")

            if hasattr(result, "choices") and result.choices:
                first_choice = result.choices[0]
                if hasattr(first_choice, "finish_reason") and first_choice.finish_reason:
                    finish_reason = first_choice.finish_reason

            cost = estimate_cost(model, input_tokens, output_tokens)

            # Record success event
            event = AICallEvent(
                call_id=call_id,
                service=_service,
                team=_team,
                model=model,
                provider="openai",
                model_version=model_version,
                latency_ms=latency,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost,
                status="success",
                finish_reason=finish_reason,
                prompt_hash=prompt_hash
            )
            send_event("neuralwatch_ai_calls", event.to_dict())
        except Exception as e:
            logger.warning(f"[NeuralWatch] Post-call instrumentation warning: {e}")

        return result

    return patched_create

def _wrap_anthropic_create(original_method: Any) -> Any:
    """Create a wrapper for anthropic.messages.create."""
    def patched_create(*args, **kwargs):
        # 1. NeuralWatch Pre-Call Setup
        start_time = time.time()
        call_id = str(uuid.uuid4())
        model = kwargs.get("model", "unknown")
        
        prompt_text = ""
        prompt_hash = ""
        session_id = kwargs.pop("session_id", None)
        if session_id is None:
            session_id = get_session_id()


        try:
            prompt_text = _get_prompt_text(kwargs, "anthropic")
            prompt_hash = _hash_prompt(prompt_text)

            if _capture_prompts and prompt_text:
                pe = PromptEvent(
                    call_id=call_id,
                    service=_service,
                    team=_team,
                    prompt_text=prompt_text,
                    session_id=session_id
                )
                send_event("neuralwatch_injections", pe.to_dict())
        except Exception as e:
            logger.warning(f"[NeuralWatch] Pre-call instrumentation warning: {e}")

        # 2. Invoke Original API Call
        try:
            result = original_method(*args, **kwargs)
        except Exception as e:
            try:
                latency = int((time.time() - start_time) * 1000)
                event = AICallEvent(
                    call_id=call_id,
                    service=_service,
                    team=_team,
                    model=model,
                    provider="anthropic",
                    latency_ms=latency,
                    status="error",
                    error=str(e),
                    finish_reason="error",
                    prompt_hash=prompt_hash
                )
                send_event("neuralwatch_ai_calls", event.to_dict())
            except Exception:
                pass
            raise e

        # 3. NeuralWatch Post-Call Success Processing
        try:
            latency = int((time.time() - start_time) * 1000)
            
            input_tokens = 0
            output_tokens = 0
            model_version = getattr(result, "model", model)
            finish_reason = "end_turn"

            if hasattr(result, "usage") and result.usage:
                input_tokens = getattr(result.usage, "input_tokens", 0)
                output_tokens = getattr(result.usage, "output_tokens", 0)

            if hasattr(result, "stop_reason") and result.stop_reason:
                finish_reason = getattr(result, "stop_reason", "end_turn")

            cost = estimate_cost(model, input_tokens, output_tokens)

            event = AICallEvent(
                call_id=call_id,
                service=_service,
                team=_team,
                model=model,
                provider="anthropic",
                model_version=model_version,
                latency_ms=latency,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost,
                status="success",
                finish_reason=finish_reason,
                prompt_hash=prompt_hash
            )
            send_event("neuralwatch_ai_calls", event.to_dict())
        except Exception as e:
            logger.warning(f"[NeuralWatch] Post-call instrumentation warning: {e}")

        return result

    return patched_create

def instrument(
    service: str,
    team: str,
    splunk_hec_url: str,
    splunk_hec_token: str,
    capture_prompts: bool = True,
    verify_ssl: bool = False
) -> None:
    """
    Auto-patches OpenAI and Anthropic client SDK modules.
    Safe call: catches exceptions internally, logging warnings instead of crashing.
    """
    global _service, _team, _capture_prompts, _instrumented, _original_openai_create, _original_anthropic_create

    try:
        _service = service
        _team = team
        _capture_prompts = capture_prompts

        # Initialize global HTTP client forwarder parameters
        configure(splunk_hec_url, splunk_hec_token, verify_ssl)

        if _instrumented:
            logger.info("[NeuralWatch] SDK is already instrumented.")
            return

        # Monkey-patch OpenAI
        try:
            from openai.resources.chat.completions import Completions
            if Completions.create != _original_openai_create:
                _original_openai_create = Completions.create
                setattr(Completions, "create", _wrap_openai_create(_original_openai_create))
                logger.info("[NeuralWatch] OpenAI SDK successfully patched.")
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"[NeuralWatch] Failed to patch OpenAI client: {e}")

        # Monkey-patch Anthropic
        try:
            from anthropic.resources.messages import Messages
            if Messages.create != _original_anthropic_create:
                _original_anthropic_create = Messages.create
                setattr(Messages, "create", _wrap_anthropic_create(_original_anthropic_create))
                logger.info("[NeuralWatch] Anthropic SDK successfully patched.")
        except ImportError:
            pass
        except Exception as e:
            logger.warning(f"[NeuralWatch] Failed to patch Anthropic client: {e}")

        _instrumented = True
        logger.info("[NeuralWatch] SDK auto-patching completed.")

    except Exception as e:
        logger.warning(f"[NeuralWatch] Instrumentation framework error: {e}")

def auto_instrument() -> None:
    """
    Reads configuration from .neuralwatch/config.json in the project directory
    and runs instrument() with the saved HEC values.
    """
    try:
        config_path = os.path.join(os.getcwd(), ".neuralwatch", "config.json")
        if not os.path.exists(config_path):
            logger.warning(
                f"[NeuralWatch] Auto-instrumentation skipped. Config file not found at {config_path}. Run 'neuralwatch init' first."
            )
            return

        with open(config_path, "r") as f:
            config = json.load(f)

        instrument(
            service=config.get("service", "unknown-service"),
            team=config.get("team", "unknown-team"),
            splunk_hec_url=config.get("splunk_hec_url", ""),
            splunk_hec_token=config.get("splunk_hec_token", ""),
            capture_prompts=config.get("capture_prompts", True),
            verify_ssl=config.get("verify_ssl", False)
        )
    except Exception as e:
        logger.warning(f"[NeuralWatch] Auto-instrumentation failed: {e}")
