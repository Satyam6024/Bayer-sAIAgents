import json
import uuid
from pathlib import Path
from datetime import datetime, timezone

DATA_DIR = Path(__file__).parent / "mock_data"


# Helpers

def uid():
    return uuid.uuid4().hex[:8]

def now():
    return datetime.now(timezone.utc).isoformat()

def log(step, phase, msg, **kw):
    print(f"  [{step:02d}] [{phase}] {msg}")
    for k, v in kw.items():
        print(f"--> {k}: {v}")

def load_json(name):
    with open(DATA_DIR / name) as f:
        return json.load(f)


# SIMULATED SPECIALIST FINDINGS
# In real system these come from SharedState after parallel run.

SPECIALIST_FINDINGS = {
    "logs_agent": [
        {"title": "Java OutOfMemoryError in payment-service",       "severity": "P1_CRITICAL", "confidence": 0.97, "evidence": {"heap_mb": 3891, "threads": 847}},
        {"title": "DB connection pool fully exhausted",              "severity": "P1_CRITICAL", "confidence": 0.95, "evidence": {"active": 200, "pending": 1847}},
        {"title": "Cascading failure: order → payment-service",      "severity": "P2_HIGH",     "confidence": 0.92, "evidence": {"error_503": 1412, "success_pct": 6}},
        {"title": "Expired TLS certificate blocking DB connections", "severity": "P2_HIGH",     "confidence": 0.98, "evidence": {"expired": "2026-02-05T23:59:59Z"}},
        {"title": "Thread deadlock in batch processor",              "severity": "P2_HIGH",     "confidence": 0.94, "evidence": {"threads": ["worker-14", "worker-22"]}},
        {"title": "Critical slow query — missing index",             "severity": "P2_HIGH",     "confidence": 0.96, "evidence": {"rows": 2800000, "time_ms": 45200}},
    ],
    "metrics_agent": [
        {"title": "Memory leak confirmed — OOM every ~14 min",  "severity": "P1_CRITICAL", "confidence": 0.96, "evidence": {"rate_mb_min": 95, "gc_pct": 78}},
        {"title": "P99 latency spike: 1200→25000ms (20.8x)",    "severity": "P1_CRITICAL", "confidence": 0.98, "evidence": {"start": 1200, "peak": 25000}},
        {"title": "Error rate surged to 94.2%",                  "severity": "P1_CRITICAL", "confidence": 0.97, "evidence": {"baseline": 2.1, "peak": 94.2}},
        {"title": "DB pool saturated — 1847 queued",             "severity": "P1_CRITICAL", "confidence": 0.95, "evidence": {"active": 200, "pending": 1847}},
        {"title": "2 pods critical — 33% capacity",              "severity": "P1_CRITICAL", "confidence": 0.99, "evidence": {"healthy_pct": 33, "circuit": "OPEN"}},
    ],
    "deploy_intel": [
        {"title": "v2.14.0 introduced unbounded in-memory queue",   "severity": "P1_CRITICAL", "confidence": 0.98, "evidence": {"queue": "in_memory_unbounded"}},
        {"title": "Circuit breaker threshold raised 50%→70%",        "severity": "P2_HIGH",     "confidence": 0.90, "evidence": {"old": 50, "new": 70}},
        {"title": "Certificate rotation partial failure",            "severity": "P2_HIGH",     "confidence": 0.97, "evidence": {"stale_pods": 2}},
        {"title": "3x traffic spike from Flash Sale",                "severity": "P2_HIGH",     "confidence": 0.93, "evidence": {"multiplier": 3}},
        {"title": "DB index rebuild cancelled during maintenance",   "severity": "P2_HIGH",     "confidence": 0.91, "evidence": {"index": "idx_transactions_status_created_at"}},
    ],
}

# CORRELATION RULES
# (title, description, keywords_to_match, confidence)

CORRELATION_RULES = [
    ("Memory Leak ↔ Unbounded Queue Config",
     "v2.14.0 unbounded queue + 4x threads → OOM at batchAllocate → 95 MiB/min leak.",
     ["memory", "oom", "unbounded"], 0.97),
    ("Slow Queries ↔ Missing Index ↔ Pool Exhaustion",
     "Cancelled index → full table scans 38-45s → 200 connections held → 1847 queued.",
     ["index", "pool", "connection", "slow query"], 0.95),
    ("Traffic Spike × Degraded Capacity = Cascade",
     "3x Flash Sale traffic hit 33% capacity. Raised circuit breaker delayed cutoff.",
     ["traffic", "capacity", "circuit", "cascading"], 0.93),
    ("Stale TLS ↔ Cert Rotation ↔ Canary Failure",
     "Partial cert rotation left canary with expired cert. Cannot connect to DB.",
     ["tls", "cert"], 0.96),
]

