"""
Module: spl_generator
Purpose: Generates Splunk search queries (SPL) from natural language questions using an LLM.
Part of: NeuralWatch — AI Fleet Observatory for Splunk
Hackathon: Splunk Agentic Ops 2026

Dependencies:
  - openai: to communicate with OpenAI-compatible API providers (OpenRouter, Nvidia, etc.)
  - python-dotenv: to load environment configuration variables

Usage:
  from mcp_agent.spl_generator import generate_spl
  spl = generate_spl("show average latency by model")
"""

import os
import logging
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(override=True)
logger = logging.getLogger("neuralwatch")

# Detailed schema-aware system prompt for SPL generation
_SYSTEM_PROMPT = """You are a Splunk SPL (Search Processing Language) expert for NeuralWatch, an AI fleet observability platform.

## NeuralWatch Splunk Schema

### index=neuralwatch_ai_calls  sourcetype="nw:ai_call"
Fields: call_id, timestamp, service, team, model, status (ok|error|timeout),
        latency_ms (int), tokens_in (int), tokens_out (int), cost_usd (float),
        user_id, session_id, environment (prod|staging|dev)

### index=neuralwatch_injections  sourcetype="nw:prompt"
Fields: call_id, timestamp, service, session_id, prompt_text,
        injection_score (0.0-1.0), risk_level (LOW|MEDIUM|HIGH|CRITICAL)

### index=neuralwatch_costs  sourcetype="nw:cost"
Fields: date, service, model, total_cost_usd, total_calls, avg_cost_per_call

### index=neuralwatch_drift  sourcetype="nw:drift"
Fields: timestamp, model, metric, value, baseline_value, drift_pct

## Valid SPL Syntax Rules
- stats: `stats AGGFUNC(field) as alias [, AGGFUNC(field) as alias]* [by field1 [, field2]]`
  AGGFUNC options: sum, count, avg, p50, p95, p99, min, max, values, dc
  Example: `stats sum(cost_usd) as total_cost by model`
  WRONG: `stats total by (field)` or `stats field as alias by (field1, field2)`
- eval inside stats: `count(eval(status="error"))` is valid
- timechart: `timechart span=1h count by model`
- sort: `sort -field` (descending) or `sort field` (ascending)
- head N: limit to N results

## Output Rules
- Output ONLY the raw SPL query string. No markdown, no backticks, no explanation.
- Always start with `index=` or `|` (for inputlookup).
- Use the exact field names from the schema above.

## Examples
User: What is the total cost?
SPL: index=neuralwatch_ai_calls sourcetype="nw:ai_call" | stats sum(cost_usd) as total_cost by team | sort -total_cost

User: Show me latency by model
SPL: index=neuralwatch_ai_calls sourcetype="nw:ai_call" | stats p50(latency_ms) as p50, p95(latency_ms) as p95, p99(latency_ms) as p99 by model | sort -p99

User: Which services have the most errors?
SPL: index=neuralwatch_ai_calls sourcetype="nw:ai_call" | stats count as total, count(eval(status="error")) as errors by service | eval error_rate=round(errors/total*100,2) | sort -error_rate

User: What is my total token usage?
SPL: index=neuralwatch_ai_calls sourcetype="nw:ai_call" | stats sum(tokens_in) as total_input_tokens, sum(tokens_out) as total_output_tokens by model | sort -total_input_tokens

User: Show prompt injection attacks
SPL: index=neuralwatch_injections sourcetype="nw:prompt" | where injection_score>0.65 | stats count as attacks, avg(injection_score) as avg_score by service, risk_level | sort -attacks
"""


def _validate_spl(spl: str) -> bool:
    """
    Basic sanity check to detect obviously-broken SPL before sending to Splunk.
    Returns True if SPL looks valid enough to try.
    """
    if not spl or len(spl) < 15:
        return False
    # Must start with index= or a pipe command
    if not (spl.startswith("index=") or spl.startswith("|") or spl.startswith("search ")):
        return False
    # Reject markdown bleed
    if "```" in spl or spl.startswith("#"):
        return False
    # Must contain at least one pipe — bare "index=X" with no stats/timechart is useless
    if "|" not in spl:
        return False
    # Reject known bad stats patterns like "stats total by (field)"
    import re
    if re.search(r'stats\s+\w+\s+by\s*\(', spl):
        return False
    return True


