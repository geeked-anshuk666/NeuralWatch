"""
Demo: dummy_app.py
Purpose: Demonstrates integration of NeuralWatch SDK with a real OpenAI client.
         This serves as the template for developers integrating the SDK.
"""

import os
import sys
from dotenv import load_dotenv

# Ensure local import is prioritized if not installed via pip
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Load HEC URLs and tokens from environmental config
load_dotenv(override=True)

# 1. Import the actual OpenAI client and the NeuralWatch SDK
import openai
from neuralwatch_sdk import instrument, set_session_id

# 2. Setup environment settings
api_key = os.getenv("OPENAI_API_KEY", "mock-key-if-not-testing-live")
hec_url = os.getenv("SPLUNK_HEC_URL", "https://localhost:8088/services/collector/event")
hec_token = os.getenv("SPLUNK_HEC_TOKEN")

print("=========================================================")
print("          NEURALWATCH SDK — DUMMY AI APP DEMO")
print("=========================================================")

if not hec_token:
    print("[Error] SPLUNK_HEC_TOKEN not found in .env. Run 'neuralwatch init' or configure it.")
    sys.exit(1)

# 3. Initialize the NeuralWatch SDK (Only 1 call needed at app startup!)
print(f"[*] Initializing NeuralWatch for service: 'customer-support-agent'...")
instrument(
    service="customer-support-agent",
    team="support-eng",
    splunk_hec_url=hec_url,
    splunk_hec_token=hec_token,
    capture_prompts=True,
    verify_ssl=False
)

# Set the session ID context dynamically (type-safe tracing)
set_session_id("session-user-12345")

# 4. Instantiate and run standard OpenAI calls
client = openai.OpenAI(api_key=api_key)

print("\n[*] Sending request to OpenAI (SDK will intercept and send telemetry)...")
try:
    # If the user has a real key, this runs. Otherwise, it will fail but demonstrate the capture logic.
    if api_key == "mock-key-if-not-testing-live":
        print("[Notice] Using mock API key. Set 'OPENAI_API_KEY' in your .env to execute a real request.")
        
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a helpful customer support agent."},
            {"role": "user", "content": "How do I return my order?"}
        ]
    )

    print("\n[+] Response received successfully!")
    print(f"Response: {response.choices[0].message.content}")
except Exception as e:
    print(f"\n[!] Call failed as expected or due to missing credentials: {e}")
    print("[*] NeuralWatch has logged the failure details (error class, status, latency) to Splunk.")

print("\nCheck the 'NeuralWatch — AI Fleet Observatory' dashboard under 'customer-support-agent' to see the metrics!")
print("=========================================================")
