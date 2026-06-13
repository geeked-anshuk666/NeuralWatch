"""
Module: splunk_setup
Purpose: Programmatically creates required NeuralWatch indexes in Splunk via REST API.
Part of: NeuralWatch — AI Fleet Observatory for Splunk
Hackathon: Splunk Agentic Ops 2026

Dependencies:
  - splunk-sdk: to connect and query
  - python-dotenv: to load environment configuration
"""

import os
import urllib3
from dotenv import load_dotenv
import splunklib.client as client

# Disable SSL warning for local self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

load_dotenv(override=True)

def create_indexes():
    host = os.getenv("SPLUNK_HOST", "localhost")
    port = int(os.getenv("SPLUNK_PORT", "8089"))
    username = os.getenv("SPLUNK_USERNAME", "admin")
    password = os.getenv("SPLUNK_PASSWORD")

    if not password or password == "your_splunk_password_here":
        print("[NeuralWatch] Error: SPLUNK_PASSWORD is not configured in your .env file.")
        print("Please open the .env file in your root folder and set the correct credentials.")
        return

    print(f"[NeuralWatch] Connecting to Splunk Management API at https://{host}:{port} as user '{username}'...")
    try:
        service = client.connect(
            host=host,
            port=port,
            username=username,
            password=password,
            verify=False
        )
    except Exception as e:
        print(f"[NeuralWatch] Connection failed: {e}")
        print("Please verify that your Splunk instance is running and port 8089 is open.")
        return

    indexes_to_create = {
        "neuralwatch_ai_calls": {"maxTotalDataSizeMB": 5000, "frozenTimePeriodInSecs": 7776000},
        "neuralwatch_injections": {"maxTotalDataSizeMB": 2000, "frozenTimePeriodInSecs": 2592000},
        "neuralwatch_costs": {"maxTotalDataSizeMB": 1000, "frozenTimePeriodInSecs": 31536000},
        "neuralwatch_drift": {"maxTotalDataSizeMB": 1000, "frozenTimePeriodInSecs": 2592000}
    }

    print("[NeuralWatch] Index initialization started...")
    for name, params in indexes_to_create.items():
        try:
            if name not in service.indexes:
                print(f"  → Creating index: '{name}'...")
                service.indexes.create(name, **params)
                print(f"  ✔ Index '{name}' created successfully.")
            else:
                print(f"  ✔ Index '{name}' already exists.")
        except Exception as e:
            print(f"  ❌ Failed to verify/create index '{name}': {e}")

    print("[NeuralWatch] Index setup task complete.")

if __name__ == "__main__":
    create_indexes()