class CommanderAgent:

    def __init__(self, alert: dict):
        self.alert = alert
        self.step = 0
        self.severity = "P4_LOW"
        self.findings = []
        self.correlations = []
        self.plan = {}
        self.tasks = []
        self.rca = {}

    def _log(self, phase, msg, **kw):
        self.step += 1
        log(self.step, phase, msg, **kw)

    # JOB 1: TRIAGE
    def triage(self):
        print("JOB 1: TRIAGE")

        self._log("ALERT", "Incoming alert",
                  source=self.alert["source"],
                  title=self.alert["title"],
                  severity=self.alert["severity"])

        self.severity = "P1_CRITICAL" if self.alert["severity"] == "P1" else "P2_HIGH"
        self._log("TRIAGE", f"Severity: {self.severity}")

        # Load data
        for name in ["application_logs.json", "infrastructure_metrics.json", "deployment_history.json"]:
            load_json(name)
            self._log("DATA", f"Loaded {name}")

        # Plan
        self.plan = {
            "hypothesis": "payment-service degradation — memory leak, deploy regression, or infra failure",
            "tasks": {
                "logs_agent":    "Find OOM errors, pool exhaustion, stack traces, cascading failures",
                "metrics_agent": "Analyze memory leak, latency, error rates, DB pool, pod health",
                "deploy_intel":  "Map deployments + infra changes against incident timeline",
            },
        }
        self._log("PLAN", "Investigation plan created",
                  hypothesis=self.plan["hypothesis"])

        # Dispatch
        for agent, objective in self.plan["tasks"].items():
            self.tasks.append({"id": f"msg-{uid()}", "to": agent, "objective": objective})
            self._log("DISPATCH", f"Task → {agent}", objective=objective[:70])

    # COLLECT FINDINGS

    def collect_findings(self):
        print(" COLLECTING SPECIALIST FINDINGS")

        for agent, items in SPECIALIST_FINDINGS.items():
            for f in items:
                f["id"] = f"find-{uid()}"
                f["agent"] = agent
                self.findings.append(f)
            self._log("COLLECT", f"{agent}: {len(items)} findings")

        self._log("COLLECT", f"Total: {len(self.findings)} findings")

    # JOB 2: CORRELATE
    def correlate(self):
        print("JOB 2: CORRELATE")

        self._log("CORRELATE", f"Cross-referencing {len(self.findings)} findings")

        for title, desc, keywords, conf in CORRELATION_RULES:
            linked = [f["id"] for f in self.findings
                      if any(kw in f["title"].lower() for kw in keywords)]
            if len(linked) >= 2:
                self.correlations.append({"id": f"corr-{uid()}", "title": title,
                                          "description": desc, "linked": linked, "confidence": conf})
                self._log("CORRELATE", title, linked=len(linked), confidence=conf)

        self._log("CORRELATE", f"Built {len(self.correlations)} correlations")

    # JOB 3: BUILD RCA
    def build_rca(self):
        print("JOB 3: BUILD RCA")

        self._log("RCA", "Building Root Cause Analysis")

        self.rca = {
            "id": f"rca-{uid()}", "timestamp": now(), "severity": "P1_CRITICAL",
            "summary": (
                "COMPOUND FAILURE: v2.14.0 unbounded queue + 4x threads → 95 MiB/min leak → "
                "OOM every ~14 min. Compounded by missing DB index, partial TLS cert failure, "
                "3x traffic spike, raised circuit breaker."
            ),
            "root_causes": [
                {"rank": 1, "title": "Unbounded in-memory queue in v2.14.0",
                 "detail": "kafka_backed→in_memory_unbounded. Threads 200→800. JVM=K8s limit.",
                 "confidence": 0.97, "category": "deployment_regression"},
                {"rank": 2, "title": "Missing DB index — full table scans",
                 "detail": "Index rebuild cancelled. 2.8M row scans at 38-45s each.",
                 "confidence": 0.95, "category": "infrastructure_gap"},
            ],
            "contributing_factors": [
                "3x traffic from Flash Sale",
                "Partial TLS cert rotation — canary can't reach DB",
                "Circuit breaker raised 50%→70%",
                "JVM heap 4Gi = K8s limit (no GC headroom)",
                "Deadlocks in batch processor",
            ],
            "timeline": [
                {"t": "Feb5 10:00", "e": "DB index rebuild cancelled"},
                {"t": "Feb5 16:00", "e": "TLS cert rotation PARTIAL FAILURE"},
                {"t": "Feb5 20:00", "e": "Circuit breaker → 70%"},
                {"t": "Feb5 22:30", "e": "v2.14.0 canary deployed (15%)"},
                {"t": "Feb6 06:00", "e": "Flash Sale push sent"},
                {"t": "Feb6 07:45", "e": "3x traffic spike"},
                {"t": "Feb6 07:48", "e": "First OOMKill"},
                {"t": "Feb6 08:00", "e": "⚠ INCIDENT — 503s at gateway"},
                {"t": "Feb6 08:04", "e": "CrashLoopBackOff"},
                {"t": "Feb6 08:06", "e": "DB pool exhausted"},
                {"t": "Feb6 08:13", "e": "33% capacity, circuit OPEN"},
            ],
            "remediation": [
                {"p": "IMMEDIATE",  "action": "Rollback to v2.13.2",       "cmd": "kubectl rollout undo deployment/payment-service",  "risk": "LOW"},
                {"p": "IMMEDIATE",  "action": "Rebuild missing DB index",  "cmd": "CREATE INDEX CONCURRENTLY idx_transactions_status_created_at ON transactions(status,created_at);", "risk": "LOW"},
                {"p": "IMMEDIATE",  "action": "Rotate TLS certs",          "cmd": "kubectl rollout restart deployment/payment-service", "risk": "LOW"},
                {"p": "SHORT_TERM", "action": "Circuit breaker → 50%",     "cmd": "circuit_breaker.error_threshold_pct=50",             "risk": "LOW"},
                {"p": "SHORT_TERM", "action": "K8s memory → 5Gi",          "cmd": "kubectl set resources ... --limits=memory=5Gi",      "risk": "MEDIUM"},
                {"p": "PREVENTIVE", "action": "Bounded queue for v2.14.0", "cmd": "BlockingQueue(capacity=10000)",                      "risk": "CODE_REVIEW"},
            ],
            "blast_radius": ["payment-service (94%)", "order-service", "api-gateway", "notification-service", "end users"],
        }

        self._log("RCA", "Summary", severity=self.rca["severity"])
        for rc in self.rca["root_causes"]:
            self._log("RCA", f"#{rc['rank']} {rc['title']}", confidence=rc["confidence"])
        self._log("RCA", f"{len(self.rca['contributing_factors'])} contributing factors")
        self._log("RCA", f"{len(self.rca['timeline'])} timeline events")
        for r in self.rca["remediation"]:
            self._log("RCA", f"[{r['p']}] {r['action']}", risk=r["risk"])
        self._log("RCA", "Complete")


    def run(self):
        print("COMMANDER AGENT — Standalone Run")

        self.triage()
        self.collect_findings()
        self.correlate()
        self.build_rca()

        print(f" DONE — {self.step} steps")
        print(f" Findings:{len(self.findings)} | Correlations:{len(self.correlations)} | Remediations:{len(self.rca['remediation'])}")
        return self.rca



if __name__ == "__main__":

    alert = {
        "source": "PagerDuty",
        "title": "payment-service: P99 latency > 10s, error rate > 80%",
        "severity": "P1",
        "affected_service": "payment-service",
    }

    print("ALERT: payment-service P1_CRITICAL...")

    rca = CommanderAgent(alert).run()

    # Summary box
    print("\n ROOT CAUSE ANALYSIS...")
    for rc in rca["root_causes"]:
        print(f"  #{rc['rank']}. {rc['title']:<46}")
    for r in rca["remediation"]:
        if r["p"] == "IMMEDIATE":
            print(f"  > {r['action']:<46}")

    # Save
    out = Path(__file__).parent / "output"
    out.mkdir(exist_ok=True)
    with open(out / "commander_log.json", "w") as f:
        json.dump({"alert": alert, "rca": rca}, f, indent=2)
    print(f"\n  Saved: {out / 'commander_log.json'}")