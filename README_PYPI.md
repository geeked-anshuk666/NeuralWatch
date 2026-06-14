# NeuralWatch - AI Fleet Observatory for Splunk

> **Real-time observability, security, and EU AI Act compliance for enterprise AI systems.**

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue?logo=python&logoColor=white)](https://python.org)
[![Splunk](https://img.shields.io/badge/Splunk-Enterprise-green?logo=splunk&logoColor=white)](https://splunk.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![OpenAI](https://img.shields.io/badge/OpenAI-Compatible-412991?logo=openai&logoColor=white)](https://openai.com)
[![Anthropic](https://img.shields.io/badge/Anthropic-Compatible-orange)](https://anthropic.com)

---

NeuralWatch is a zero-code-change AI observability platform that gives engineering and compliance teams complete visibility into their AI systems. By instrumenting the OpenAI and Anthropic Python SDKs at the library level, NeuralWatch automatically captures every LLM API call - its cost, latency, model, team attribution, and prompt content - and streams structured telemetry to Splunk in real time. No custom logging. No code changes beyond a single `instrument()` call.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Module Breakdown](#module-breakdown)
  - [Module A - Prompt Injection Sentinel](#module-a--prompt-injection-sentinel)
  - [Module B - NLP Query Agent (MCP)](#module-b--nlp-query-agent-mcp)
  - [Module C - AI Fleet Observatory](#module-c--ai-fleet-observatory)
  - [Module D - EU AI Act Compliance](#module-d--eu-ai-act-compliance)
- [Data Flow Diagram](#data-flow-diagram)
- [Repository Structure](#repository-structure)
- [Quick Start](#quick-start)
  - [Prerequisites](#prerequisites)
  - [1. Install the SDK](#1-install-the-sdk)
  - [2. Initialize NeuralWatch](#2-initialize-neuralwatch)
  - [3. Instrument Your Application](#3-instrument-your-application)
  - [4. Install the Splunk App](#4-install-the-splunk-app)
  - [5. Run the Live Simulator](#5-run-the-live-simulator)
- [SDK Reference](#sdk-reference)
  - [instrument()](#instrument)
  - [set_session_id() and trace_context()](#set_session_id-and-trace_context)
  - [auto_instrument()](#auto_instrument)
  - [CLI Commands](#cli-commands)
- [Splunk App Dashboards](#splunk-app-dashboards)
- [Security Design](#security-design)
- [EU AI Act Compliance Scoring](#eu-ai-act-compliance-scoring)
- [MCP Agent - Natural Language Querying](#mcp-agent--natural-language-querying)
- [Configuration Reference](#configuration-reference)
- [Development](#development)
- [License](#license)

---

## Architecture Overview

```
Your Application (client = openai.OpenAI(...))
      │
      ▼ (SDK Intercepts Every Call)
neuralwatch_sdk
 ├── instrumentor.py   (Monkey-patches API Clients)
 ├── cost_estimator.py (Calculates Token Cost in USD)
 └── forwarder.py      (Enqueues Async Telemetry Payload)
      │
      ▼ (HTTPS HEC Endpoint Request)
Splunk Enterprise
 ├── HEC Event Collector Endpoint
 ├── neuralwatch_ai_calls  index (nw:ai_call logs)
 ├── neuralwatch_injections index (nw:prompt logs)
 └── Dashboards & MCP NL-to-SPL Agent Query Bridge
```

---

## Module Breakdown

### Module A - Prompt Injection Sentinel

The Prompt Injection Sentinel captures every prompt sent through the instrumented LLM clients and classifies it for adversarial content using a heuristic classification engine inspired by the Foundation-Sec model architecture.

**How it works:**

```
User Prompt ──► SDK Interception ──► Heuristic Classifier (foundation_sec_classify.py)
                                           │
                                  Assign Risk Level
                     [LOW (0.05-0.20) / MEDIUM / HIGH / CRITICAL (0.93-0.98)]
                                           │
                                           ▼
                                 neuralwatch_injections Index
                                           ▼
                                 Splunk Security Sentinel Dashboard
```

**Detected threat categories:**

| Risk Level | Score Range | Example Patterns |
|---|---|---|
| `CRITICAL` | 0.93 – 0.98 | `ignore all previous instructions`, `print system prompt verbatim`, `DAN mode` |
| `HIGH` | 0.72 – 0.85 | `grant me access`, `output passwords`, `exfiltrate` |
| `MEDIUM` | 0.42 – 0.62 | `bypass input validation`, `sql injection`, `cross-site scripting` |
| `LOW` | 0.05 – 0.20 | Benign requests |

**Session Persistence Detection:** The Sentinel tracks `session_id` across multiple events. Services receiving more than 5 `HIGH`/`CRITICAL` events from the same session trigger elevated Art. 9 risk scoring.

---

### Module B - NLP Query Agent (MCP)

The NeuralWatch MCP Agent provides natural language query access to all telemetry data in Splunk. It translates English questions into SPL, executes them through the Splunk Management API, and synthesizes a human-readable answer using an LLM.

```
User Question ("How much did we spend today?")
      │
      ▼
spl_generator.py (NL → SPL translation)
      │
      ▼
mcp_client.py (Runs Splunk SDK Management API call)
      │
      ▼
agent.py (OpenAI LLM processes logs & synthesizes summary)
      │
      ▼
"GPT-4o cost $14.23 today across 4 services..."
```

**Available via CLI:**
```bash
python mcp_agent/cli.py
```

---

### Module C - AI Fleet Observatory

The AI Fleet Observatory is the primary real-time operational dashboard, providing live visibility into AI API costs, latency, token consumption, and model usage patterns across all instrumented services.

**Key Metrics Tracked:**

| Metric | Source | Refresh |
|---|---|---|
| Total AI API Cost (USD) | `cost_usd` per call | 15s |
| Average Latency (ms) | `latency_ms` per call | 15s |
| Error Rate (%) | `status=error` counts | 15s |
| Cost by Model | aggregated `cost_usd` grouped by model | 15s |
| Cost by Service | aggregated `cost_usd` grouped by service | 15s |
| Latency p50/p95 | percentile stats per model | 15s |
| Active AI Calls (timechart) | time-series call volume | 15s |

---

### Module D - EU AI Act Compliance

NeuralWatch continuously computes EU AI Act compliance scores for every monitored service, mapping live telemetry data and static policy baselines to five key articles.

**Scoring Model:**

```
Article 9 (Risk Management)     ──┐
Article 13 (Transparency)       ──┼─► Overall Score = (Art9+Art13+Art14+Art17+Art72)/5
Article 14 (Human Oversight)    ──┤
Article 17 (Quality Management) ──┤            │
Article 72 (Systemic Risk)      ──┘            ▼
                                    Score >= 90: ✅ COMPLIANT
                                    Score >= 70: ⚠️ AT RISK
                                    Score < 70:  ❌ NON-COMPLIANT
```

---

## Data Flow Diagram

```
1. Application calls OpenAI client completion method.
2. Instrumented SDK extracts token counts, latency, and computes cost.
3. SDK hashes prompts and enqueues events asynchronously in background queue.
4. SDK returns the API response instantly (zero-latency overhead).
5. Background thread batches and POSTs events to Splunk HTTP Event Collector (HEC).
6. Splunk indexes events in 'neuralwatch_ai_calls' and 'neuralwatch_injections'.
7. Live dashboards query Splunk every 15 seconds to update charts.
```

---

## Repository Structure

```
NeuralWatch/
│
├── neuralwatch_sdk/              # PyPI-publishable Python SDK
│   ├── __init__.py               # Public API: instrument, set_session_id, trace_context
│   ├── instrumentor.py           # Core monkey-patching engine (OpenAI + Anthropic)
│   ├── forwarder.py              # Non-blocking HEC telemetry queue with atexit flush
│   ├── cost_estimator.py         # Per-model USD pricing table and calculator
│   ├── cli.py                    # `neuralwatch` CLI (init / status / demo)
│   └── templates/                # App scaffolding templates
│
├── splunk_app/                   # Installable Splunk App
│   ├── default/
│   │   ├── app.conf              # App metadata
│   │   ├── props.conf            # Sourcetype extraction rules
│   │   ├── transforms.conf       # Lookup references
│   │   ├── savedsearches.conf    # Scheduled alert queries
│   │   └── data/ui/views/        # Dashboard XML definitions
│   │       ├── neuralwatch_main.xml         # AI Fleet Observatory
│   │       ├── neuralwatch_injection.xml    # Prompt Injection Sentinel
│   │       └── neuralwatch_compliance.xml   # EU AI Act Compliance
│   ├── bin/
│   │   ├── foundation_sec_classify.py   # Batch heuristic classifier
│   │   └── compliance_score.py          # SDK compliance score reporter
│   └── lookups/
│       ├── neuralwatch_compliance_baseline.csv   # Per-service policy config
│       └── neuralwatch_cost_model.csv            # Model pricing table
│
├── mcp_agent/                    # Natural language Splunk query agent
│   ├── agent.py                  # Core interrogator and answer synthesizer
│   ├── mcp_client.py             # Splunk SDK query runner
│   ├── spl_generator.py          # NL → SPL compiler with LLM
│   ├── cli.py                    # Interactive CLI entry point
│   └── prompts/
│       └── system_prompt.txt     # Agent system prompt with few-shot SPL examples
│
├── demo/
│   ├── live_simulator.py         # Continuous telemetry simulator (mocked OpenAI)
│   └── dummy_app.py              # Integration template for real OpenAI SDK
│
├── tests/
│   ├── unit/
│   │   └── test_instrumentor.py  # Unit tests for SDK instrumentation logic
│   └── integration/
│       └── test_hec_pipeline.py  # End-to-end HEC pipeline tests
│
├── splunk_app.tar.gz             # Pre-packaged release artifact for Splunk Web upload
├── pyproject.toml                # Build config for pip / PyPI packaging
├── requirements.txt              # Runtime dependencies
├── requirements-dev.txt          # Development and test dependencies
└── LICENSE                       # MIT License
```

---

## Quick Start

### Prerequisites

| Requirement | Version |
|---|---|
| Python | ≥ 3.9 |
| Splunk Enterprise | ≥ 9.0 |
| Splunk HTTP Event Collector | Enabled |
| OpenAI SDK | ≥ 1.0.0 (optional - only if using real calls) |
| Anthropic SDK | ≥ 0.3.0 (optional - only if using real calls) |

---

### 1. Install the SDK

**From PyPI (Production):**
```bash
pip install neuralwatch-splunk
```

**From source (Development):**
```bash
git clone https://github.com/geeked-anshuk666/NeuralWatch.git
cd NeuralWatch
pip install -e .
```

> [!NOTE]
> **Package Name vs. Import Namespace**
> - The installation package is named **`neuralwatch-splunk`** (e.g., `pip install neuralwatch-splunk`).
> - The Python namespace to import in your code is **`neuralwatch_sdk`** (e.g., `import neuralwatch_sdk`).

**Verify installation:**
```bash
neuralwatch --help
```

---

### 2. Initialize NeuralWatch

Run the interactive setup wizard. It validates your HEC connection and generates a local config file:

```bash
neuralwatch init
```

You will be prompted for:
- **Service name** - the name of your application (e.g., `checkout-service`)
- **Team name** - the owning team (e.g., `payments-eng`)
- **Splunk HEC URL** - e.g., `https://localhost:8088/services/collector/event`
- **HEC Token** - your Splunk HEC token (masked input)

This creates `.neuralwatch/config.json` with your settings.

---

### 3. Instrument Your Application

Add **two lines** to the entry point of your application:

```python
import openai
from neuralwatch_sdk import instrument, set_session_id

# Initialize once at startup
instrument(
    service="my-service",
    team="my-team",
    splunk_hec_url="https://localhost:8088/services/collector/event",
    splunk_hec_token="your-hec-token",
    capture_prompts=True,
    verify_ssl=False
)

# Optional: set a session or user ID for tracing (type-safe - no SDK changes needed)
set_session_id("user-session-abc123")

# Use OpenAI as normal - NeuralWatch captures everything automatically
client = openai.OpenAI(api_key="your-key")
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "How do I reset my password?"}]
)
```

**That's it.** NeuralWatch intercepts the call, extracts all telemetry, and sends it to Splunk without changing the response or adding any observable latency to your application.

#### Using `auto_instrument()` (config-file driven)

If you prefer loading configuration from the `.neuralwatch/config.json` file created by `neuralwatch init`:

```python
from neuralwatch_sdk import auto_instrument
auto_instrument()
```

#### Using `trace_context()` (scoped context management)

For request-scoped tracing in web frameworks:

```python
from neuralwatch_sdk import trace_context
import openai

client = openai.OpenAI()

with trace_context(session_id=request.user.id):
    # All AI calls within this block are tagged with the user's session ID
    response = client.chat.completions.create(...)
```

---

### 4. Install the Splunk App

#### Option A: Upload via Splunk Web (Recommended)

1. Navigate to **Splunk Web** → **Apps** → **Manage Apps**
2. Click **Install app from file**
3. Upload `splunk_app.tar.gz` from the repository root
4. Check **Overwrite app** if updating
5. Click **Upload**
6. Restart Splunk when prompted

#### Option B: Manual Installation

```bash
# Copy the app directory to your Splunk home
cp -r splunk_app/ $SPLUNK_HOME/etc/apps/neuralwatch/
$SPLUNK_HOME/bin/splunk restart
```

#### Create the Required Indexes

Run the index setup script (requires Splunk Management API credentials):

```bash
python demo/setup_indexes.py
```

Or create them manually in Splunk Web → **Settings** → **Indexes**:

| Index Name | Type | Sourcetypes |
|---|---|---|
| `neuralwatch_ai_calls` | Events | `nw:ai_call` |
| `neuralwatch_injections` | Events | `nw:prompt` |

---

### 5. Run the Live Simulator

The simulator provides a continuous stream of realistic AI telemetry events - including normal API calls, adversarial injection attempts, and simulated persistent attacker sessions - without requiring a real OpenAI API key.

```bash
python demo/live_simulator.py
```

The simulator will:
- Fire a new simulated AI event every **2 seconds**
- Route **40% of events** as adversarial injection attempts (HIGH/CRITICAL risk)
- Simulate **persistent session attacks** against `auth-service` to drive Art. 9 scoring
- Generate **~10% error events** to populate Art. 17 quality metrics
- Apply heuristic classification and populate `injection_score` and `risk_level` fields in real time

Open your Splunk dashboards after 30 seconds to see live, updating metrics.

---

## SDK Reference

### `instrument()`

The primary instrumentation function. Call once at application startup.

```python
from neuralwatch_sdk import instrument

instrument(
    service: str,           # Service identifier (e.g., "checkout-service")
    team: str,              # Team identifier (e.g., "payments-eng")
    splunk_hec_url: str,    # Full HEC endpoint URL
    splunk_hec_token: str,  # Splunk HEC authentication token
    capture_prompts: bool = True,   # Whether to capture prompt text for injection analysis
    verify_ssl: bool = False        # SSL certificate verification
)
```

**What it patches:** `openai.resources.chat.completions.Completions.create` and `anthropic.resources.messages.Messages.create` using monkey-patching with `setattr`. The original methods are preserved and called - NeuralWatch only wraps them.

**Events emitted per API call:**

| Event | Target Index | Fields |
|---|---|---|
| `AICallEvent` | `neuralwatch_ai_calls` | `call_id`, `service`, `team`, `model`, `provider`, `latency_ms`, `input_tokens`, `output_tokens`, `cost_usd`, `status`, `finish_reason`, `prompt_hash` |
| `PromptEvent` | `neuralwatch_injections` | `call_id`, `service`, `team`, `prompt_text`, `session_id`, `injection_score`, `risk_level` |

---

### `set_session_id()` and `trace_context()`

Thread-local session tracking - **type-safe** and compatible with native SDK type checkers.

```python
from neuralwatch_sdk import set_session_id, trace_context

# Simple setter (persistent for the thread)
set_session_id("user-abc-123")

# Context manager (auto-restores previous session on exit)
with trace_context(session_id="request-xyz-456"):
    response = client.chat.completions.create(...)
# session_id is automatically restored to previous value here
```

---

### `auto_instrument()`

Reads configuration from `.neuralwatch/config.json` and calls `instrument()` automatically. Useful for applications deployed with `neuralwatch init`.

```python
from neuralwatch_sdk import auto_instrument
auto_instrument()
```

---

### CLI Commands

```bash
# Initialize NeuralWatch and configure HEC connection
neuralwatch init [--service NAME] [--team NAME] [--splunk-url URL] [--token TOKEN]

# Inspect current configuration and connection status
neuralwatch status

# Send 100 test events to validate the telemetry pipeline
neuralwatch demo
```

---

## Splunk App Dashboards

### Dashboard 1: AI Fleet Observatory (`neuralwatch_main`)

The primary operations dashboard for engineering teams.

| Panel | Query | Insight |
|---|---|---|
| Total Cost (24h) | `sum(cost_usd)` | Total USD spent across all AI services |
| Average Latency | `avg(latency_ms)` | Mean response time across all models |
| Error Rate % | `errors/total × 100` | API reliability metric |
| Cost by Model | grouped by `model` | Which models are driving spend |
| Cost by Service | grouped by `service` | Which teams are the top spenders |
| Latency p50/p95 | percentile stats | Tail latency visibility per model |
| Call Volume (timechart) | `timechart span=5m count` | Call rate trends over time |

---

### Dashboard 2: Prompt Injection Sentinel (`neuralwatch_injection`)

Security dashboard for detecting and tracking adversarial prompt activity.

| Panel | Query | Insight |
|---|---|---|
| Active Incidents (24h) | `risk_level IN (HIGH,CRITICAL)` | Total high-severity threats |
| Threat Distribution | `stats count by risk_level` | Risk level breakdown pie chart |
| Incidents by Service | `stats count by service` | Which services are most targeted |
| Session Persistence | `stats dc(session_id) by service` | Repeated attacker session tracking |
| Injection Trend | `timechart span=5m count by risk_level` | Threat activity timeline |

---

### Dashboard 3: EU AI Act Compliance (`neuralwatch_compliance`)

Compliance monitoring dashboard mapping live telemetry to regulatory article scores.

| Panel | Article | Metric |
|---|---|---|
| Services Fully Compliant | Art. 13 + 14 | `disclosure_enabled=1 AND human_review_required=0` |
| Active Injection Incidents | Art. 9 | `risk_level IN (HIGH, CRITICAL)` |
| Services Requiring Human Review | Art. 14 | `human_review_required=1` |
| Quality Error Rate % | Art. 17 | `errors/total × 100` |
| Per-Service Compliance Scorecard | All | Full score matrix per service |
| Injection Incidents by Service | Art. 9 | Bar chart of incident counts |
| Disclosure Status Distribution | Art. 13 | Pie chart of disclosure compliance |
| Error Rate by Service | Art. 17 | Quality management per-service |
| Latency Drift by Model | Art. 72 | p50 vs p95 systemic risk |
| Threat Activity Timeline | Art. 9 | Live injection events per minute |

---

## Security Design

NeuralWatch follows secure-by-default design principles:

| Control | Implementation |
|---|---|
| **Secret Isolation** | HEC tokens never logged or embedded in source. Read from environment variables or `.neuralwatch/config.json` (git-ignored). |
| **Prompt Hashing** | Full prompt text is stored under `nw:prompt` sourcetype only when `capture_prompts=True`. Prompt hashes (SHA-256, truncated to 16 chars) are stored with AI call events only. |
| **Non-Blocking Forwarding** | All telemetry is enqueued asynchronously. The forwarder operates on a background daemon thread and never blocks your application's hot path. |
| **Graceful Failure** | Every instrumentation hook is wrapped in a `try/except`. If NeuralWatch encounters an error, your application continues normally - telemetry is silently dropped. |
| **SSL Verification** | Configurable per deployment. Disabled by default for local Splunk setups with self-signed certificates. Recommend `verify_ssl=True` for production. |
| **Queue Overflow Protection** | The forwarder queue has a maximum capacity of 10,000 events. Overflow events are dropped with a warning log, preventing memory growth. |
| **atexit Flush** | On application shutdown, the SDK waits up to 5 seconds for the telemetry queue to fully drain, ensuring no events are lost on clean exits. |

---

## EU AI Act Compliance Scoring

The compliance scoring engine computes a weighted score for each monitored service across five EU AI Act articles. Scores are computed in real time by joining live telemetry indexes with a static policy baseline CSV (`neuralwatch_compliance_baseline.csv`).

### Policy Baseline Configuration

The `splunk_app/lookups/neuralwatch_compliance_baseline.csv` file defines per-service compliance policies:

```csv
service,disclosure_enabled,human_review_required,human_review_threshold,risk_category,ai_act_scope
checkout-service,1,1,0.95,high_risk,yes
auth-service,1,0,0.0,limited_risk,yes
fraud-detection-svc,1,1,0.95,high_risk,yes
product-svc,1,0,0.0,minimal_risk,yes
email-svc,0,0,0.0,minimal_risk,yes
```

| Column | Description |
|---|---|
| `disclosure_enabled` | Whether the service discloses AI usage to end users (Art. 13) |
| `human_review_required` | Whether human review is mandated for AI outputs (Art. 14) |
| `human_review_threshold` | Confidence threshold above which human review is required |
| `risk_category` | EU AI Act risk classification (`high_risk`, `limited_risk`, `minimal_risk`) |
| `ai_act_scope` | Whether the service falls within EU AI Act scope |

### Running the Compliance Report Programmatically

```bash
python splunk_app/bin/compliance_score.py
```

**Example output:**
```json
{
  "status": "success",
  "overall_average": 87.4,
  "services": [
    { "service": "auth-service", "overall_score": "96.0", "status": "COMPLIANT" },
    { "service": "product-svc",  "overall_score": "90.0", "status": "COMPLIANT" },
    { "service": "checkout-service", "overall_score": "82.0", "status": "AT RISK" },
    { "service": "email-svc",    "overall_score": "74.0", "status": "AT RISK" },
    { "service": "fraud-detection-svc", "overall_score": "68.0", "status": "NON-COMPLIANT" }
  ]
}
```

---

## MCP Agent - Natural Language Querying

The `mcp_agent` module implements a conversational query interface over all NeuralWatch Splunk indexes.

### Running the Agent

```bash
python mcp_agent/cli.py
```

### Example Queries

```
You: How much did we spend on GPT-4o today?
NeuralWatch: GPT-4o cost $14.23 today across 4 services. checkout-service is 
             the top spender at $6.77 (47.6% of total GPT-4o spend).

You: Which service has the most injection incidents this week?
NeuralWatch: auth-service leads with 47 HIGH/CRITICAL injection events this week,
             followed by checkout-service with 31 incidents.

You: What is the average latency for Claude models?
NeuralWatch: Claude-3-Opus averages 1,847ms (p95: 3,200ms). Claude-3-Sonnet 
             averages 892ms (p95: 1,450ms).
```

### How SPL Generation Works

The `spl_generator.py` module uses an LLM with a specialized system prompt that includes:
- NeuralWatch index schema documentation
- Available fields per sourcetype
- Few-shot examples of natural language → SPL translations
- Common aggregation patterns for cost, latency, and security queries

---

## Configuration Reference

### Environment Variables

| Variable | Required | Description |
|---|---|---|
| `SPLUNK_HEC_URL` | Yes | Full HEC endpoint (e.g., `https://localhost:8088/services/collector/event`) |
| `SPLUNK_HEC_TOKEN` | Yes | Splunk HEC authentication token |
| `SPLUNK_HOST` | Optional | Splunk Management API host (default: `localhost`) |
| `SPLUNK_PORT` | Optional | Splunk Management API port (default: `8089`) |
| `SPLUNK_USERNAME` | Optional | Splunk admin username (default: `admin`) |
| `SPLUNK_PASSWORD` | Optional | Splunk admin password (required for MCP agent and compliance reporter) |
| `OPENAI_API_KEY` | Optional | OpenAI API key (required only for real AI calls and the MCP agent) |

Create a `.env` file in the repository root (already git-ignored):

```env
SPLUNK_HEC_URL=https://localhost:8088/services/collector/event
SPLUNK_HEC_TOKEN=your-hec-token-here
SPLUNK_HOST=localhost
SPLUNK_PORT=8089
SPLUNK_USERNAME=admin
SPLUNK_PASSWORD=your-splunk-password
OPENAI_API_KEY=sk-your-openai-key
```

### `instrument()` Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `service` | `str` | - | Service name for telemetry attribution |
| `team` | `str` | - | Team name for telemetry attribution |
| `splunk_hec_url` | `str` | - | Splunk HEC endpoint URL |
| `splunk_hec_token` | `str` | - | Splunk HEC token |
| `capture_prompts` | `bool` | `True` | Enable prompt capture to `neuralwatch_injections` |
| `verify_ssl` | `bool` | `False` | Enable SSL certificate verification for HEC requests |

---

## Development

### Setup

```bash
git clone https://github.com/your-org/neuralwatch.git
cd neuralwatch
pip install -e ".[dev]"
```

### Running Tests

```bash
pytest tests/ -v --cov=neuralwatch_sdk
```

### Running the Live Simulator

```bash
python demo/live_simulator.py
```

### Code Quality

```bash
ruff check neuralwatch_sdk/
mypy neuralwatch_sdk/
```

### Building the Splunk App Package

```bash
tar -czf splunk_app.tar.gz splunk_app/
```

### Project Commit History

| Commit | Description |
|---|---|
| `d4d0faa` | `feat(sdk)` - Core monkey-patching engine and non-blocking HEC forwarder |
| `22fff19` | `feat(splunk)` - App metadata, custom props, cost/compliance lookups |
| `bad5602` | `feat(observability)` - AI Fleet Observatory dashboard and bulk simulator |
| `95555fd` | `feat(security)` - Prompt Injection Sentinel and Foundation-Sec classifier |
| `d87a5b8` | `feat(mcp)` - MCP client, agent bridge, and NL-to-SPL compiler |
| `8ec8be3` | `feat(compliance)` - EU AI Act scoring dashboard and unit/integration tests |
| `8273880` | `feat(demo)` - Continuous live telemetry simulator with mocked OpenAI client |
| `1b21137` | `fix(compliance)` - Live index queries and resolved empty dashboard panels |
| `f517893` | `feat(sdk)` - Thread-local session tracking, atexit flush, PyPI namespace isolation |
| `4c3d3b8` | `feat(demo)` - Simulator updated to align with EU AI Act dashboard risk categories |
| `1c14979` | `build(release)` - Finalized Splunk App release artifact v1.0.0 |

---

## License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

```
MIT License

Copyright (c) 2026 NeuralWatch

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.
```

---

<p align="center">Built with ❤️ for the AI-powered enterprise. MIT Licensed.</p>
