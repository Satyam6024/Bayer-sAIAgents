# Multi-Agent Root Cause Analysis System

A distributed system of **three specialized AI agents** built from scratch that work together to diagnose infrastructure incidents, analyze logs, and resolve critical production issues. Each agent operates **independently** yet collaboratively to provide comprehensive root cause analysis.

---

## 🎯 System Overview

This project demonstrates **autonomous agent-based incident response** where:
- **Logs Agent** → Analyzes application and system logs to surface errors, failures, and stack traces
- **Metrics Agent** → Examines infrastructure metrics (CPU, memory, latency, error rates) to detect anomalies  
- **Commander Agent** → Orchestrates the investigation, correlates findings, and produces a comprehensive Root Cause Analysis (RCA)

All three agents are **built from scratch** (no framework dependencies) and can run **standalone or in coordination** to provide deep investigative insights.

---

## 📋 The Three Agents

### 1. **Logs Agent** (`logs_agent.py`)
**Purpose:** Extract actionable findings from raw application and structured logs

**What it does:**
- Searches for critical errors (OutOfMemoryError, connection pool exhaustion, TLS cert failures)
- Identifies cascading failures and service dependencies
- Extracts stack traces and thread deadlocks
- Correlates error patterns across services
- Produces **severity-ranked findings** with confidence scores

**Typical Findings:**
- `Java OutOfMemoryError in payment-service` (P1_CRITICAL, 0.97 confidence)
- `DB connection pool fully exhausted` (P1_CRITICAL, 0.95 confidence)
- `Cascading failure: order → payment-service` (P2_HIGH, 0.92 confidence)
- `Thread deadlock in batch processor` (P2_HIGH, 0.94 confidence)

---

### 2. **Metrics Agent** (`metrics_agent_standalone.py`)
**Purpose:** Detect anomalies and degradation patterns in infrastructure metrics

**What it does:**
- Monitors memory leak progression and garbage collection overhead
- Tracks P99 latency spikes and error rate surges
- Analyzes database connection pool saturation
- Assesses pod health and resource constraints
- Identifies correlation between metrics-level root causes

**Typical Findings:**
- `Memory leak confirmed — OOM every ~14 min` (P1_CRITICAL, 0.96 confidence)
- `P99 latency spike: 1200→25000ms (20.8x)` (P1_CRITICAL, 0.98 confidence)
- `Error rate surged to 94.2%` (P1_CRITICAL, 0.97 confidence)
- `DB pool saturated — 1847 queued` (P1_CRITICAL, 0.95 confidence)

---

### 3. **Commander Agent** (`commander_agent.py`)
**Purpose:** Orchestrate investigation and synthesize comprehensive RCA

**What it does:**
- Receives an alert (PagerDuty-style incident notification)
- Triggers parallel analysis by Logs and Metrics agents
- Correlates findings from all sources (logs, metrics, deployment history)
- Ranks root causes by likelihood and impact
- Recommends immediate and preventive actions
- Produces comprehensive RCA document with timeline and remediation

**RCA Output includes:**
```
Root Causes (ranked by confidence):
  #1 v2.14.0 introduced unbounded in-memory queue (0.98 confidence)
  #2 Circuit breaker threshold raised 50%→70% (0.90 confidence)
  
Contributing Factors:
  - 3x traffic spike from Flash Sale
  - Certificate rotation partial failure
  - Pod restart loops and resource constraints
  
Remediation:
  [IMMEDIATE] Rollback v2.14.0 to v2.13.2
  [IMMEDIATE] Manually scale DB connection pool +500
  [SHORT-TERM] Apply bounded queue fix in code review
```

---

## 🚀 Running the Agents

### Prerequisites
```bash
# No external dependencies! Agents use only Python standard library
python --version  # Python 3.7+
```

### Run Individual Agents (Standalone)

#### **Run Logs Agent**
```bash
cd allStandaloneAgents
python logs_agent.py
```

**Output:**
- Console logs showing each analysis step with `[STEP]` markers
- Structured findings with severity, confidence, and evidence
- JSON report saved to `output/logs_agent_log.json`

---

#### **Run Metrics Agent**
```bash
cd allStandaloneAgents
python metrics_agent_standalone.py
```

