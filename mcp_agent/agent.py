"""
Module: agent
Purpose: Core natural language analytics agent chaining Splunk MCP tools and synthesizing answers.
Part of: NeuralWatch - AI Fleet Observatory for Splunk
Hackathon: Splunk Agentic Ops 2026

Dependencies:
  - openai: for answer synthesis
  - mcp_agent.mcp_client: for executing Splunk queries
  - mcp_agent.spl_generator: for translating questions to SPL

Usage:
  from mcp_agent.agent import NeuralWatchAgent
  agent = NeuralWatchAgent()
  answer = agent.answer("How much did we spend on GPT-4o today?")
"""

import os
import json
import logging
from typing import Optional
from openai import OpenAI
from dotenv import load_dotenv
from mcp_agent.mcp_client import MCPClient
from mcp_agent.spl_generator import generate_spl

load_dotenv(override=True)
logger = logging.getLogger("neuralwatch")

class NeuralWatchAgent:
    """
    Agent that chains multiple Splunk tools to respond to natural language questions.
    """
    def __init__(self, callback_display_tool=None):
        """
        Initialize the agent and connect to the Splunk MCP Server client.
        
        Args:
            callback_display_tool: Optional callback to notify CLI when a tool is called.
        """
        self.callback_display_tool = callback_display_tool
        
        # Pull Splunk settings
        host = os.getenv("SPLUNK_HOST", "localhost")
        port = int(os.getenv("SPLUNK_PORT", "8089"))
        user = os.getenv("SPLUNK_USERNAME", "admin")
        pw = os.getenv("SPLUNK_PASSWORD", "")
        
        # Configure tool runner
        self.client = MCPClient(host, port, user, pw)
        self.saia_available: Optional[bool] = None
        
    def _log_tool_call(self, tool_name: str, status: str, detail: str = ""):
        if self.callback_display_tool:
            self.callback_display_tool(tool_name, status, detail)

    def answer(self, question: str) -> str:
        """
        Processes a natural language question by chaining Splunk MCP tools.
        
        Workflow:
          1. Discovery: splunk_get_indexes()
          2. Generation: Translates question to SPL (via spl_generator)
          3. Query execution: splunk_run_query()
          4. Synthesis: Asks LLM to answer using query result tables.
        
        Returns:
            Natural language response summary.
        """
        # Step 1: Discover indexes (Tool Call 1)
        self._log_tool_call("splunk_get_indexes", "running", "Fetching list of available indexes")
        indexes = self.client.call_tool("splunk_get_indexes")
        if isinstance(indexes, dict) and "error" in indexes:
            self._log_tool_call("splunk_get_indexes", "failed", indexes["error"])
            return f"Failed to connect to Splunk: {indexes['error']}"
            
        self._log_tool_call(
            "splunk_get_indexes",
            "success",
            f"Found {len(indexes)} indexes ({', '.join([i for i in indexes if i.startswith('neuralwatch')])})"
        )

        # Step 2: Generate SPL query (Tool Call 2 - Try SAIA first with adaptive caching, fall back to LLM)
        use_saia = False
        saia_result: dict = {"error": "SAIA not attempted"}  # always-bound sentinel
        if self.saia_available is None:
            self._log_tool_call("saia_generate_spl", "running", f"Probing SAIA for query: '{question}'")
            saia_result = self.client.call_tool(
                "saia_generate_spl", 
                {"question": question, "indexes": ["neuralwatch_ai_calls", "neuralwatch_injections"]}
            )
            if isinstance(saia_result, dict) and "error" not in saia_result:
                self.saia_available = True
                use_saia = True
                spl = saia_result.get("spl", "")
                self._log_tool_call("saia_generate_spl", "success", f"Generated query via SAIA: {spl}")
            else:
                self.saia_available = False
                reason = saia_result.get("error") if isinstance(saia_result, dict) else "unknown error"
                self._log_tool_call("saia_generate_spl", "failed", f"{reason}. SAIA unavailable; caching failure status.")

        if self.saia_available and not use_saia:
            self._log_tool_call("saia_generate_spl", "running", f"Translating query: '{question}'")
            saia_result = self.client.call_tool(
                "saia_generate_spl", 
                {"question": question, "indexes": ["neuralwatch_ai_calls", "neuralwatch_injections"]}
            )
            if isinstance(saia_result, dict) and "error" not in saia_result:
                spl = saia_result.get("spl", "")
                self._log_tool_call("saia_generate_spl", "success", f"Generated query via SAIA: {spl}")
            else:
                self._log_tool_call("saia_generate_spl", "failed", "SAIA execution failed. Trying LLM fallback...")
                self._log_tool_call("LLM fallback SPL generator", "running", f"Translating: '{question}'")
                spl = generate_spl(question)
                self._log_tool_call("LLM fallback SPL generator", "success", f"Generated query via LLM: {spl}")
        elif not self.saia_available and not use_saia:
            self._log_tool_call("LLM fallback SPL generator", "running", f"Translating: '{question}' (SAIA cached as unavailable)")
            spl = generate_spl(question)
            self._log_tool_call("LLM fallback SPL generator", "success", f"Generated query via LLM: {spl}")

        # Step 3: Execute SPL (Tool Call 3)
        self._log_tool_call("splunk_run_query", "running", f"Executing SPL: {spl}")
        results_data = self.client.call_tool("splunk_run_query", {"spl": spl})
        
        if isinstance(results_data, dict) and "error" in results_data:
            self._log_tool_call("splunk_run_query", "failed", results_data["error"])
            return f"Failed to execute Splunk query: {results_data['error']}"
            
        self._log_tool_call("splunk_run_query", "success", f"Search completed. Returned {len(results_data)} rows.")

        # Step 4: Synthesize Answer
        # If SAIA is active, call saia_explain_spl first and pass it to synthesis
        explanation = ""
        if isinstance(saia_result, dict) and "error" not in saia_result:
            self._log_tool_call("saia_explain_spl", "running", f"Explaining query: {spl}")
            explain_res = self.client.call_tool("saia_explain_spl", {"spl": spl})
            if isinstance(explain_res, dict) and "error" not in explain_res:
                explanation = explain_res.get("explanation", "")
                self._log_tool_call("saia_explain_spl", "success", "Explanation retrieved from SAIA")
            else:
                self._log_tool_call("saia_explain_spl", "failed", explain_res.get("error", "unknown error") if isinstance(explain_res, dict) else "unknown error")

        self._log_tool_call("Synthesizing answer", "running", "Processing raw data rows")
        answer = self._synthesize_answer(question, spl, results_data, explanation=explanation)
        self._log_tool_call("Synthesizing answer", "success", "Answer finalized")
        
        return answer

    def _synthesize_answer(self, question: str, spl: str, results_data: list, explanation: str = "") -> str:
        """
        Asks the LLM to format and synthesize the final answer based on Splunk search outputs.
        """
        api_key = os.getenv("LLM_API_KEY")
        base_url = os.getenv("LLM_API_BASE", "https://api.openai.com/v1")
        model = os.getenv("LLM_MODEL", "gpt-4o")

        # Static fallback if no LLM key is configured
        if not api_key or api_key == "your_llm_api_key_here":
            return self._static_fallback_synthesis(question, results_data)

        # Prepare summary of results for prompt context
        results_summary = json.dumps(results_data[:20], indent=2)  # Cap at 20 rows to save context space

        system_prompt = (
            "You are a professional security and observability operations analyst at NeuralWatch.\n"
            "Format the raw Splunk query output into a concise, professional response to the user's question.\n"
            "Include specific numbers, costs, and model metrics if present in the data.\n"
            "Keep the answer under 3-4 sentences. Be direct and operational.\n"
        )

        user_content = (
            f"User Question: {question}\n\n"
            f"Splunk SPL query used: {spl}\n\n"
            f"Search Results Output:\n{results_summary}"
        )
        if explanation:
            user_content += f"\n\nSplunk AI Assistant Query Explanation:\n{explanation}"

        try:
            extra_headers = {}
            if "openrouter" in base_url:
                extra_headers = {
                    "HTTP-Referer": os.getenv("OPENROUTER_SITE_URL", "https://neuralwatch.local"),
                    "X-Title": os.getenv("OPENROUTER_APP_NAME", "NeuralWatch"),
                }
            client = OpenAI(api_key=api_key, base_url=base_url, default_headers=extra_headers)
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                temperature=0.2,
                max_tokens=250
            )
            content = response.choices[0].message.content
            if content and content.strip():
                return content.strip()
            
            logger.warning("[NeuralWatch] LLM synthesis returned empty content. Falling back to static synthesis.")
            return self._static_fallback_synthesis(question, results_data)
        except Exception as e:
            logger.error(f"[NeuralWatch] Answer synthesis failed: {e}")
            return self._static_fallback_synthesis(question, results_data)

    def _static_fallback_synthesis(self, question: str, results_data: list) -> str:
        """
        Static answer formatting when no LLM key is configured.
        """
        if not results_data:
            return "No data found matching your query."

        row = results_data[0]

        if "total_cost" in row or "total_cost_usd" in row:
            total = sum(float(r.get("total_cost", r.get("cost_usd", r.get("total_cost_usd", 0)))) for r in results_data)
            return f"The total cost across all teams is **${total:.2f}** from {len(results_data)} team(s)."

        if "total_input_tokens" in row or "total_output_tokens" in row or "total_tokens" in row:
            total_in = sum(int(r.get("total_input_tokens", 0)) for r in results_data)
            total_out = sum(int(r.get("total_output_tokens", 0)) for r in results_data)
            top_model = results_data[0].get("model", "unknown")
            return (
                f"Total token usage across {len(results_data)} model(s): "
                f"**{total_in:,} input tokens** and **{total_out:,} output tokens** "
                f"({total_in + total_out:,} total). Highest usage: {top_model}."
            )

        if "p99" in row or "p95" in row or "p50" in row:
            lines = [f"{r.get('model','?')}: p50={r.get('p50','?')}ms p95={r.get('p95','?')}ms p99={r.get('p99','?')}ms" for r in results_data[:5]]
            return "Latency by model:\n" + "\n".join(lines)

        if "error_rate" in row:
            services_info = ", ".join([f"{r.get('service','?')}: {r.get('error_rate','?')}%" for r in results_data[:5]])
            return f"Service error rates: {services_info}."

        if "attacks" in row or "injection_score" in row or "avg_score" in row:
            total_attacks = sum(int(r.get("attacks", 0)) for r in results_data)
            return f"Detected **{total_attacks} prompt injection attack(s)** across {len(results_data)} service/risk combinations."

        if "calls" in row and "cost" in row:
            top = results_data[0]
            return f"Top model by call volume: **{top.get('model','?')}** with {top.get('calls','?')} calls costing ${float(top.get('cost',0)):.2f}."

        if "total_calls" in row:
            total = sum(int(r.get("total_calls", 0)) for r in results_data)
            return f"Total AI calls: **{total:,}** across {len(results_data)} service(s)."

        # Generic fallback - show field names and first row values
        fields = list(row.keys())[:6]
        summary = ", ".join(f"{f}={row[f]}" for f in fields)
        return f"Retrieved {len(results_data)} row(s) from Splunk. Sample: {summary}."
