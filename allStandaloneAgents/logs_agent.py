import json
import uuid
from pathlib import Path
from datetime import datetime, timezone

DATA_DIR = Path(__file__).parent / "mock_data"


def uid():
    return uuid.uuid4().hex[:8]

def now():
    return datetime.now(timezone.utc).isoformat()

def log(step, phase, msg, **kw):
    print(f"  [{step:02d}] [{phase}] {msg}")
    for k, v in kw.items():
        print(f"--> {k}: {v}")



class LogsAgent:

    def __init__(self, raw_logs: dict, task: dict):
        self.raw_logs = raw_logs
        self.task = task
        self.findings = []
        self.step = 0
        self.log_entries = []

    def _log(self, phase, msg, **kw):
        self.step += 1
        log(self.step, phase, msg, **kw)

    def _add_finding(self, title, description, severity, confidence, evidence, services, log_ids=None):
        finding = {
            "id": f"find-{uid()}",
            "agent": "logs_agent",
            "timestamp": now(),
            "title": title,
            "description": description,
            "severity": severity,
            "confidence": confidence,
            "evidence": evidence,
            "related_services": services,
            "related_log_ids": log_ids or [],
        }
        self.findings.append(finding)
        self._log("FINDING", title, severity=severity, confidence=confidence)

    def _search_logs(self, keyword):
        """Search log entries by keyword in message field."""
        return [l for l in self.log_entries if keyword in l.get("message", "")]


    def receive_task(self):
        self._log("HANDOFF", "Received INVESTIGATION_TASK from Commander",
                  objective=self.task.get("objective"),
                  focus_services=self.task.get("focus_services"))


    def ingest_data(self):
        self._log("INGEST", "Loading log entries from SharedState")

        self.log_entries = self.raw_logs.get("log_entries", [])
        if not self.log_entries:
            self._log("INGEST", "No log entries found -- aborting")
            return False


        levels = {}
        for l in self.log_entries:
            lvl = l.get("level", "UNKNOWN")
            levels[lvl] = levels.get(lvl, 0) + 1


        services = {}
        for l in self.log_entries:
            svc = l.get("service", "unknown")
            services[svc] = services.get(svc, 0) + 1

        self._log("INGEST", "Data loaded",
                  total_entries=len(self.log_entries),
                  by_level=levels,
                  by_service=services)
        return True


    def check_oom_errors(self):
        self._log("SCAN:OOM", "Scanning for OutOfMemoryError")

        matches = self._search_logs("OutOfMemoryError")
        if not matches:
            self._log("SCAN:OOM", "No OOM errors found -- skipping")
            return

        entry = matches[0]
        meta = entry.get("metadata", {})
        stack = entry.get("stack_trace", [])

        self._log("SCAN:OOM", "OOM error found",
                  log_id=entry["id"],
                  service=entry["service"],
                  heap_used_mb=meta.get("heap_used_mb"),
                  heap_max_mb=meta.get("heap_max_mb"),
                  thread_count=meta.get("thread_count"),
                  root_frame=stack[0] if stack else "N/A")

        self._add_finding(
            title="Java OutOfMemoryError in payment-service",
            description=(
                f"Heap exhausted at {meta['heap_used_mb']}/{meta['heap_max_mb']} MiB. "
                f"Root frame: {stack[0] if stack else 'N/A'}. "
                f"Thread count abnormally high at {meta.get('thread_count', 'N/A')}."
            ),
            severity="P1_CRITICAL",
            confidence=0.97,
            evidence={
                "heap_used_mb": meta.get("heap_used_mb"),
                "heap_max_mb": meta.get("heap_max_mb"),
                "thread_count": meta.get("thread_count"),
                "stack_trace": stack,
            },
            services=["payment-service"],
            log_ids=[e["id"] for e in matches],
        )


    def check_connection_pool(self):
        self._log("SCAN:POOL", "Scanning for connection pool exhaustion")

        matches = self._search_logs("Connection pool exhausted")
        if not matches:
            self._log("SCAN:POOL", "No pool exhaustion found -- skipping")
            return

        entry = matches[0]
        meta = entry.get("metadata", {})

        self._log("SCAN:POOL", "Pool exhaustion found",
                  log_id=entry["id"],
                  pool_name=meta.get("pool_name"),
                  active=meta.get("active_connections"),
                  max_size=meta.get("max_pool_size"),
                  pending=meta.get("pending_requests"))

        self._add_finding(
            title="Database connection pool fully exhausted",
            description=(
                f"HikariCP pool at max: {meta['active_connections']}/{meta['max_pool_size']} active, "
                f"{meta['pending_requests']} requests queued. Queries timing out."
            ),
            severity="P1_CRITICAL",
            confidence=0.95,
            evidence={
                "pool_name": meta.get("pool_name"),
                "active": meta.get("active_connections"),
                "max_size": meta.get("max_pool_size"),
                "pending": meta.get("pending_requests"),
            },
            services=["payment-service"],
            log_ids=[e["id"] for e in matches],
        )


    def check_cascading_failure(self):
        self._log("SCAN:CASCADE", "Scanning for cascading failures")

        matches = self._search_logs("Cascading failure")
        if not matches:
            self._log("SCAN:CASCADE", "No cascading failures found -- skipping")
            return

        entry = matches[0]
        meta = entry.get("metadata", {})
        errors = meta.get("error_codes", {})

        self._log("SCAN:CASCADE", "Cascading failure found",
                  log_id=entry["id"],
                  service=entry["service"],
                  success_rate=f"{meta.get('success_rate_pct')}%",
                  error_503=errors.get("503"),
                  fallback=meta.get("fallback_type"))

        self._add_finding(
            title="Cascading failure: order-service to payment-service",
            description=(
                f"{errors.get('503', 0)} 503 errors in 60s. "
                f"Success rate dropped to {meta['success_rate_pct']}%. "
                f"Fallback: {meta.get('fallback_type')}."
            ),
            severity="P2_HIGH",
            confidence=0.92,
            evidence={
                "success_rate_pct": meta.get("success_rate_pct"),
                "error_codes": errors,
                "fallback_type": meta.get("fallback_type"),
            },
            services=["payment-service", "order-service"],
            log_ids=[e["id"] for e in matches],
        )


    def check_tls_errors(self):
        self._log("SCAN:TLS", "Scanning for TLS/certificate errors")

        matches = self._search_logs("TLS handshake failed")
        if not matches:
            self._log("SCAN:TLS", "No TLS errors found -- skipping")
            return

        entry = matches[0]
        meta = entry.get("metadata", {})

        self._log("SCAN:TLS", "TLS error found",
                  log_id=entry["id"],
                  cert_cn=meta.get("cert_cn"),
                  cert_expiry=meta.get("cert_expiry"),
                  ssl_error=meta.get("ssl_error_code"))

        self._add_finding(
            title="Expired TLS certificate blocking DB connections",
            description=(
                f"Certificate for {meta['cert_cn']} expired at {meta['cert_expiry']}. "
                "Canary pods using stale cert bundle cannot connect to database."
            ),
            severity="P2_HIGH",
            confidence=0.98,
            evidence={
                "cert_cn": meta.get("cert_cn"),
                "cert_expiry": meta.get("cert_expiry"),
                "ssl_error": meta.get("ssl_error_code"),
                "target": meta.get("connection_target"),
            },
            services=["payment-service"],
            log_ids=[e["id"] for e in matches],
        )


    def check_deadlocks(self):
        self._log("SCAN:DEADLOCK", "Scanning for thread deadlocks")

        matches = self._search_logs("Deadlock detected")
        if not matches:
            self._log("SCAN:DEADLOCK", "No deadlocks found -- skipping")
            return

        entry = matches[0]
        meta = entry.get("metadata", {})

        self._log("SCAN:DEADLOCK", "Deadlock found",
                  log_id=entry["id"],
                  threads=meta.get("deadlocked_threads"),
                  resources=meta.get("locked_resources"),
                  affected_tx=meta.get("affected_transactions"))

        self._add_finding(
            title="Thread deadlock in batch transaction processor",
            description=(
                f"Threads {meta['deadlocked_threads']} deadlocked on {meta['locked_resources']}. "
                f"{meta['affected_transactions']} transactions blocked."
            ),
            severity="P2_HIGH",
            confidence=0.94,
            evidence={
                "threads": meta.get("deadlocked_threads"),
                "resources": meta.get("locked_resources"),
                "affected_transactions": meta.get("affected_transactions"),
                "duration_ms": meta.get("deadlock_duration_ms"),
            },
            services=["payment-service"],
            log_ids=[e["id"] for e in matches],
        )

    def check_slow_queries(self):
        self._log("SCAN:SLOW_QUERY", "Scanning for database query timeouts")

        matches = self._search_logs("Database query timeout")
        if not matches:
            self._log("SCAN:SLOW_QUERY", "No slow queries found -- skipping")
            return

        entry = matches[0]
        meta = entry.get("metadata", {})

        self._log("SCAN:SLOW_QUERY", "Slow query found",
                  log_id=entry["id"],
                  table=meta.get("table"),
                  execution_ms=meta.get("execution_time_ms"),
                  rows_scanned=meta.get("rows_scanned"),
                  missing_index=meta.get("missing_index"))

        self._add_finding(
            title="Critical slow query -- missing database index",
            description=(
                f"Query on {meta['table']} scanned {meta['rows_scanned']:,} rows, "
                f"took {meta['execution_time_ms']:,}ms (limit 5000ms). "
                f"Missing index: {meta['missing_index']}."
            ),
            severity="P2_HIGH",
            confidence=0.96,
            evidence={
                "table": meta.get("table"),
                "execution_ms": meta.get("execution_time_ms"),
                "rows_scanned": meta.get("rows_scanned"),
                "missing_index": meta.get("missing_index"),
                "timeout_ms": meta.get("timeout_ms"),
            },
            services=["payment-service"],
            log_ids=[e["id"] for e in matches],
        )


    def report(self):
        msg = {
            "id": f"msg-{uid()}",
            "sender": "logs_agent",
            "receiver": "commander",
            "type": "STATUS_UPDATE",
            "payload": {
                "status": "complete",
                "findings_count": len(self.findings),
                "summary": [{"id": f["id"], "title": f["title"], "severity": f["severity"]}
                            for f in self.findings],
            },
        }
        self._log("REPORT", f"STATUS_UPDATE sent to Commander ({len(self.findings)} findings)")
        return msg


    def run(self):
        print("  LOGS AGENT -- Standalone Run")
        self.receive_task()

        if not self.ingest_data():
            return self.findings, None

        self.check_oom_errors()
        self.check_connection_pool()
        self.check_cascading_failure()
        self.check_tls_errors()
        self.check_deadlocks()
        self.check_slow_queries()

        message = self.report()

        print(f"  DONE -- {len(self.findings)} findings, {self.step} steps")
        return self.findings, message


