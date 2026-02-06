from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


# ──────────────────────────────────────────────────────────────
# 1.  ENUMS & VALUE OBJECTS
# ──────────────────────────────────────────────────────────────

class Severity(str, Enum):
    P1_CRITICAL = "P1_CRITICAL"   # Full outage / data loss risk
    P2_HIGH     = "P2_HIGH"       # Major degradation, customer-facing
    P3_MEDIUM   = "P3_MEDIUM"     # Partial impact, workaround exists
    P4_LOW      = "P4_LOW"        # Cosmetic / non-urgent


class AgentRole(str, Enum):
    COMMANDER        = "commander"
    LOGS_AGENT       = "logs_agent"
    METRICS_AGENT    = "metrics_agent"
    DEPLOY_INTEL     = "deploy_intel"


class InvestigationPhase(str, Enum):
    ALERT_RECEIVED       = "alert_received"
    TRIAGE               = "triage"
    PARALLEL_INVESTIGATION = "parallel_investigation"
    CORRELATION          = "correlation"
    ROOT_CAUSE_ANALYSIS  = "root_cause_analysis"
    REMEDIATION_PLAN     = "remediation_plan"
    COMPLETE             = "complete"


class MessageType(str, Enum):
    INVESTIGATION_TASK   = "investigation_task"     # Commander → Agent
    FINDING              = "finding"                 # Agent → Commander
    CORRELATION_REQUEST  = "correlation_request"     # Commander → All
    STATUS_UPDATE        = "status_update"           # Any → Commander
    ESCALATION           = "escalation"              # Agent → Commander
    REMEDIATION_ACTION   = "remediation_action"      # Commander → External


# ──────────────────────────────────────────────────────────────
# 2.  DATA STRUCTURES
# ──────────────────────────────────────────────────────────────

@dataclass
class Finding:
    """A single piece of evidence discovered by a specialist agent."""
    id: str = field(default_factory=lambda: f"find-{uuid.uuid4().hex[:8]}")
    agent: AgentRole = AgentRole.COMMANDER
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    title: str = ""
    description: str = ""
    severity: Severity = Severity.P4_LOW
    evidence: dict[str, Any] = field(default_factory=dict)
    related_services: list[str] = field(default_factory=list)
    related_log_ids: list[str] = field(default_factory=list)
    confidence: float = 0.0  # 0.0 – 1.0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "agent": self.agent.value,
            "timestamp": self.timestamp,
            "title": self.title,
            "description": self.description,
            "severity": self.severity.value,
            "evidence": self.evidence,
            "related_services": self.related_services,
            "related_log_ids": self.related_log_ids,
            "confidence": self.confidence,
        }


@dataclass
class RootCauseAnalysis:
    """Final RCA document produced by the Commander after correlation."""
    id: str = field(default_factory=lambda: f"rca-{uuid.uuid4().hex[:8]}")
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    summary: str = ""
    root_causes: list[dict[str, Any]] = field(default_factory=list)
    contributing_factors: list[str] = field(default_factory=list)
    timeline: list[dict[str, str]] = field(default_factory=list)
    remediation_steps: list[dict[str, Any]] = field(default_factory=list)
    severity: Severity = Severity.P1_CRITICAL
    blast_radius: list[str] = field(default_factory=list)
    findings_used: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "summary": self.summary,
            "severity": self.severity.value,
            "root_causes": self.root_causes,
            "contributing_factors": self.contributing_factors,
            "timeline": self.timeline,
            "remediation_steps": self.remediation_steps,
            "blast_radius": self.blast_radius,
            "findings_used": self.findings_used,
        }


# ──────────────────────────────────────────────────────────────
# 3.  INTER-AGENT MESSAGE ENVELOPE
# ──────────────────────────────────────────────────────────────

@dataclass
class AgentMessage:
    """
    Typed message exchanged between agents via the communication bus.
    Every message is immutable once created and stored in the shared ledger.
    """
    id: str = field(default_factory=lambda: f"msg-{uuid.uuid4().hex[:8]}")
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    sender: AgentRole = AgentRole.COMMANDER
    receiver: AgentRole | str = AgentRole.COMMANDER  # str for "ALL"
    msg_type: MessageType = MessageType.STATUS_UPDATE
    payload: dict[str, Any] = field(default_factory=dict)
    in_reply_to: Optional[str] = None  # parent message id

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "sender": self.sender.value if isinstance(self.sender, AgentRole) else self.sender,
            "receiver": self.receiver.value if isinstance(self.receiver, AgentRole) else self.receiver,
            "msg_type": self.msg_type.value,
            "payload": self.payload,
            "in_reply_to": self.in_reply_to,
        }


# ──────────────────────────────────────────────────────────────
# 4.  SHARED STATE  (single source of truth for the graph)
# ──────────────────────────────────────────────────────────────

