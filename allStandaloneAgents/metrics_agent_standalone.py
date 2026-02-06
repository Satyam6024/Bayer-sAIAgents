import json
import uuid
from pathlib import Path
from datetime import datetime, timezone


# Helper
def uid():
    return uuid.uuid4().hex[:8]  # used for finding IDs and message IDs

def now():
    return datetime.now(timezone.utc).isoformat() 

def log(step, icon, phase, msg, **data):
    print(f"  [{step:02d}] {icon} [{phase}] {msg}")
    for k, v in data.items():
        print(f"-->{k}: {v}")



# METRICS AGENT
class MetricsAgent:  # Encapsulates all agent state + behavior

    def __init__(self, raw_metrics: dict, task: dict):
        self.raw_metrics = raw_metrics 
        self.task = task
        self.findings = []  # accumulates final conclusions
        self.step = 0

    def _log(self, icon, phase, msg, **data):  # wrapper around global log()
        self.step += 1
        log(self.step, icon, phase, msg, **data)

    def _add_finding(self, title, description, severity, confidence, evidence):  # Standardizes how findings are created
        finding = {
            "id": f"find-{uid()}",
            "agent": "metrics_agent",
            "timestamp": now(),
            "title": title,
            "description": description,
            "severity": severity,
            "confidence": confidence,
            "evidence": evidence,
            "related_services": ["payment-service"],
        }
        self.findings.append(finding)
        self._log("$", "FINDING", title, severity=severity, confidence=confidence)

    # Step 1: Receive Task
    def receive_task(self):  # Entry point for Commander
        self._log("i", "HANDOFF", "Received INVESTIGATION_TASK from Commander",
                  objective=self.task.get("objective"),  # what to analyze, which metrics matter
                  key_metrics=self.task.get("key_metrics"))

    # Step 2: Ingest Data
    def ingest_data(self):  # loads only relevant slices of telementry
        self._log("i", "INGEST", "Loading payment-service metrics from SharedState")

        svc = self.raw_metrics.get("services", {}).get("payment-service", {})

        # if fails it prevents reasoning on missing data
        if not svc:
            self._log("!", "INGEST", "payment-service not found — aborting")
            return False

        # Extract all sub-objects at once
        self.pods = svc.get("pods", {})  # pod list
        self.pod = self.pods.get("pay-pod-9b1e", {})  # select primary pod for deep analysis
        self.mem = self.pod.get("memory", {})  # memory metrics used for leak detection
        self.latency = svc.get("latency", {}).get("timeseries", [])  # latency signals
        self.error_rate = svc.get("error_rate", {}).get("timeseries", [])  # error rate signals
        self.db = svc.get("database", {})  # database health (pool, slow queries)

        # Gateway upstream (secondary source)
        gw = self.raw_metrics.get("services", {}).get("api-gateway", {})
        self.upstream = gw.get("upstream_health", {}).get("payment-service", {})

        self._log("1", "INGEST", "Data loaded",  # act as schema validation i.e. summarize ingestion success
                  pods=len(self.pods),
                  pod_status=self.pod.get("status"),
                  has_memory=bool(self.mem),
                  has_latency=bool(self.latency),
                  has_errors=bool(self.error_rate),
                  has_db=bool(self.db.get("connection_pool")))
        return True

    # Step 3A: Memory Leak
    def check_memory_leak(self):  # analyse the Primary root cause
        self._log("i", "MEMORY", "Analyzing memory leak pattern")  # primary root cause analysis

        leak = self.mem.get("leak_analysis", {})  # Uses precomputed leak metadata

        if not leak.get("leak_detected"):  # avoid false positive
            self._log("!", "MEMORY", "No leak detected — skipping")
            return

        ts = self.mem.get("timeseries", [])
        # extract rootcause parameters
        rate = leak["leak_rate_mb_per_min"]
        gc = leak["gc_overhead_pct"]
        oom_min = leak["estimated_oom_minutes"]
        source = leak["suspected_source"]

        self._log("#", "MEMORY", "Leak data",
                  rate_mb_min=rate, gc_overhead=f"{gc}%",
                  oom_in=f"~{oom_min:.0f} min", source=source)

        self._add_finding(
            title=f"Memory leak confirmed — OOM every ~{oom_min:.0f} min",
            description=f"Memory grows at {rate} MiB/min. GC overhead {gc}%. Source: {source}.",
            severity="P1_CRITICAL",
            confidence=0.96,
            evidence={"leak_rate_mb_per_min": rate, "gc_overhead_pct": gc,
                      "oom_cycle_min": oom_min, "timeseries_sample": ts[:5]},
        )

    # Step 3B: Latency
    def check_latency(self):  #user impact analysis
        self._log("i", "LATENCY", "Analyzing P99 latency")

        if not self.latency:
            self._log("!", "LATENCY", "No data — skipping")
            return

        start = self.latency[0]["p99"]
        peak = max(t["p99"] for t in self.latency)  # Compare baseline vs worst case
        factor = round(peak / start, 1)  # Quantify degradation

        self._log("#", "LATENCY", "Degradation computed",
                  p99_start=f"{start}ms", p99_peak=f"{peak}ms", factor=f"{factor}x")

        self._add_finding(
            title=f"P99 latency spike: {start}ms → {peak}ms ({factor}x)",
            description=f"P99 degraded {factor}x. Sawtooth pattern tied to pod restart cycles.",
            severity="P1_CRITICAL",
            confidence=0.98,
            evidence={"p99_start": start, "p99_peak": peak, "factor": factor},
        )

    # Step 3C: Error Rate
    def check_error_rate(self):
        self._log("i", "ERRORS", "Analyzing error rate")

        if not self.error_rate:
            self._log("!", "ERRORS", "No data — skipping")
            return

        baseline = self.error_rate[0]["value"]  # Measure escalation
        peak = max(t["value"] for t in self.error_rate)

        self._log("#", "ERRORS", "Surge computed",
                  baseline=f"{baseline}%", peak=f"{peak}%")

        self._add_finding(
            title=f"Error rate surged to {peak}%",
            description=f"Error rate escalated from {baseline}% to {peak}%. Correlated with OOM + pod failures.",
            severity="P1_CRITICAL",
            confidence=0.97,
            evidence={"baseline_pct": baseline, "peak_pct": peak},
        )  # Confirms outage severity

    # Step 3D: DB Pool
    def check_db_pool(self):
        self._log("i", "DB_POOL", "Analyzing connection pool")

        pool = self.db.get("connection_pool")  # extract DB pool state
        if not pool:
            self._log("!", "DB_POOL", "No data — skipping")
            return


        # metrics needed to prove saturation
        active = pool["active"]
        max_sz = pool["max_size"]
        pending = pool["pending"]
        checkout = pool["avg_checkout_time_ms"]
        slow = self.db.get("slow_queries", [])

        self._log("#", "DB_POOL", "Pool state",
                  utilization=f"{active}/{max_sz} (100%)",
                  pending=pending, avg_checkout=f"{checkout/1000:.1f}s",
                  slow_queries=len(slow))


        # Adds amplifier finding
        self._add_finding(
            title=f"DB pool saturated — {pending} requests queued",
            description=f"All {max_sz} connections active. {pending} queued. Checkout time {checkout/1000:.1f}s. Slow queries holding locks.",
            severity="P1_CRITICAL",
            confidence=0.95,
            evidence={"pool": pool, "slow_queries": slow},
        )

    # Step 3E: Pod Health
    def check_pod_health(self):
        self._log("i", "PODS", "Scanning pod health")

        bad_statuses = {"CrashLoopBackOff", "OOMKilled"}  #If a worker keeps crashing again and again, or if it was killed because it ran out of memory, I will consider it broken
        unhealthy = [
            name for name, info in self.pods.items()
            if isinstance(info, dict) and info.get("status") in bad_statuses  # find all broken workers
        ]

        if not unhealthy:  # If nothing is broken, stop
            self._log("1", "PODS", "All pods healthy")
            return

        # From the traffic manager (API Gateway), how much of the service is still usable?
        # This tells how bad the situation is for users.
        capacity = self.upstream.get("healthy_pct", "?")
        circuit = self.upstream.get("circuit_state", "?")

        # Report each broken worker
        # For every broken worker, log exactly what’s wrong with it.
        for pod in unhealthy:
            info = self.pods[pod]
            self._log("!", "PODS", f"UNHEALTHY: {pod}",
                      status=info["status"], restarts=info.get("restart_count", "?"))


        # Raise a serious incident finding
        self._add_finding(
            title=f"{len(unhealthy)} pods critical — {capacity}% capacity remaining",
            description=f"Unhealthy: {unhealthy}. Circuit breaker: {circuit}. Surviving pods >88% CPU.",
            severity="P1_CRITICAL",
            confidence=0.99,
            evidence={"unhealthy_pods": unhealthy, "healthy_pct": capacity, "circuit": circuit},
        )

    # Step 4: Report
    # Produces agent-to-agent response
    def report(self):
        msg = {
            "id": f"msg-{uid()}",
            "sender": "metrics_agent",
            "receiver": "commander",
            "type": "STATUS_UPDATE",
            # Since the CommanderAgent doesn’t need raw metrics again it will just give the conclusions
            "payload": {
                "status": "complete",
                "findings_count": len(self.findings),
                "summary": [{"id": f["id"], "title": f["title"], "severity": f["severity"]}
                            for f in self.findings],
            },
        }
        self._log("1", "REPORT", f"STATUS_UPDATE → Commander ({len(self.findings)} findings)")
        return msg


    def run(self):  # Orchestrates full workflow
        print("METRICS AGENT — Standalone Run")

        self.receive_task()

        if not self.ingest_data():
            return self.findings

        self.check_memory_leak()
        self.check_latency()
        self.check_error_rate()
        self.check_db_pool()
        self.check_pod_health()

        message = self.report()

        print(f" DONE — {len(self.findings)} findings, {self.step} steps")

        return self.findings, message


