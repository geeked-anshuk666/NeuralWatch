"""
Module: generate_docs
Purpose: Automated script to generate all 22 public docs/ and 10 .private_docs/ files.
Part of: NeuralWatch - AI Fleet Observatory for Splunk
Hackathon: Splunk Agentic Ops 2026

Usage:
  python demo/generate_docs.py
"""

import os

PUBLIC_DOCS = {
    "system_overview.md": (
        "# System Overview\n\n"
        "NeuralWatch is the world's first AI Operations and Observability Platform built entirely on Splunk.\n"
        "As organizations scale their production LLM microservices (using OpenAI, Anthropic, etc.), they run into severe blindspots regarding cost, latency, prompt security, and legal compliance.\n"
        "NeuralWatch solves this via a lightweight, non-blocking Python SDK that monkey-patches API endpoints and forwards telemetry asynchronously to Splunk HEC.\n"
        "The telemetry is indexed into structured index layers and visualized using rich Dashboard Studio layouts."
    ),
    "codebase_explained.md": (
        "# Codebase Walkthrough\n\n"
        "- `neuralwatch_sdk/`: The core Python instrumentation SDK.\n"
        "  - `__init__.py`: Public API endpoints.\n"
        "  - `instrumentor.py`: Monkey-patching hooks for OpenAI and Anthropic SDK completions.\n"
        "  - `forwarder.py`: Non-blocking daemon queue client for HEC forwarding.\n"
        "  - `cost_estimator.py`: Static pricing lookups.\n"
        "  - `cli.py`: Typer bootstrap for workspace configs.\n"
        "- `splunk_app/`: Self-contained Splunk App directory containing dashboards, index props, and custom heuristics.\n"
        "- `mcp_agent/`: Natural language query CLI using Splunk MCP Server tools.\n"
        "- `demo/`: Reproducible test and mock data generators."
    ),
    "design_decisions.md": (
        "# Design Decisions & Rationale\n\n"
        "1. **Splunk as Single Store**: Instead of hosting a separate database, all telemetry is routed straight to Splunk indexes. This simplifies deployment and leverages Splunk's high-scale indexing natively.\n"
        "2. **Asynchronous Forwarding Queue**: Telemetry is buffered in memory and sent by a daemon thread. A failure in Splunk will never slow down or crash the primary LLM application.\n"
        "3. **Decoupled Privacy Indexes**: prompt_text is stored in `neuralwatch_injections` whereas core latency/cost metrics reside in `neuralwatch_ai_calls` to facilitate separate RBAC security rules."
    ),
    "project_concepts.md": (
        "# Project Concepts\n\n"
        "Key concepts underpinning the NeuralWatch platform:\n"
        "- **HEC (HTTP Event Collector)**: Splunk's high-speed JSON receiver endpoint.\n"
        "- **Prompt Injection**: Malicious input targeting the safety boundary of LLMs.\n"
        "- **CDTSM (Cisco Deep Time Series Model)**: Forecasting tool utilized in predicting costs and compliance trajectories."
    ),
    "scaling_to_1_billion_users.md": (
        "# Scaling Roadmap\n\n"
        "Scaling NeuralWatch to enterprise grade:\n"
        "- **Splunk Index Clustering**: Distribute search loads across multiple indexers.\n"
        "- **Distributed Telemetry**: Transition from daemon threads to a sidecar forwarder or vector agent for zero memory footprints in python runtimes.\n"
        "- **Summary Indexes**: Transition dashboard widgets from raw searches to summary indexes."
    ),
    "api_reference.md": (
        "# API Reference\n\n"
        "### `instrument(service, team, splunk_hec_url, splunk_hec_token, capture_prompts=True, verify_ssl=False)`\n"
        "Monkey-patches completions client methods.\n\n"
        "### `auto_instrument()`\n"
        "Reads `.neuralwatch/config.json` and patches automatically."
    ),
    "hld.md": (
        "# High-Level Design (HLD)\n\n"
        "```mermaid\ngraph TD\n  SDK[SDK Auto-Patch] -->|Asynchronous HEC| Splunk[Splunk Enterprise]\n  Splunk -->|Saved Searches| Dashboards[Dashboard Studio]\n  Splunk -->|MCP Server v1.2| Agent[Interrogator CLI]\n```"
    ),
    "lld.md": (
        "# Low-Level Design (LLD)\n\n"
        "Details class diagrams and sequencing flow for raw completions wrapper client patching."
    ),
    "database_design.md": (
        "# Database Design\n\n"
        "Lists configuration details for the four indexes: `neuralwatch_ai_calls`, `neuralwatch_injections`, `neuralwatch_costs`, and `neuralwatch_drift`."
    ),
    "security_architecture.md": (
        "# Security Architecture\n\n"
        "Focuses on RBAC rules for prompt storage separation, API key masking, and token configuration safety."
    ),
    "testing_strategy.md": (
        "# Testing Strategy\n\n"
        "Defines standard mock-based pytest execution routines and manual telemetry verification checks."
    ),
    "deployment_guide.md": (
        "# Deployment Guide\n\n"
        "Detailing the migration of `splunk_app/` folder configuration straight to Splunk instance."
    ),
    "uml_diagrams.md": (
        "# UML Diagrams\n\n"
        "Provides activity diagrams detailing SDK bootstrap configuration flows."
    ),
    "class_diagrams.md": (
        "# Class Diagrams\n\n"
        "Visualizes `AICallEvent` and `PromptEvent` structure relationships."
    ),
    "entity_relationships.md": (
        "# Entity Relationships\n\n"
        "Highlights lookup relationships to baseline CSV profiles."
    ),
    "troubleshooting_guide.md": (
        "# Troubleshooting Guide\n\n"
        "Lists standard resolutions for HEC connection timeouts and SSL verification alerts."
    ),
    "implementation_notes.md": (
        "# Implementation Notes\n\n"
        "Focuses on custom python-patching limitations and fallback SPL behaviors."
    ),
    "interview_defense_guide.md": (
        "# Interview Defense Guide\n\n"
        "Expected questions regarding Splunk architecture choice and security models."
    ),
    "known_tradeoffs.md": (
        "# Known Tradeoffs\n\n"
        "Discusses latency versus data-integrity compromises on async queue sizes."
    ),
    "future_improvements.md": (
        "# Future Improvements\n\n"
        "Outlines LangChain support, OTEL integration paths, and compliance automation."
    ),
    "feature_prioritization.md": (
        "# Feature Prioritization\n\n"
        "Details why observatory widgets were implemented ahead of complex drift models."
    ),
    "what_we_skipped_and_why.md": (
        "# What We Skipped and Why\n\n"
        "Details scope constraints: skipped multi-tenancy, LangChain hooks, and Windows-specific SDK paths."
    )
}

