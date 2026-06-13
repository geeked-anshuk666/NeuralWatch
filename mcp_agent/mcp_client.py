"""
Module: mcp_client
Purpose: Establishes connection to Splunk REST API, mirroring Splunk MCP Server v1.2 tool behaviors.
Part of: NeuralWatch — AI Fleet Observatory for Splunk
Hackathon: Splunk Agentic Ops 2026

Dependencies:
  - splunklib.client: official Splunk SDK for executing REST commands and searches
  - python-dotenv: environment config

Usage:
  from mcp_agent.mcp_client import MCPClient
  client = MCPClient("localhost", 8089, "admin", "password")
  indexes = client.call_tool("splunk_get_indexes")
"""

import json
import logging
from typing import Any, Optional
import splunklib.client as client
import splunklib.results as results
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("neuralwatch")

class MCPClient:
    """
    Abstractions mirroring the Splunk MCP Server tool ecosystem.
    Communicates directly with Splunk Enterprise over the Management Port.
    """
    def __init__(self, host: str = "localhost", port: int = 8089, username: str = "admin", password: str = ""):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.service: Optional[Any] = None

    def connect(self) -> bool:
        """Establish session connection to Splunk REST Management API."""
        try:
            # Connect using splunk SDK client
            self.service = client.connect(
                host=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                verify=False
            )
            return True
        except Exception as e:
            logger.warning(f"[NeuralWatch] Failed to connect to Splunk Management API: {e}")
            return False

    def call_tool(self, tool_name: str, params: Optional[dict] = None) -> Any:
        """
        Execute an MCP-equivalent tool call.
        Chains to standard API operations under the hood.
        """
        if not self.service and not self.connect():
            return {"error": "Splunk is unreachable. Verify connection credentials in .env"}

        if params is None:
            params = {}

        try:
            if tool_name == "splunk_get_indexes":
                return self._splunk_get_indexes()
            elif tool_name == "splunk_run_query":
                spl = params.get("spl", "")
                earliest = params.get("earliest", "-24h")
                latest = params.get("latest", "now")
                return self._splunk_run_query(spl, earliest, latest)
            elif tool_name == "splunk_get_knowledge_objects":
                return self._splunk_get_knowledge_objects()
            elif tool_name == "splunk_run_saved_search":
                search_name = params.get("name", "")
                return self._splunk_run_saved_search(search_name)
            elif tool_name == "saia_generate_spl":
                question = params.get("question", "")
                indexes = params.get("indexes", [])
                return self._saia_generate_spl(question, indexes)
            elif tool_name == "saia_explain_spl":
                spl = params.get("spl", "")
                return self._saia_explain_spl(spl)
            else:
                return {"error": f"Tool '{tool_name}' is not supported."}
        except Exception as e:
            logger.error(f"[NeuralWatch] Tool execution error ({tool_name}): {e}")
            return {"error": str(e)}

    def _splunk_get_indexes(self) -> list[str]:
        """Fetch list of active indexes."""
        # Mirror: splunk_get_indexes
        if self.service:
            return [idx.name for idx in self.service.indexes]
        return []

    def _splunk_run_query(self, spl: str, earliest: str, latest: str) -> list[dict]:
        """Execute search SPL and return results in tabular/list format."""
        # Mirror: splunk_run_query
        # Standard safety wraps
        if not spl.strip().lower().startswith("search") and not spl.strip().startswith("|"):
            spl = f"search {spl}"

        if not self.service:
            return []

        job = self.service.jobs.create(spl, earliest_time=earliest, latest_time=latest)
        while not job.is_done():
            # Wait for job completion
            pass

        has_xml_reader = hasattr(results, "ResultsReader")
        output_mode = "xml" if has_xml_reader else "json"
        
        raw_results = job.results(count=100, output_mode=output_mode)
        if has_xml_reader:
            reader = getattr(results, "ResultsReader")(raw_results)
        else:
            reader = getattr(results, "JSONResultsReader")(raw_results)
            
        results_list = []
        for result in reader:
            if isinstance(result, dict):
                results_list.append(dict(result))
        return results_list

    def _splunk_get_knowledge_objects(self) -> list[str]:
        """List saved searches matching NeuralWatch namespace."""
        # Mirror: splunk_get_knowledge_objects
        if self.service:
            searches = self.service.saved_searches
            return [s.name for s in searches if s.name.startswith("NeuralWatch")]
        return []

    def _splunk_run_saved_search(self, search_name: str) -> list[dict]:
        """Execute a predefined Splunk saved search."""
        # Mirror: splunk_run_saved_search
        if not self.service:
            return []
            
        saved_search = self.service.saved_searches.get(search_name)
        if not saved_search:
            return []
            
        # Run saved search job
        job = saved_search.dispatch()
        while not job.is_done():
            pass

        has_xml_reader = hasattr(results, "ResultsReader")
        output_mode = "xml" if has_xml_reader else "json"
        
        raw_results = job.results(count=100, output_mode=output_mode)
        if has_xml_reader:
            reader = getattr(results, "ResultsReader")(raw_results)
        else:
            reader = getattr(results, "JSONResultsReader")(raw_results)
            
        results_list = []
        for result in reader:
            if isinstance(result, dict):
                results_list.append(dict(result))
        return results_list

    def _saia_generate_spl(self, question: str, indexes: list[str]) -> dict:
        """
        Calls Splunk AI Assistant (SAIA) to generate SPL from natural language.
        If SAIA is unavailable/unconfigured, returns an error to trigger local LLM fallback.
        """
        if not self.service:
            return {"error": "Splunk unreachable"}
            
        try:
            # Check if SAIA app is installed
            has_saia = False
            for app in self.service.apps:
                if "splunk_ai_assistant" in app.name or "saia" in app.name:
                    has_saia = True
                    break
                    
            if not has_saia:
                return {"error": "Splunk AI Assistant (SAIA) app is not installed"}

            # Try to query the SAIA generation endpoint if available
            response = self.service.post("splunk_ai_assistant/generate_spl", question=question, indexes=",".join(indexes))
            content = response.read().decode("utf-8")
            data = json.loads(content)
            return {"spl": data.get("spl", "")}
        except Exception as e:
            logger.info(f"[NeuralWatch] SAIA generate_spl unavailable: {e}. Falling back to configured LLM.")
            return {"error": f"SAIA generate_spl unavailable: {e}"}

    def _saia_explain_spl(self, spl: str) -> dict:
        """
        Calls Splunk AI Assistant (SAIA) to explain SPL queries in natural language.
        """
        if not self.service:
            return {"error": "Splunk unreachable"}
            
        try:
            # Check if SAIA is installed
            has_saia = False
            for app in self.service.apps:
                if "splunk_ai_assistant" in app.name or "saia" in app.name:
                    has_saia = True
                    break
                    
            if not has_saia:
                return {"error": "Splunk AI Assistant (SAIA) app is not installed"}

            response = self.service.post("splunk_ai_assistant/explain_spl", spl=spl)
            content = response.read().decode("utf-8")
            data = json.loads(content)
            return {"explanation": data.get("explanation", "")}
        except Exception as e:
            return {"error": f"SAIA explain_spl unavailable: {e}"}
