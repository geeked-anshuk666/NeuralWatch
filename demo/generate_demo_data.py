"""
Module: generate_demo_data
Purpose: Generates and populates 7 days of reproducible synthetic AI telemetry events into Splunk HEC.
Part of: NeuralWatch — AI Fleet Observatory for Splunk
Hackathon: Splunk Agentic Ops 2026

Dependencies:
  - requests: for sending HTTP payloads in batches to Splunk HEC
  - python-dotenv: to load Splunk environment config
  - random: for deterministic data generation using seed 42

Usage:
  python demo/generate_demo_data.py
"""

import os
import sys
import json
import time
import uuid
import random
import hashlib
import requests
from typing import Dict, Any, List
from dotenv import load_dotenv

# Set random seed for reproducibility (Rule 12)
random.seed(42)

# Load environment configs
load_dotenv(override=True)

SPLUNK_HEC_URL = os.getenv("SPLUNK_HEC_URL", "https://localhost:8088/services/collector/event")
SPLUNK_HEC_TOKEN = os.getenv("SPLUNK_HEC_TOKEN", "your_splunk_hec_token_here")
SSL_VERIFY = os.getenv("NEURALWATCH_SSL_VERIFY", "false").lower() == "true"

if not SSL_VERIFY:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Schema definitions
MODELS = ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022", "claude-3-opus-20240229", "claude-sonnet-4-6"]
PROVIDERS = {
    "gpt-4o": "openai",
    "gpt-4o-mini": "openai",
    "gpt-4-turbo": "openai",
    "claude-3-5-sonnet-20241022": "anthropic",
    "claude-3-5-haiku-20241022": "anthropic",
    "claude-3-opus-20240229": "anthropic",
    "claude-sonnet-4-6": "anthropic"
}

TEAMS = ["payments-eng", "security-ops", "search-team", "recommendations-dev", "core-infra"]
SERVICES = ["checkout-service", "auth-service", "fraud-detection-svc", "product-svc", "email-svc"]
FINISH_REASONS = ["stop", "stop", "stop", "stop", "length", "content_filter"]

# Per-model pricing for calculation
COST_TABLE = {
    "gpt-4o": (0.005, 0.015),
    "gpt-4o-mini": (0.00015, 0.0006),
    "gpt-4-turbo": (0.01, 0.03),
    "claude-3-5-sonnet-20241022": (0.003, 0.015),
    "claude-3-5-haiku-20241022": (0.0008, 0.004),
    "claude-3-opus-20240229": (0.015, 0.075),
    "claude-sonnet-4-6": (0.003, 0.015)
}

def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    in_c, out_c = COST_TABLE.get(model, (0.01, 0.03))
    return round((input_tokens / 1000.0 * in_c) + (output_tokens / 1000.0 * out_c), 6)

def generate_events() -> List[Dict[str, Any]]:
    """
    Generate exactly 7 days of telemetry data ending at the current time.
    Target: 84,000+ events (approx 500 events per hour × 24h × 7d).
    """
    events: List[Dict[str, Any]] = []
    end_time = time.time()
    start_time = end_time - (7 * 24 * 3600)  # 7 days ago
    
    # 7 days * 24 hours = 168 hourly intervals
    total_hours = 168
    events_per_hour = 505  # 505 * 168 = 84,840 events
    
    print(f"[NeuralWatch] Generating synthetic AI telemetry dataset ({total_hours * events_per_hour} events)...")
    
    for hour in range(total_hours):
        hour_start = start_time + (hour * 3600)
        
        for i in range(events_per_hour):
            event_time = hour_start + random.randint(0, 3599)
            call_id = str(uuid.uuid4())
            model = random.choice(MODELS)
            provider = PROVIDERS[model]
            team = random.choice(TEAMS)
            service = random.choice(SERVICES)
            
            # Base distribution for tokens
            input_tokens = int(random.lognormvariate(6.2, 0.6))
            output_tokens = int(random.lognormvariate(5.5, 0.5))
            
            # Bound tokens logically
            input_tokens = max(10, min(8000, input_tokens))
            output_tokens = max(5, min(4000, output_tokens))
            
            # Latency (ms) modeled around provider speed and output tokens
            base_latency = 150 if provider == "openai" else 300
            latency = int(base_latency + (output_tokens * random.uniform(2.0, 5.0)))
            
            # Error distribution (3% error rate)
            is_error = random.random() < 0.03
            status = "error" if is_error else "success"
            err_msg = random.choice(["Rate limit exceeded", "API Timeout", "Service Unavailable", "Context Length Exceeded"]) if is_error else None
            finish_reason = "error" if is_error else random.choice(FINISH_REASONS)
            
            cost = calculate_cost(model, input_tokens, output_tokens) if not is_error else 0.0
            prompt_hash = hashlib.sha256(f"prompt-data-{hour}-{i}".encode()).hexdigest()[:16]
            
            # Standard HEC wrap format
            hec_event = {
                "time": event_time,
                "host": service,
                "source": "neuralwatch_sdk",
                "sourcetype": "nw:ai_call",
                "index": "neuralwatch_ai_calls",
                "event": {
                    "call_id": call_id,
                    "service": service,
                    "team": team,
                    "model": model,
                    "provider": provider,
                    "model_version": f"{model}-v1",
                    "latency_ms": latency,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "cost_usd": cost,
                    "status": status,
                    "error": err_msg,
                    "finish_reason": finish_reason,
                    "prompt_hash": prompt_hash
                }
            }
            events.append(hec_event)
            
    # Sort events by time to ensure chronological indexing order
    events.sort(key=lambda x: float(x["time"]))
    return events

def post_batches(events: List[Dict[str, Any]]):
    """Send HEC events in batches of 1000 for high efficiency."""
    headers = {"Authorization": f"Splunk {SPLUNK_HEC_TOKEN}"}
    batch_size = 10000
    total = len(events)
    sent_count = 0
    
    print(f"[NeuralWatch] Forwarding events in batches to Splunk HEC: {SPLUNK_HEC_URL}...")
    
    for i in range(0, total, batch_size):
        batch = events[i:i+batch_size]
        # HEC accepts newline-separated JSON payloads
        payload = "\n".join(json.dumps(event) for event in batch)
        
        try:
            response = requests.post(
                SPLUNK_HEC_URL,
                data=payload,
                headers=headers,
                timeout=15.0,
                verify=SSL_VERIFY
            )
            if response.status_code == 200:
                sent_count += len(batch)
                sys.stdout.write(f"\rProgress: {sent_count}/{total} events ingested successfully.")
                sys.stdout.flush()
            else:
                print(f"\n[NeuralWatch] Failed batch index {i}: status code {response.status_code} - {response.text}")
        except Exception as e:
            print(f"\n[NeuralWatch] Ingestion batch error: {e}")
            break
            
    print(f"\n[NeuralWatch] Ingestion complete. Total ingested: {sent_count} events.")

if __name__ == "__main__":
    start = time.time()
    events = generate_events()
    print(f"Generated {len(events)} events in {time.time() - start:.2f} seconds.")
    post_batches(events)