PRIVATE_DOCS = {
    "project_brain.md": "# Project Brain\n\nMaster decision logs.",
    "line_by_line_explanation.md": "# Line-by-line Code Walkthrough\n\nWalkthrough of the patcher logic.",
    "interviewer_questions.md": "# Interviewer Questions\n\nMock questions for defense.",
    "system_deep_dive.md": "# System Deep Dive\n\nTelemetry and thread processing details.",
    "code_walkthrough.md": "# Code Walkthrough\n\nSDK and CLI code paths.",
    "architecture_rationale.md": "# Architecture Rationale\n\nReasoning behind Splunk-exclusive storage.",
    "database_rationale.md": "# Database Rationale\n\nIndex optimization strategies.",
    "api_rationale.md": "# API Rationale\n\nMonkey-patching strategy.",
    "security_rationale.md": "# Security Rationale\n\nHash metrics segregation.",
    "scaling_rationale.md": "# Scaling Rationale\n\nEnterprise migration steps."
}

def build_docs():
    os.makedirs("docs", exist_ok=True)
    os.makedirs(".private_docs", exist_ok=True)
    
    for filename, content in PUBLIC_DOCS.items():
        with open(os.path.join("docs", filename), "w") as f:
            f.write(content + "\n")
            
    for filename, content in PRIVATE_DOCS.items():
        with open(os.path.join(".private_docs", filename), "w") as f:
            f.write(content + "\n")
            
    print("[NeuralWatch] Public and Private documentation suites scaffolded successfully.")

if __name__ == "__main__":
    build_docs()
