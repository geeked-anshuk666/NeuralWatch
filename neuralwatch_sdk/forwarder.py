"""
Module: forwarder
Purpose: Asynchronous, non-blocking Splunk HTTP Event Collector (HEC) telemetry forwarder.
Part of: NeuralWatch - AI Fleet Observatory for Splunk
Hackathon: Splunk Agentic Ops 2026

Dependencies:
  - requests: for sending HTTP payloads to Splunk HEC
  - queue, threading: for safe background async processing

Usage:
  from neuralwatch_sdk.forwarder import configure, send_event
  configure("https://localhost:8088/services/collector/event", "token-123", verify_ssl=False)
  send_event("neuralwatch_ai_calls", {"model": "gpt-4o", "latency_ms": 150})
"""

import queue
import threading
import time
import logging
import requests
import urllib3
from typing import Optional

# Setup library logger
logger = logging.getLogger("neuralwatch")

# Thread-safe in-memory queue for events
_event_queue: queue.Queue = queue.Queue(maxsize=10000)

# Global variables for HEC config
_hec_url: Optional[str] = None
_hec_token: Optional[str] = None
_verify_ssl: bool = False
_worker_thread: Optional[threading.Thread] = None
_queue_lock = threading.Lock()

# Retries configuration
RETRY_DELAYS = [1, 2, 4]  # seconds

def configure(hec_url: str, hec_token: str, verify_ssl: bool = False) -> None:
    """
    Configure the HEC connection parameters and initialize the background worker thread.

    Args:
        hec_url: The full HEC REST collector URL
        hec_token: Splunk HEC authentication token
        verify_ssl: Set to True to validate SSL certs (default: False for local setups)
    """
    global _hec_url, _hec_token, _verify_ssl, _worker_thread

    try:
        _hec_url = hec_url
        _hec_token = hec_token
        _verify_ssl = verify_ssl

        # Disable SSL warnings if validation is turned off
        if not verify_ssl:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        # Start the background daemon thread if not already running
        with _queue_lock:
            if _worker_thread is None or not _worker_thread.is_alive():
                _worker_thread = threading.Thread(target=_worker_loop, daemon=True)
                _worker_thread.start()
                logger.info("[NeuralWatch] Background forwarder worker thread started.")
    except Exception as e:
        logger.warning(f"[NeuralWatch] Failed to configure forwarder: {e}")

def send_event(index: str, event_dict: dict) -> bool:
    """
    Enqueue an event to be sent asynchronously to Splunk HEC.
    This call is non-blocking and will never raise an exception.

    Args:
        index: Target Splunk index
        event_dict: JSON-serializable event payload

    Returns:
        bool: True if successfully enqueued, False otherwise.
    """
    try:
        if not _hec_url or not _hec_token:
            logger.warning("[NeuralWatch] HEC forwarder is not configured. Drop event.")
            return False
        
        # Enqueue event without blocking the caller
        _event_queue.put_nowait((index, event_dict))
        return True
    except queue.Full:
        logger.warning("[NeuralWatch] Telemetry queue is full. Event dropped.")
        return False
    except Exception as e:
        logger.warning(f"[NeuralWatch] Error enqueuing event: {e}")
        return False

def _send_hec_request(index: str, event_dict: dict) -> bool:
    """
    Send an event to the Splunk HTTP Event Collector with retries and exponential backoff.
    """
    if not _hec_url or not _hec_token:
        return False

    headers = {
        "Authorization": f"Splunk {_hec_token}",
        "Content-Type": "application/json"
    }

    # Prepare standard HEC event wrap
    payload = {
        "time": event_dict.get("timestamp", time.time()),
        "host": event_dict.get("service", "unknown-service"),
        "source": "neuralwatch_sdk",
        "sourcetype": event_dict.get("sourcetype", "nw:ai_call"),
        "index": index,
        "event": event_dict
    }

    # Remove extra timestamp or sourcetype from event payload if not needed in properties
    payload["event"].pop("timestamp", None)
    payload["event"].pop("sourcetype", None)

    for i, delay in enumerate(RETRY_DELAYS):
        try:
            response = requests.post(
                _hec_url,
                json=payload,
                headers=headers,
                timeout=5.0,
                verify=_verify_ssl
            )
            if response.status_code == 200:
                return True
            else:
                logger.warning(
                    f"[NeuralWatch] HEC responded with status {response.status_code}: {response.text}"
                )
        except requests.exceptions.RequestException as e:
            logger.warning(f"[NeuralWatch] HEC connection attempt {i+1}/3 failed: {e}")
        
        # Wait before retrying
        time.sleep(delay)

    logger.warning("[NeuralWatch] HEC forwarding failed after 3 attempts. Event dropped silently.")
    return False

def _worker_loop() -> None:
    """
    Infinite background loop that runs on a daemon thread, draining the queue
    and forwarding events to Splunk.
    """
    while True:
        try:
            # Block until an item is available in the queue
            index, event_dict = _event_queue.get()
            try:
                _send_hec_request(index, event_dict)
            finally:
                _event_queue.task_done()
        except Exception as e:
            # Prevent worker thread crash
            logger.error(f"[NeuralWatch] Unexpected error in worker loop: {e}")
            time.sleep(1.0)

def flush(timeout: float = 5.0) -> None:
    """
    Block and drain the telemetry event queue on exit up to the timeout duration.
    """
    if _event_queue.empty():
        return
    logger.info(f"[NeuralWatch] Draining telemetry queue ({_event_queue.qsize()} events)...")
    start = time.time()
    while not _event_queue.empty():
        if time.time() - start > timeout:
            logger.warning("[NeuralWatch] Flush timed out. Remaining events dropped.")
            break
        time.sleep(0.1)

# Auto-register clean shutdown hook
import atexit
atexit.register(flush)

