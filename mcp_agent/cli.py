"""
Module: cli
Purpose: Terminal command line interface for natural language interrogation of Splunk.
Part of: NeuralWatch - AI Fleet Observatory for Splunk
Hackathon: Splunk Agentic Ops 2026

Dependencies:
  - rich: for high-fidelity interactive CLI formats
  - mcp_agent.agent: core interrogator logic

Usage:
  python mcp_agent/cli.py
"""

import sys
import logging
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from mcp_agent.agent import NeuralWatchAgent

# Force stdout/stderr to UTF-8 so Rich can render Unicode symbols on Windows CP1252 consoles
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Suppress debug logs from libraries
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

console = Console()

# Symbols: fall back to ASCII if terminal can't render Unicode
def _sym(unicode_char: str, ascii_fallback: str) -> str:
    try:
        unicode_char.encode(sys.stdout.encoding or "utf-8")
        return unicode_char
    except (UnicodeEncodeError, TypeError):
        return ascii_fallback

SYM_SPIN = _sym("⟳", "~")
SYM_OK   = _sym("✔", "OK")
SYM_FAIL = _sym("✘", "!!")
SYM_ERR  = _sym("✖", "XX")

def display_tool_call(tool_name: str, status: str, detail: str = ""):
    """
    Console callback to render tool execution state in real-time.
    """
    if status == "running":
        console.print(f"  [dim]{SYM_SPIN} {tool_name}...[/dim]")
    elif status == "success":
        console.print(f"    [green]{SYM_OK}[/green] [dim]{tool_name} completed. {detail}[/dim]")
    elif status == "failed":
        console.print(f"    [red]{SYM_FAIL}[/red] [bold red]{tool_name} failed: {detail}[/bold red]")

def run_cli():
    """
    Starts the interactive query loop for Splunk interrogations.
    """
    welcome_panel = Panel(
        "[bold cyan]NeuralWatch AI Interrogator[/bold cyan]\n"
        "Connected to Splunk via MCP Server v1.2\n"
        "Ask anything about your AI fleet (e.g. costs, latency, prompt security, compliance)",
        title="Agentic Interrogation Terminal",
        border_style="cyan"
    )
    console.print(welcome_panel)

    try:
        # Initialize agent with CLI logging callback
        agent = NeuralWatchAgent(callback_display_tool=display_tool_call)
    except Exception as e:
        console.print(f"[red]{SYM_ERR} Failed to connect to Splunk Management Port: {e}[/red]")
        sys.exit(1)

    while True:
        try:
            question = Prompt.ask("\n[bold cyan]Question[/bold cyan]")
            
            if not question.strip():
                continue
                
            if question.strip().lower() in ["exit", "quit"]:
                console.print("[yellow]Exiting interrogator CLI. Goodbye![/yellow]")
                break

            console.print("\n  [bold cyan]Querying Splunk via MCP...[/bold cyan]")
            
            answer = agent.answer(question)
                
            # Render synthesized answer panel
            answer_panel = Panel(
                answer,
                title="Answer",
                border_style="green",
                padding=(1, 2)
            )
            console.print(answer_panel)

        except KeyboardInterrupt:
            console.print("\n[yellow]Interrupted by user. Exiting...[/yellow]")
            break
        except Exception as e:
            console.print(f"[red]{SYM_ERR} An error occurred: {e}[/red]")

if __name__ == "__main__":
    run_cli()