def generate_spl(question: str) -> str:
    """
    Generate Splunk SPL query from natural language query.

    Configured to use any OpenAI-compatible provider (e.g. OpenRouter, Nvidia, OpenAI, Anthropic).
    Falls back to pre-validated static keyword mappings if LLM is unavailable or produces bad SPL.

    Args:
        question: User's natural language question (e.g. "which service has the highest error rate?")

    Returns:
        SPL query string ready to execute on Splunk.
    """
    api_key = os.getenv("LLM_API_KEY")
    base_url = os.getenv("LLM_API_BASE", "https://api.openai.com/v1")
    model = os.getenv("LLM_MODEL", "gpt-4o")

    if not api_key or api_key in ("your_llm_api_key_here", "your_openrouter_api_key_here"):
        logger.warning("[NeuralWatch] LLM API key not set. Using fallback static SPL mappings.")
        return _fallback_spl_mapping(question)

    # Allow override from external prompt file
    system_prompt = _SYSTEM_PROMPT
    try:
        prompt_path = os.path.join(os.path.dirname(__file__), "prompts", "system_prompt.txt")
        if os.path.exists(prompt_path):
            with open(prompt_path, "r") as f:
                system_prompt = f.read()
    except Exception as e:
        logger.warning(f"[NeuralWatch] Could not load system prompt file: {e}")

    try:
        extra_headers = {}
        if "openrouter" in base_url:
            extra_headers = {
                "HTTP-Referer": os.getenv("OPENROUTER_SITE_URL", "https://neuralwatch.local"),
                "X-Title": os.getenv("OPENROUTER_APP_NAME", "NeuralWatch"),
            }
        llm = OpenAI(api_key=api_key, base_url=base_url, default_headers=extra_headers)

        response = llm.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question}
            ],
            temperature=0.0,
            max_tokens=250
        )

        content = response.choices[0].message.content
        spl_query = content.strip() if content else ""

        # Strip markdown code fences if any
        if spl_query.startswith("```"):
            lines = spl_query.splitlines()
            spl_query = "\n".join(lines[1:-1]) if lines[-1].startswith("```") else "\n".join(lines[1:])
        spl_query = spl_query.replace("`", "").strip()

        # Validate before returning — fall back if LLM produced bad SPL
        if not _validate_spl(spl_query):
            logger.warning(f"[NeuralWatch] LLM produced invalid SPL: '{spl_query}'. Using static fallback.")
            return _fallback_spl_mapping(question)

        return spl_query

    except Exception as e:
        logger.error(f"[NeuralWatch] LLM SPL generation failed: {e}. Using fallback static query.")
        return _fallback_spl_mapping(question)


def _fallback_spl_mapping(question: str) -> str:
    """
    Returns pre-validated search queries based on keywords in the natural language question.
    """
    q = question.lower()

    if "cost" in q or "budget" in q or "spend" in q or "price" in q:
        if "forecast" in q or "predict" in q:
            return 'index=neuralwatch_ai_calls sourcetype="nw:ai_call" | timechart span=1d sum(cost_usd) as daily_cost | predict daily_cost algorithm=LLP5 future_timespan=7 as forecast upper95 lower95'
        return 'index=neuralwatch_ai_calls sourcetype="nw:ai_call" | stats sum(cost_usd) as total_cost by team | sort -total_cost'

    if "token" in q or "throughput" in q:
        return 'index=neuralwatch_ai_calls sourcetype="nw:ai_call" | stats sum(tokens_in) as total_input_tokens, sum(tokens_out) as total_output_tokens by model | sort -total_input_tokens'

    if "usage" in q and "model" in q:
        return 'index=neuralwatch_ai_calls sourcetype="nw:ai_call" | stats count as calls, sum(cost_usd) as cost by model | sort -calls | head 10'

    if "usage" in q:
        return 'index=neuralwatch_ai_calls sourcetype="nw:ai_call" | stats count as total_calls, sum(cost_usd) as total_cost, sum(tokens_in) as total_tokens_in, sum(tokens_out) as total_tokens_out by service | sort -total_calls'

    if "latency" in q or "speed" in q or "slow" in q or "fast" in q:
        return 'index=neuralwatch_ai_calls sourcetype="nw:ai_call" | stats p50(latency_ms) as p50, p95(latency_ms) as p95, p99(latency_ms) as p99, count by model | sort -p99'

    if "error" in q or "failure" in q or "fail" in q:
        return 'index=neuralwatch_ai_calls sourcetype="nw:ai_call" | stats count as total, count(eval(status="error")) as errors by service | eval error_rate=round(errors/total*100,2) | sort -error_rate'

    if "injection" in q or "attack" in q or "security" in q or "prompt" in q:
        return 'index=neuralwatch_injections sourcetype="nw:prompt" | where injection_score>0.65 | stats count as attacks, avg(injection_score) as avg_score by service, risk_level | sort -attacks'

    if "compliance" in q or "eu ai act" in q or "regulation" in q:
        return 'index=neuralwatch_ai_calls sourcetype="nw:ai_call" | stats count as total_calls, count(eval(status="error")) as errors by service | eval error_rate=round(errors/total_calls*100,2) | eval compliance=if(error_rate<5,"COMPLIANT","AT RISK") | table service, total_calls, error_rate, compliance'

    if ("top" in q or "popular" in q or "most" in q) and "model" in q:
        return 'index=neuralwatch_ai_calls sourcetype="nw:ai_call" | stats count as calls, sum(cost_usd) as cost by model | sort -calls | head 10'

    if "drift" in q or "degradation" in q:
        return 'index=neuralwatch_drift sourcetype="nw:drift" | stats avg(drift_pct) as avg_drift, max(drift_pct) as max_drift by model, metric | sort -max_drift'

    # Default: call volume over time
    return 'index=neuralwatch_ai_calls sourcetype="nw:ai_call" | timechart span=1h count by model | fillnull value=0'


