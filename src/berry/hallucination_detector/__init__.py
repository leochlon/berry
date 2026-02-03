from __future__ import annotations

# Verification now routes through K8s service via k8s_wrapper.py
from .k8s_wrapper import (
    run_detect_hallucination_k8s as run_detect_hallucination,
    run_audit_trace_budget_k8s as run_audit_trace_budget,
)

__all__ = ["run_detect_hallucination", "run_audit_trace_budget"]
