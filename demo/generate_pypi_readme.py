import re

def main():
    readme_path = "README.md"
    pypi_readme_path = "README_PYPI.md"
    
    with open(readme_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    # 1. Replace Architecture Overview
    arch_mermaid = """```mermaid
graph TD
    subgraph Client Application [Client Application Namespace]
        App[Your Application]
        SDK[neuralwatch_sdk]
        App -->|chat.completions.create| SDK
    end

    subgraph SDK Internals [SDK Engine]
        Inst[instrumentor<br/>Patches OpenAI/Claude]
        Cost[cost_estimator<br/>USD Pricing lookup]
        Fwd[forwarder<br/>Queue-backed async thread]
        SDK --> Inst
        Inst --> Cost
        Cost --> Fwd
    end

    subgraph Splunk Enterprise [Splunk Log Analytics]
        HEC[HTTP Event Collector]
        Index1[(neuralwatch_ai_calls)]
        Index2[(neuralwatch_injections)]
        Fwd -->|HTTPS HEC| HEC
        HEC --> Index1
        HEC --> Index2
    end

    subgraph User Interface [Telemetry Dashboards]
        Dash1[AI Fleet Observatory]
        Dash2[Prompt Injection Sentinel]
        Dash3[EU AI Act Compliance]
        MCP[MCP Query Agent]
        Index1 --> Dash1
        Index2 --> Dash2
        Index1 & Index2 --> Dash3
        MCP -->|SPL Query via API| Index1
    end
```"""

    arch_ascii = """```
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
```"""
    content = content.replace(arch_mermaid, arch_ascii)

    # 2. Replace Module A Flow
    sentinel_mermaid = """```mermaid
flowchart LR
    Prompt[User Prompt] -->|Intercepted by SDK| Classify[foundation_sec_classify.py]
    Classify --> Pattern{Pattern Match?}
    Pattern -->|'ignore all previous...' / DAN mode| High[Critical / High Risk]
    Pattern -->|'bypass input validation' / XSS| Med[Medium Risk]
    Pattern -->|Benign requests| Low[Low Risk]
    High & Med & Low -->|Assign Injection Score 0.0 - 1.0| Score[Telemetry Event]
    Score -->|Route to neuralwatch_injections| Index[(Splunk Index)]
    Index --> Dash[Prompt Injection Sentinel Dashboard]
```"""

    sentinel_ascii = """```
User Prompt ──► SDK Interception ──► Heuristic Classifier (foundation_sec_classify.py)
                                           │
                                  Assign Risk Level
                     [LOW (0.05-0.20) / MEDIUM / HIGH / CRITICAL (0.93-0.98)]
                                           │
                                           ▼
                                 neuralwatch_injections Index
                                           ▼
                                 Splunk Security Sentinel Dashboard
```"""
    content = content.replace(sentinel_mermaid, sentinel_ascii)

    # 3. Replace Module B Flow
    mcp_mermaid = """```mermaid
flowchart TD
    User[User Question: 'How much did we spend on GPT-4o?'] -->|Input| Gen[spl_generator.py<br/>NL to SPL Compiler]
    Gen -->|Generated SPL Query| Client[mcp_client.py<br/>Splunk SDK Runner]
    Client -->|API Request| Splunk[(neuralwatch_ai_calls)]
    Splunk -->|Raw Results JSON| Synth[agent.py<br/>LLM Synthesizer]
    Synth -->|Formatted Summary| Out[User Response: 'GPT-4o cost $12.47 across 3 services...']
```"""

    mcp_ascii = """```
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
```"""
    content = content.replace(mcp_mermaid, mcp_ascii)

    # 4. Replace Compliance Scoring Model
    compliance_mermaid = """```mermaid
graph TD
    subgraph Adherence [EU AI Act Compliance Scoring Model]
        Art9[Art. 9: Risk Management<br/>100 - high_incidents * 5]
        Art13[Art. 13: Transparency<br/>100 if disclosure_enabled = 1, else 0]
        Art14[Art. 14: Human Oversight<br/>100 if no review, else threshold * 100]
        Art17[Art. 17: Quality Management<br/>1 - error_rate * 100]
        Art72[Art. 72: Systemic Risk<br/>90 Adjusted by Latency Drift]
    end
    Art9 & Art13 & Art14 & Art17 & Art72 -->|Average| Score[Overall Compliance Score]
    Score --> Threshold{Score Threshold}
    Threshold -->|Score >= 90| Comp[✅ COMPLIANT]
    Threshold -->|Score >= 70| Risk[⚠️ AT RISK]
    Threshold -->|Score < 70| Non[❌ NON-COMPLIANT]
```"""

    compliance_ascii = """```
Article 9 (Risk Management)     ──┐
Article 13 (Transparency)       ──┼─► Overall Score = (Art9+Art13+Art14+Art17+Art72)/5
Article 14 (Human Oversight)    ──┤
Article 17 (Quality Management) ──┤            │
Article 72 (Systemic Risk)      ──┘            ▼
                                    Score >= 90: ✅ COMPLIANT
                                    Score >= 70: ⚠️ AT RISK
                                    Score < 70:  ❌ NON-COMPLIANT
```"""
    content = content.replace(compliance_mermaid, compliance_ascii)

    # 5. Replace Sequence Diagram
    seq_mermaid = """```mermaid
sequenceDiagram
    participant App as Your Application
    participant SDK as neuralwatch_sdk
    participant Queue as Background Queue
    participant HEC as Splunk HEC
    participant Splunk as Splunk Indexes
    participant Dashboard as Dashboards

    App->>SDK: client.chat.completions.create(...)
    SDK->>SDK: Extract model, tokens, latency, cost
    SDK->>SDK: Hash prompt text
    SDK->>Queue: Enqueue AICallEvent (non-blocking)
    SDK->>Queue: Enqueue PromptEvent (if capture_prompts=True)
    SDK->>App: Return API response (zero added latency)

    Queue-->>HEC: POST /services/collector/event
    HEC-->>Splunk: Index neuralwatch_ai_calls
    HEC-->>Splunk: Index neuralwatch_injections

    Dashboard->>Splunk: SPL Query (every 15s)
    Splunk-->>Dashboard: Aggregated results
    Dashboard-->>Dashboard: Render live charts
```"""

    seq_ascii = """```
1. Application calls OpenAI client completion method.
2. Instrumented SDK extracts token counts, latency, and computes cost.
3. SDK hashes prompts and enqueues events asynchronously in background queue.
4. SDK returns the API response instantly (zero-latency overhead).
5. Background thread batches and POSTs events to Splunk HTTP Event Collector (HEC).
6. Splunk indexes events in 'neuralwatch_ai_calls' and 'neuralwatch_injections'.
7. Live dashboards query Splunk every 15 seconds to update charts.
```"""
    content = content.replace(seq_mermaid, seq_ascii)
    
    with open(pypi_readme_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Successfully generated README_PYPI.md")

if __name__ == "__main__":
    main()