@dataclass
class SharedState:
    """
    Passed through every node in the LangGraph reasoning graph.
    Agents READ from and WRITE to this state; the graph runtime
    ensures consistency.
    """
    # ── Investigation metadata ──
    investigation_id: str = field(default_factory=lambda: f"inv-{uuid.uuid4().hex[:8]}")
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    phase: InvestigationPhase = InvestigationPhase.ALERT_RECEIVED
    severity: Severity = Severity.P4_LOW

    # ── Incoming alert ──
    alert: dict[str, Any] = field(default_factory=dict)

    # ── Raw data sources (loaded once by Commander) ──
    raw_logs: dict[str, Any] = field(default_factory=dict)
    raw_metrics: dict[str, Any] = field(default_factory=dict)
    raw_deployments: dict[str, Any] = field(default_factory=dict)

    # ── Investigation plan (set by Commander during triage) ──
    investigation_plan: dict[str, Any] = field(default_factory=dict)

    # ── Specialist findings ──
    findings: list[Finding] = field(default_factory=list)

    # ── Communication ledger (append-only) ──
    message_ledger: list[AgentMessage] = field(default_factory=list)

    # ── Correlation & RCA ──
    correlations: list[dict[str, Any]] = field(default_factory=list)
    rca: Optional[RootCauseAnalysis] = None

    # ── Graph control flags ──
    needs_escalation: bool = False
    investigation_complete: bool = False

    # ────── helpers ──────

    def add_finding(self, finding: Finding) -> None:
        self.findings.append(finding)

    def send_message(self, msg: AgentMessage) -> None:
        self.message_ledger.append(msg)

    def get_messages_for(self, agent: AgentRole) -> list[AgentMessage]:
        return [
            m for m in self.message_ledger
            if m.receiver == agent or m.receiver == "ALL"
        ]

    def get_findings_by_agent(self, agent: AgentRole) -> list[Finding]:
        return [f for f in self.findings if f.agent == agent]

    def to_dict(self) -> dict:
        return {
            "investigation_id": self.investigation_id,
            "created_at": self.created_at,
            "phase": self.phase.value,
            "severity": self.severity.value,
            "alert": self.alert,
            "investigation_plan": self.investigation_plan,
            "findings": [f.to_dict() for f in self.findings],
            "message_ledger": [m.to_dict() for m in self.message_ledger],
            "correlations": self.correlations,
            "rca": self.rca.to_dict() if self.rca else None,
            "needs_escalation": self.needs_escalation,
            "investigation_complete": self.investigation_complete,
        }


# ──────────────────────────────────────────────────────────────
# 5.  COMMUNICATION BUS  (helper layer over SharedState)
# ──────────────────────────────────────────────────────────────

class CommunicationBus:
    """
    Thin routing layer.  In a production system this would be backed
    by Redis Streams or Kafka; here it delegates to SharedState's
    append-only message_ledger.
    """

    @staticmethod
    def dispatch(state: SharedState, sender: AgentRole, receiver: AgentRole | str,
                 msg_type: MessageType, payload: dict, in_reply_to: str | None = None) -> AgentMessage:
        msg = AgentMessage(
            sender=sender,
            receiver=receiver,
            msg_type=msg_type,
            payload=payload,
            in_reply_to=in_reply_to,
        )
        state.send_message(msg)
        return msg

    @staticmethod
    def broadcast(state: SharedState, sender: AgentRole,
                  msg_type: MessageType, payload: dict) -> AgentMessage:
        return CommunicationBus.dispatch(state, sender, "ALL", msg_type, payload)

    @staticmethod
    def inbox(state: SharedState, agent: AgentRole,
              msg_type: MessageType | None = None) -> list[AgentMessage]:
        msgs = state.get_messages_for(agent)
        if msg_type:
            msgs = [m for m in msgs if m.msg_type == msg_type]
        return msgs


# ──────────────────────────────────────────────────────────────
# 6.  QUICK SMOKE TEST
# ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    state = SharedState(
        alert={
            "source": "PagerDuty",
            "title": "payment-service: P99 latency > 10s, error rate > 80%",
            "severity": "P1",
            "triggered_at": "2026-02-06T08:05:00Z",
            "affected_service": "payment-service",
        }
    )

    # Commander sends tasks
    CommunicationBus.dispatch(
        state, AgentRole.COMMANDER, AgentRole.LOGS_AGENT,
        MessageType.INVESTIGATION_TASK,
        {"instruction": "Deep-scan payment-service logs for OOM and connection errors"}
    )
    CommunicationBus.dispatch(
        state, AgentRole.COMMANDER, AgentRole.METRICS_AGENT,
        MessageType.INVESTIGATION_TASK,
        {"instruction": "Analyze memory leak pattern and latency spike in payment-service"}
    )

    # Logs agent responds with a finding
    f = Finding(
        agent=AgentRole.LOGS_AGENT,
        title="OutOfMemoryError in TransactionProcessor",
        description="Heap exhausted at 3891/4096 MiB due to unbounded batch allocation",
        severity=Severity.P1_CRITICAL,
        evidence={"log_id": "log-0002", "heap_used_mb": 3891},
        related_services=["payment-service"],
        confidence=0.95,
    )
    state.add_finding(f)

    print(json.dumps(state.to_dict(), indent=2, default=str))
    print(f"\n✅  State management smoke test passed — {len(state.message_ledger)} messages, {len(state.findings)} findings")