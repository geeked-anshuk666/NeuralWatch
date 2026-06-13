#!/bin/bash
# Script: splunk_setup.sh
# Purpose: Create indexes and configure Splunk HTTP Event Collector (HEC)
# Part of: NeuralWatch — AI Fleet Observatory for Splunk
# Hackathon: Splunk Agentic Ops 2026

# Load environment variables
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

SPLUNK_BIN=${SPLUNK_HOME:-/opt/splunk}/bin/splunk
SPLUNK_USER=${SPLUNK_USERNAME:-admin}
SPLUNK_PASS=${SPLUNK_PASSWORD:-changeme}

echo "[NeuralWatch] Initializing Splunk Indexes..."

# Create indexes
$SPLUNK_BIN add index neuralwatch_ai_calls -maxDataSize 5000 -frozenTimePeriodInSecs 7776000 -auth "$SPLUNK_USER:$SPLUNK_PASS"
$SPLUNK_BIN add index neuralwatch_injections -maxDataSize 2000 -frozenTimePeriodInSecs 2592000 -auth "$SPLUNK_USER:$SPLUNK_PASS"
$SPLUNK_BIN add index neuralwatch_costs -maxDataSize 1000 -frozenTimePeriodInSecs 31536000 -auth "$SPLUNK_USER:$SPLUNK_PASS"
$SPLUNK_BIN add index neuralwatch_drift -maxDataSize 1000 -frozenTimePeriodInSecs 2592000 -auth "$SPLUNK_USER:$SPLUNK_PASS"

echo "[NeuralWatch] Indexes created successfully."