if __name__ == "__main__":

    # Load logs (Commander puts this in SharedState)
    with open(DATA_DIR / "application_logs.json") as f:
        raw_logs = json.load(f)

    task = {
        "objective": "Find OOM errors, connection pool exhaustion, stack traces, cascading failures",
        "focus_services": ["payment-service", "api-gateway", "order-service"],
        "lookback": "15 minutes",
    }

    print(" COMMANDER HANDOFF (simulated)")
    print(" 1. Alert received (P1_CRITICAL)")
    print(" 2. Raw logs loaded into SharedState")
    print(" 3. Dispatching task to Logs Agent")

    # Run
    agent = LogsAgent(raw_logs=raw_logs, task=task)
    findings, outgoing_msg = agent.run()


    print(" FINDINGS")
    for i, f in enumerate(findings):
        sev = "P1" if "P1" in f["severity"] else "P2"
        print(f"\n [{sev}] #{i+1} {f['title']}")
        print(f" {f['description']}")
        print(f" Confidence: {f['confidence']}  |  Logs: {f['related_log_ids']}")

    out = DATA_DIR.parent / "output"
    out.mkdir(exist_ok=True)
    path = out / "logs_agent_log.json"
    with open(path, "w") as f:
        json.dump({"findings": findings, "outgoing_message": outgoing_msg}, f, indent=2)
    print(f"\n  Saved: {path}")