**Output:**
- Step-by-step analysis of memory, latency, error rates, and pod health  
- P1/P2 findings with supporting evidence
- JSON report saved to `output/metrics_agent_log.json`

---

#### **Run Commander Agent (Orchestrator)**
```bash
cd allStandaloneAgents
python commander_agent.py
```

**Output:**
- Triage of incoming alert
- Correlation of findings from all agents
- Complete RCA with root causes, timeline, and remediation steps
- JSON report saved to `output/commander_log.json`

---

### View Results
All agent outputs are saved as structured JSON:
```bash
cat output/logs_agent_log.json      # Logs Agent findings
cat output/metrics_agent_log.json   # Metrics Agent findings
cat output/commander_log.json       # Commander RCA synthesis
```

---

## 📊 Mock Data Structure

The system uses **realistic production-like mock data** to simulate a real infrastructure incident. Three datasets are provided:

### 1. **application_logs.json** 
**Location:** `allStandaloneAgents/mock_data/application_logs.json`

**Contains:**
- 222+ structured log entries from microservices
- **Services:** `payment-service`, `api-gateway`, `order-service`, `database-layer`
- **Log Levels:** ERROR, WARN, INFO, DEBUG
- **Critical Messages:**
  - Java OutOfMemoryError with heap size and thread count
  - Connection pool exhaustion (200 active, 1847 pending)
  - TLS certificate expiration blocking DB connections
  - SQL query timeouts (missing indexes)
  - API gateway circuit breaker state transitions

**Example Entry:**
```json
{
  "id": "log-0002",
  "timestamp": "2026-02-06T08:00:14.892Z",
  "service": "payment-service",
  "level": "ERROR",
  "message": "java.lang.OutOfMemoryError: Java heap space",
  "metadata": {
    "heap_mb": 3891,
    "threads": 847,
    "gc_pct": 95
  }
}
```

---

### 2. **infrastructure_metrics.json**
**Location:** `allStandaloneAgents/mock_data/infrastructure_metrics.json`

**Contains:**
- Time-series metrics collected every **60 seconds** over a **15-minute window**
- **Metrics per Service:**
  - **CPU:** limit (2000 millicores), usage timeseries
  - **Memory:** limit (4096 MB), timeseries, leak analysis with rate
  - **Latency:** P50, P95, P99 with per-second values
  - **Error Rate:** baseline vs. peak measurements
  - **Database Pool:** active connections, pending queue, slow query count
- **Pod Status:** CrashLoopBackOff, RestartCount metrics

**Example Metrics:**
```json
{
  "pod": "pay-pod-9b1e",
  "status": "CrashLoopBackOff",
  "restart_count": 4,
  "memory": {
    "timeseries": [
      {"t": "08:00", "value": 2870},
      {"t": "08:01", "value": 3045},
      ...
    ],
    "leak_analysis": {
      "leak_detected": true,
      "leak_rate_mb_per_min": 95,
      "gc_overhead_pct": 78
    }
  }
}
```

---

### 3. **deployment_history.json**
**Location:** `allStandaloneAgents/mock_data/deployment_history.json`

**Contains:**
- **151 records** spanning 32-hour window (2026-02-05 → 2026-02-06)
- **Release Information:**
  - Version numbers (v2.13.1, v2.13.2, v2.14.0, etc.)
  - Deployment types: rolling_update, canary, blue-green
  - Trigger reasons: hotfix, scheduled_release, security_patch
  - Author information (commit history)
  - Rollback availability
- **Configuration Changes:**
  - Circuit breaker thresholds (50% → 70%)
  - Connection pool settings
  - Message queue configurations
  - TLS certificate rotations
- **Changelog:**
  - FIX: Corrected decimal rounding in EUR transactions
  - FIX: Updated retry logic for payment gateway
  - FEAT: Unbounded in-memory queue (root cause!)

**Example Deployment:**
```json
{
  "id": "deploy-002",
  "timestamp": "2026-02-05T22:30:00Z",
  "service": "payment-service",
  "version": "v2.14.0",
  "previous_version": "v2.13.2",
  "type": "canary",
  "canary_weight_pct": 15,
  "changelog": [
    "FEAT: Add unbounded in-memory transaction buffer",
    "FIX: Retry logic improvements"
  ]
}
```

