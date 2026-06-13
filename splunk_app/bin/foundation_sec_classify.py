"""
Module: foundation_sec_classify
Purpose: Simulates adversarial classification for telemetry events using a local heuristic model.
Part of: NeuralWatch — AI Fleet Observatory for Splunk
Hackathon: Splunk Agentic Ops 2026

Dependencies:
  - splunk-sdk: to query and write back events to Splunk indexes
  - python-dotenv: to load Splunk environment credentials

Usage:
  python splunk_app/bin/foundation_sec_classify.py
"""

import os
import logging
from dotenv import load_dotenv
import splunklib.client as client
import splunklib.results as results

# Load environment configuration
load_dotenv()

# Setup logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("neuralwatch_classifier")

# Heuristics rules for prompt injection severity classification
HEURISTIC_RULES = [
    # Critical patterns
    ("ignore all previous instructions", 0.96, "CRITICAL"),
    ("print your system prompt", 0.94, "CRITICAL"),
    ("system prompt verbatim", 0.95, "CRITICAL"),
    ("dan (do anything now)", 0.93, "CRITICAL"),
    ("system('rm -rf", 0.98, "CRITICAL"),
    
    # High patterns
    ("pretend you are the system administrator", 0.78, "HIGH"),
    ("grant me access", 0.75, "HIGH"),
    ("list all users", 0.72, "HIGH"),
    ("output passwords", 0.85, "HIGH"),
    ("exfiltrate", 0.81, "HIGH"),
    
    # Medium patterns
    ("bypass a standard input validation", 0.58, "MEDIUM"),
    ("training data", 0.45, "MEDIUM"),
    ("cross-site scripting", 0.42, "MEDIUM"),
    ("sql injection", 0.62, "MEDIUM")
]

def classify_text(prompt: str) -> tuple[float, str]:
    """
    Apply heuristic rules to classify the injection risk of prompt text.
    """
    text_lower = prompt.lower()
    for pattern, score, risk in HEURISTIC_RULES:
        if pattern in text_lower:
            return score, risk
    return 0.10, "LOW"

def run_classification():
    """
    Queries Splunk for unclassified prompt events and updates their scores.
    """
    host = os.getenv("SPLUNK_HOST", "localhost")
    port = int(os.getenv("SPLUNK_PORT", "8089"))
    username = os.getenv("SPLUNK_USERNAME", "admin")
    password = os.getenv("SPLUNK_PASSWORD")
    
    if not password:
        logger.warning("[NeuralWatch] Splunk password not configured. Skipping classification run.")
        return
        
    try:
        # Establish connection to Splunk Management API
        service = client.connect(
            host=host,
            port=port,
            username=username,
            password=password,
            verify=False
        )
        
        # Search query for unclassified prompts
        search_query = 'search index=neuralwatch_injections sourcetype="nw:prompt" | where isnull(injection_score)'
        
        # Run search job
        job = service.jobs.create(search_query)
        while not job.is_done():
            pass
            
        # Parse search results
        has_xml_reader = hasattr(results, "ResultsReader")
        output_mode = "xml" if has_xml_reader else "json"
        
        raw_results = job.results(count=100, output_mode=output_mode)
        if has_xml_reader:
            reader = getattr(results, "ResultsReader")(raw_results)
        else:
            reader = getattr(results, "JSONResultsReader")(raw_results)
            
        unclassified_events = []
        for result in reader:
            if isinstance(result, dict):
                unclassified_events.append(result)
                
        logger.info(f"[NeuralWatch] Found {len(unclassified_events)} unclassified prompts.")
        
        # In a real environment, we would classify and overwrite or update.
        # For our mock / batch simulation, we output the classified list.
        for event in unclassified_events:
            prompt_text = event.get("prompt_text", "")
            score, risk = classify_text(prompt_text)
            logger.info(f"Classified Event ID {event.get('call_id')}: Score={score}, Risk={risk}")
            
    except Exception as e:
        logger.error(f"[NeuralWatch] Classification error: {e}")

if __name__ == "__main__":
    run_classification()