# MAIN - Simulate Commander handoff & run
if __name__ == "__main__":

    # Load metrics (Commander would put this in SharedState)
    data_path = Path(__file__).parent / "mock_data" / "infrastructure_metrics.json"
    with open(data_path) as f:
        raw_metrics = json.load(f)

    # Commander's task to this agent
    task = {
        "objective": "Analyze memory leaks, latency, error rates, DB pool, pod health",
        "focus_services": ["payment-service"],
        "key_metrics": ["memory_usage", "p99_latency", "error_rate", "db_connections", "pod_health"],
    }

    print("SIMULATING COMMANDER HANDOFF")
    print("- Alert received from PagerDuty (P1_CRITICAL)")
    print("- CommanderAgent called -> loaded raw_metrics into SharedState")
    print("- CommanderAgent dispatching INVESTIGATION_TASK to Metrics Agent")

    # Run agent
    agent = MetricsAgent(raw_metrics=raw_metrics, task=task)
    findings, outgoing_msg = agent.run()

    # Print findings
    print("\n FINDINGS...")
    for i, f in enumerate(findings):
        print(f"\n  0 #{i+1} {f['title']}")
        print(f" {f['description']}")
        print(f" Confidence: {f['confidence']}  |  Evidence: {list(f['evidence'].keys())}")

    # Save execution log
    output_dir = Path(__file__).parent / "output"
    output_dir.mkdir(exist_ok=True)
    log_path = output_dir / "metrics_agent_log.json"
    with open(log_path, "w") as f:
        json.dump({"findings": findings, "outgoing_message": outgoing_msg}, f, indent=2)
    print(f"\n Log saved: {log_path}")