---

## ✅ Why Mock Data is Ideal for Testing

### 1. **Realistic Incident Scenario** 
The mock data simulates a **genuine production outage** with cascading failures:
- A bad deployment (v2.14.0) introduces an unbounded queue → memory leak
- Memory leak → OOM every ~14 minutes
- OOM → pod restarts → service unavailability
- Cascading failures → 94.2% error rate across payment processing
- Traffic spike (3x) during Flash Sale exacerbates the issue
- Expired TLS cert blocks DB recovery attempts

This **end-to-end narrative** tests agent reasoning across multiple failure domains.

---

### 2. **Multi-Domain Coverage**
Agents must correlate findings across **4 distinct data sources:**
- **Logs:** Error messages, stack traces, service interactions
- **Metrics:** Resource usage, latency, error rates over time
- **Deployments:** Version changes that correlate with incident timing
- **Pod Health:** Restart counts, status changes, resource constraints

This prevents **false positives** and tests holistic incident understanding.

---

### 3. **Confidence & Evidence Testing**
Each finding includes:
- **Severity levels** (P1_CRITICAL, P2_HIGH, P3_MEDIUM)
- **Confidence scores** (0.90 → 0.99 range)
- **Supporting evidence** (concrete metrics, log IDs, timeseries data)

This allows validation that:
- High-confidence findings have strong supporting evidence
- Agents cite specific sources (log IDs, metric values, deployment IDs)
- Risk assessments match actual impact scope

---

### 4. **Root Cause Isolation Testing**
Mock data includes **multiple overlapping symptoms** to test agent discrimination:
- Both memory leak AND circuit breaker misconfiguration caused high latency
- Both pod restarts AND traffic spike caused error rate spike
- Both TLS cert expiration AND connection pool exhaustion caused DB timeouts

Agents must rank root causes by probability and causality, not just feature matching.

---

### 5. **Timeline & Correlation Testing**
Timestamps across all datasets are **carefully synchronized**:
- Deployment of v2.14.0 at `2026-02-05T22:30:00Z`
- Memory metrics show leak progression starting within minutes
- Error spike in logs appears 8 minutes after deployment
- Pod restart loop begins ~14 minutes after OOM

This tests agent ability to:
- Correlate events across time windows
- Identify causal sequences (deployment → metric change → errors)
- Reject coincidental correlations

---

### 6. **Scalability & Performance Testing**
Mock datasets contain realistic volume:
- **222 log entries** (typical 15-min production window)
- **166 metric datapoints** (granular 60-second intervals × 15 min × multiple services)
- **151 deployment records** (historical context across 32 hours)
- **Multiple services** (payment, order, api-gateway, database)

Agents must process this volume efficiently without fetching irrelevant data.

---

### 7. **Remediation Quality Testing**
The mock data supports validation of recommended actions:
- **Immediate actions** (rollback, scaling) map to actual deployment history
- **Short-term fixes** (queue bounds) appear in version control
- **Preventive measures** (monitoring thresholds, tests) address root cause, not symptom

---

## 📁 Project Structure

```
Bayers_hackathon/
├── README.md                              # This file
├── requirements.txt                       # Python dependencies (minimal)
├── pyproject.toml                         # Project metadata
│
└── allStandaloneAgents/
    ├── commander_agent.py                 # Commander: Orchestrates investigation
    ├── logs_agent.py                      # Logs: Analyzes application logs
    ├── metrics_agent_standalone.py        # Metrics: Analyzes infrastructure metrics
    │
    ├── mock_data/
    │   ├── application_logs.json          # 222 structured log entries
    │   ├── infrastructure_metrics.json    # Time-series metrics (CPU, memory, latency)
    │   └── deployment_history.json        # 151 deployment records
    │
    └── output/
        ├── commander_log.json             # RCA synthesis output
        ├── logs_agent_log.json            # Logs agent findings
        └── metrics_agent_log.json         # Metrics agent findings
```

---

## 🔄 Agent Architecture

### Design Principles
- **No Frameworks:** Pure Python, standard library only
- **Modular:** Each agent operates independently with clear interfaces
- **Observable:** Detailed step-by-step logging visible during execution  
- **Structured Output:** All findings as JSON with evidence and confidence
- **Composable:** Agents can run standalone OR orchestrated by Commander

