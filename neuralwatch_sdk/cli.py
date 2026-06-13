"""
Module: cli
Purpose: Typer CLI for NeuralWatch configuration, status inspection, and test event generation.
Part of: NeuralWatch — AI Fleet Observatory for Splunk
Hackathon: Splunk Agentic Ops 2026

Dependencies:
  - typer: CLI framework
  - rich: pretty console layouts
  - requests: HEC HTTP ping/validation
  - json, os: file handling and config mapping

Usage:
  Run 'neuralwatch --help' in terminal.
"""

import os
import json
import uuid
import time
import random
import requests
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

app = typer.Typer(name="neuralwatch", help="NeuralWatch CLI — AI Fleet Observatory for Splunk")
console = Console()

CONFIG_DIR = ".neuralwatch"
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")

def _load_config() -> dict:
    """Load configuration from local storage if present."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

@app.command(help="Initialize NeuralWatch in this project directory.")
def init(
    service: str = typer.Option(None, "--service", "-s", help="Name of the service (e.g. checkout-service)"),
    team: str = typer.Option(None, "--team", "-t", help="Team owning the service (e.g. payments)"),
    splunk_url: str = typer.Option(None, "--splunk-url", "-u", help="Splunk HEC URL endpoint"),
    hec_token: str = typer.Option(None, "--token", "-k", help="Splunk HEC authentication token", hide_input=True)
):
    # Prompt user if arguments are not provided
    if not service:
        service = typer.prompt("Enter Service Name (e.g., checkout-service)")
    if not team:
        team = typer.prompt("Enter Owning Team Name (e.g., payments-eng)")
    if not splunk_url:
        splunk_url = typer.prompt("Enter Splunk HEC URL", default="https://localhost:8088/services/collector/event")
    if not hec_token:
        hec_token = typer.prompt("Enter Splunk HEC Token", hide_input=True)

    console.print("[cyan][NeuralWatch] Validating Splunk HEC connectivity...[/cyan]")
    
    # Verify HEC connection
    headers = {"Authorization": f"Splunk {hec_token}"}
    test_payload = {
        "time": time.time(),
        "source": "neuralwatch_sdk",
        "sourcetype": "nw:ai_call",
        "index": "neuralwatch_ai_calls",
        "event": {
            "call_id": str(uuid.uuid4()),
            "service": service,
            "team": team,
            "model": "ping-test",
            "provider": "neuralwatch",
            "latency_ms": 1,
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0.0,
            "status": "success",
            "prompt_hash": ""
        }
    }

    try:
        # HEC uses SSL. Standard local setups have self-signed certs.
        # Disable SSL warnings & verification by default for local setup checks.
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        response = requests.post(splunk_url, json=test_payload, headers=headers, timeout=5.0, verify=False)
        if response.status_code == 200:
            console.print("[green]✔ HEC Connection Successful![/green]")
        else:
            console.print(f"[yellow]⚠ HEC responded with code {response.status_code}: {response.text}[/yellow]")
            console.print("[yellow]Continuing setup but verify Splunk settings later.[/yellow]")
    except Exception as e:
        console.print(f"[red]✖ HEC Connection Failed: {e}[/red]")
        console.print("[yellow]Continuing setup, please ensure Splunk is running on this port.[/yellow]")

    # Create config directory and config file
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        config = {
            "service": service,
            "team": team,
            "splunk_hec_url": splunk_url,
            "splunk_hec_token": hec_token,
            "capture_prompts": True,
            "verify_ssl": False
        }
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
        console.print(f"[green]✔ Config file created at {CONFIG_FILE}[/green]")
    except Exception as e:
        console.print(f"[red]✖ Failed to write config: {e}[/red]")
        raise typer.Exit(1)

    # Scaffold Splunk App templates if template folder is available
    scaffold_app_path = "splunk_app"
    try:
        os.makedirs(os.path.join(scaffold_app_path, "default"), exist_ok=True)
        os.makedirs(os.path.join(scaffold_app_path, "lookups"), exist_ok=True)
        os.makedirs(os.path.join(scaffold_app_path, "dashboards"), exist_ok=True)
        
        # Write basic app metadata files
        with open(os.path.join(scaffold_app_path, "default", "app.conf"), "w") as f:
            f.write(f"[launcher]\nauthor = NeuralWatch\ndescription = AI Observability for {service}\nversion = 0.1.0\n\n[ui]\nis_visible = 1\nlabel = NeuralWatch - {service}\n")
            
        console.print(f"[green]✔ Splunk app scaffolded successfully in ./{scaffold_app_path}[/green]")
    except Exception as e:
        console.print(f"[yellow]⚠ Failed to scaffold Splunk app: {e}[/yellow]")

    # Display Next Steps panel
    welcome_panel = Panel(
        "[bold green]NeuralWatch successfully initialized![/bold green]\n\n"
        "[bold]Next Steps:[/bold]\n"
        "1. Copy the scaffolded [cyan]splunk_app/[/cyan] directory to your Splunk apps folder:\n"
        "   [yellow]cp -r splunk_app $SPLUNK_HOME/etc/apps/neuralwatch[/yellow]\n"
        "2. Restart Splunk to load dashboards and configurations.\n"
        "3. Import [cyan]neuralwatch_sdk[/cyan] in your codebase:\n"
        "   [cyan]import neuralwatch_sdk[/cyan]\n"
        "   [cyan]neuralwatch_sdk.auto_instrument()[/cyan]",
        title="Setup Completed",
        border_style="green"
    )
    console.print(welcome_panel)

@app.command(help="Check NeuralWatch configuration and connection status.")
def status():
    config = _load_config()
    if not config:
        console.print("[red]✖ NeuralWatch has not been initialized in this folder. Run 'neuralwatch init' first.[/red]")
        raise typer.Exit(1)

    table = Table(title="NeuralWatch Settings", show_header=False, border_style="cyan")
    table.add_row("Service", config.get("service"))
    table.add_row("Team", config.get("team"))
    table.add_row("HEC Endpoint", config.get("splunk_hec_url"))
    token = config.get("splunk_hec_token", "")
    masked_token = token[:8] + "..." + token[-4:] if len(token) > 12 else "***"
    table.add_row("HEC Token", masked_token)
    table.add_row("SSL Verification", str(config.get("verify_ssl", False)))
    table.add_row("Capture Prompts", str(config.get("capture_prompts", True)))
    
    console.print(table)

@app.command(help="Generate 100 test events to verify the telemetry pipeline.")
def demo():
    config = _load_config()
    if not config:
        console.print("[red]✖ NeuralWatch not initialized. Run 'neuralwatch init' first.[/red]")
        raise typer.Exit(1)

    console.print("[cyan][NeuralWatch] Sending 100 test events to HEC...[/cyan]")
    
    # Configure forwarder parameters
    from neuralwatch_sdk.forwarder import configure as f_conf, send_event as f_send
    from neuralwatch_sdk.cost_estimator import estimate_cost
    import hashlib
    f_conf(config.get("splunk_hec_url"), config.get("splunk_hec_token"), config.get("verify_ssl", False))

    models = ["gpt-4o", "gpt-4o-mini", "claude-3-5-sonnet-20241022", "claude-sonnet-4-6"]
    providers = {"gpt-4o": "openai", "gpt-4o-mini": "openai", "claude-3-5-sonnet-20241022": "anthropic", "claude-sonnet-4-6": "anthropic"}
    
    success_count = 0
    for i in range(100):
        model = random.choice(models)
        provider = providers[model]
        input_tokens = random.randint(100, 2000)
        output_tokens = random.randint(50, 1000)
        latency = random.randint(150, 2500)
        cost = estimate_cost(model, input_tokens, output_tokens)
        call_id = str(uuid.uuid4())
        
        event = {
            "call_id": call_id,
            "service": config.get("service"),
            "team": config.get("team"),
            "model": model,
            "provider": provider,
            "latency_ms": latency,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": cost,
            "status": "success",
            "finish_reason": "stop",
            "prompt_hash": hashlib.sha256(f"test-prompt-{i}".encode()).hexdigest()[:16]
        }
        
        if f_send("neuralwatch_ai_calls", event):
            success_count += 1

    console.print(f"[green]✔ Enqueued {success_count}/100 events to background thread forwarder.[/green]")
    console.print("[cyan]Background thread is delivering the payloads asynchronously. Please check Splunk in a few moments.[/cyan]")

if __name__ == "__main__":
    app()