### Agent Lifecycle
```
1. receive_task()    → Accept investigation objective
2. ingest_data()     → Load relevant data subset
3. analyze_*()       → Domain-specific analysis (domain-specific methods)
4. correlate()       → Cross-reference findings
5. build_message()   → Prepare output for consumers
6. run()             → Execute full pipeline
```

---

## 🎓 Example Walkthrough

### Run a Full Investigation
```bash
cd allStandaloneAgents
python commander_agent.py
```

**Console Output (abridged):**
```
COMMANDER AGENT — Standalone Run
  [01] [TRIAGE] Alert received: payment-service P1_CRITICAL
  [02] [DISPATCH] Loading Logs Agent...
  [03] [DISPATCH] Loading Metrics Agent...
  [04] [ANALYZE] Logs Agent: 6 findings discovered
  [05] [ANALYZE] Metrics Agent: 5 findings discovered
  [06] [CORRELATE] Comparing 11 findings across 3 sources
  [07] [RCA] Building causality graph...
  
ROOT CAUSE ANALYSIS...
  #1. v2.14.0 introduced unbounded in-memory queue
  #2. Circuit breaker threshold raised 50%→70%
  #3. 3x traffic spike from Flash Sale
  
REMEDIATION...
  > Rollback v2.14.0 to v2.13.2
  > Manually scale DB connection pool +500
  > Apply bounded queue fix in code review
  
  Saved: output/commander_log.json
```

### Inspect Individual Findings
```bash
cat output/commander_log.json | python -m json.tool
```

**Sample Finding (from JSON):**
```json
{
  "id": "find-a7f3c291",
  "agent": "metrics_agent",
  "timestamp": "2026-02-06T08:15:00Z",
  "title": "Memory leak confirmed — OOM every ~14 min",
  "description": "Heap memory grows at 95 MB/min with 78% GC overhead",
  "severity": "P1_CRITICAL",
  "confidence": 0.96,
  "evidence": {
    "leak_rate_mb_min": 95,
    "gc_pct": 78,
    "pod_restarts": 4,
    "crash_pattern": "every ~14 minutes"
  }
}
```

---

## 🔍 Key Insights from Mock Data

The incident scenario encapsulates **5 interconnected failures:**

| Root Cause | Trigger | Signal | Evidence |
|-----------|---------|--------|----------|
| **Unbounded queue** | v2.14.0 deployment | Memory leak (95 MB/min) | `deployment_history.json` |
| **High traffic** | Flash Sale event | 3x throughput spike | `infrastructure_metrics.json` |
| **Circuit breaker misconfiguration** | Threshold raised to 70% | P99 latency 20.8x increase | `infrastructure_metrics.json` |
| **TLS cert expiration** | Cert rotation partial failure | DB connection timeouts | `application_logs.json` |
| **Pod resource constraints** | OOM from leak + traffic | Restart loop (CrashLoopBackOff) | `infrastructure_metrics.json` |

Agents must **independently identify** these factors and **collaboratively rank** them by causality.

---

## 🛠️ Extending the System

### Add a New Agent
```python
class MyCustomAgent:
    def __init__(self, raw_data: dict, task: dict):
        self.raw_data = raw_data
        self.task = task
        self.findings = []
        
    def analyze(self):
        # Implement domain-specific logic
        pass
        
    def run(self):
        self.receive_task()
        self.ingest_data()
        self.analyze()
        return self.findings
```

### Add New Mock Data
1. Add JSON file to `mock_data/`
2. Update agent `ingest_data()` method to load it
3. Add analysis logic in domain-specific methods

---

## 📝 Notes

- **Python 3.7+** required (uses f-strings, pathlib)
- **No dependencies:** Agents use `json`, `uuid`, `pathlib`, `datetime` only
- **Deterministic:** All findings pre-computed (no LLM calls in standalone mode)
- **Extensible:** Easy to add new agents, data sources, or analysis logic

---

## 🤝 Contributing

To add features or improve agents:
1. Extend the relevant agent class
2. Add findings with structured evidence
3. Update mock data if testing new scenarios
4. Validate output JSON format
5. Update this README with new capabilities

---

**Version:** 1.0 | **Last Updated:** February 2026
