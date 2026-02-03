"""Kubernetes service wrappers for hallucination detection.

These wrappers call the berry-service Kubernetes endpoint instead of running
verification locally. This allows centralized budget tracking and authentication.

Environment variables:
- BERRY_SERVICE_URL: Override the K8s service URL (default: http://berry.berry.svc.cluster.local:8000)
- OPENAI_API_KEY: Used as the Bearer token for authentication (sk-* format)
"""

from __future__ import annotations

import os
import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

# Default K8s service URL (internal cluster DNS)
DEFAULT_BERRY_SERVICE_URL = "http://berry.berry.svc.cluster.local:8000"


def _get_service_url() -> str:
    """Get the berry-service URL from environment or default."""
    return (os.environ.get("BERRY_SERVICE_URL") or "").strip() or DEFAULT_BERRY_SERVICE_URL


def _get_api_key() -> str:
    """Get the user's API key from environment."""
    key = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if not key:
        raise ValueError("OPENAI_API_KEY is not set (required for K8s service authentication)")
    return key


def run_detect_hallucination_k8s(
    *,
    answer: str,
    spans: List[Dict[str, str]],
    verifier_model: str = "gpt-4o-mini",
    default_target: float = 0.95,
    max_claims: int = 25,
    claim_split: str = "sentences",
    require_citations: bool = False,
    context_mode: str = "cited",
    include_prompts: bool = False,
    timeout_s: float = 60.0,
    # Ignored params kept for compatibility with local version
    placeholder: str = "[REDACTED]",
    citation_regex: Optional[str] = None,
    temperature: float = 0.0,
    top_logprobs: int = 10,
    max_concurrency: int = 8,
    units: str = "bits",
    max_prompt_chars: int = 3000,
    pool_json_path: Optional[str] = None,
    local_llm_model_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Call detect_hallucination via the Kubernetes berry-service.

    This is a drop-in replacement for run_detect_hallucination that calls
    the remote service instead of running verification locally.

    Args:
        answer: The answer text to verify
        spans: Evidence spans to verify against (list of {"sid": str, "text": str})
        verifier_model: Model to use for verification
        default_target: Target confidence threshold
        max_claims: Maximum number of claims to extract
        claim_split: How to split claims ("sentences" or "lines")
        require_citations: Whether to require citations for each claim
        context_mode: Context mode ("all" or "cited")
        include_prompts: Whether to include prompts in response
        timeout_s: Request timeout in seconds

    Returns:
        Verification result dict with flagged, under_budget, summary, details
    """
    service_url = _get_service_url()
    try:
        api_key = _get_api_key()
    except ValueError as e:
        return {
            "flagged": True,
            "under_budget": True,
            "error": str(e),
            "details": [],
        }

    # Convert spans format if needed (sid -> id for service API)
    formatted_spans = []
    for s in (spans or []):
        sid = s.get("sid") or s.get("id", "")
        text = s.get("text", "")
        if sid and text:
            formatted_spans.append({"id": str(sid), "text": str(text)})

    payload = {
        "answer": str(answer or ""),
        "spans": formatted_spans,
        "verifier_model": str(verifier_model or "gpt-4o-mini"),
        "default_target": float(default_target or 0.95),
        "max_claims": int(max_claims or 25),
        "require_citations": bool(require_citations),
        "context_mode": str(context_mode or "cited"),
    }

    logger.info(f"Calling K8s detect_hallucination: {service_url}, {len(formatted_spans)} spans")

    try:
        with httpx.Client(timeout=timeout_s) as client:
            resp = client.post(
                f"{service_url}/detect_hallucination",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

            if resp.status_code == 401:
                return {
                    "flagged": True,
                    "under_budget": True,
                    "error": f"Authentication failed: {resp.json().get('detail', 'Invalid API key')}",
                    "details": [],
                }

            if resp.status_code == 402:
                return {
                    "flagged": True,
                    "under_budget": True,
                    "error": f"Budget exceeded: {resp.json().get('detail', 'Budget limit reached')}",
                    "details": [],
                }

            if resp.status_code != 200:
                return {
                    "flagged": True,
                    "under_budget": True,
                    "error": f"Service error ({resp.status_code}): {resp.text[:500]}",
                    "details": [],
                }

            result = resp.json()
            logger.info(f"K8s detect_hallucination complete: flagged={result.get('flagged')}")
            return result

    except httpx.TimeoutException:
        logger.error(f"K8s detect_hallucination timeout ({timeout_s}s)")
        return {
            "flagged": True,
            "under_budget": True,
            "error": f"Service timeout after {timeout_s}s",
            "details": [],
        }
    except httpx.RequestError as e:
        logger.error(f"K8s detect_hallucination request error: {e}")
        return {
            "flagged": True,
            "under_budget": True,
            "error": f"Service connection error: {e}",
            "details": [],
        }


def run_audit_trace_budget_k8s(
    *,
    steps: List[Dict[str, Any]],
    spans: List[Dict[str, str]],
    verifier_model: str = "gpt-4o-mini",
    default_target: float = 0.95,
    require_citations: bool = False,
    context_mode: str = "cited",
    include_prompts: bool = False,
    timeout_s: float = 60.0,
    # Ignored params kept for compatibility with local version
    placeholder: str = "[REDACTED]",
    temperature: float = 0.0,
    top_logprobs: int = 10,
    max_concurrency: int = 8,
    units: str = "bits",
    max_prompt_chars: int = 3000,
    pool_json_path: Optional[str] = None,
    local_llm_model_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Call audit_trace_budget via the Kubernetes berry-service.

    This is a drop-in replacement for run_audit_trace_budget that calls
    the remote service instead of running verification locally.

    Args:
        steps: List of (claim, citations) steps to verify
        spans: Evidence spans to verify against (list of {"sid": str, "text": str})
        verifier_model: Model to use for verification
        default_target: Target confidence threshold
        require_citations: Whether to require citations for each step
        context_mode: Context mode ("all" or "cited")
        include_prompts: Whether to include prompts in response
        timeout_s: Request timeout in seconds

    Returns:
        Verification result dict with flagged, under_budget, summary, details
    """
    service_url = _get_service_url()
    try:
        api_key = _get_api_key()
    except ValueError as e:
        return {
            "flagged": True,
            "under_budget": True,
            "error": str(e),
            "details": [],
        }

    # Convert spans format if needed (sid -> id for service API)
    formatted_spans = []
    for s in (spans or []):
        sid = s.get("sid") or s.get("id", "")
        text = s.get("text", "")
        if sid and text:
            formatted_spans.append({"id": str(sid), "text": str(text)})

    # Format steps for service API
    formatted_steps = []
    for st in (steps or []):
        claim = st.get("claim", "")
        cites = st.get("cites", [])
        confidence = st.get("confidence")
        if claim:
            step = {"claim": str(claim), "cites": list(cites or [])}
            if confidence is not None:
                step["confidence"] = float(confidence)
            formatted_steps.append(step)

    payload = {
        "steps": formatted_steps,
        "spans": formatted_spans,
        "verifier_model": str(verifier_model or "gpt-4o-mini"),
        "default_target": float(default_target or 0.95),
        "require_citations": bool(require_citations),
        "context_mode": str(context_mode or "cited"),
    }

    logger.info(f"Calling K8s audit_trace_budget: {service_url}, {len(formatted_steps)} steps, {len(formatted_spans)} spans")

    try:
        with httpx.Client(timeout=timeout_s) as client:
            resp = client.post(
                f"{service_url}/audit_trace_budget",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

            if resp.status_code == 401:
                return {
                    "flagged": True,
                    "under_budget": True,
                    "error": f"Authentication failed: {resp.json().get('detail', 'Invalid API key')}",
                    "details": [],
                }

            if resp.status_code == 402:
                return {
                    "flagged": True,
                    "under_budget": True,
                    "error": f"Budget exceeded: {resp.json().get('detail', 'Budget limit reached')}",
                    "details": [],
                }

            if resp.status_code != 200:
                return {
                    "flagged": True,
                    "under_budget": True,
                    "error": f"Service error ({resp.status_code}): {resp.text[:500]}",
                    "details": [],
                }

            result = resp.json()
            logger.info(f"K8s audit_trace_budget complete: flagged={result.get('flagged')}")
            return result

    except httpx.TimeoutException:
        logger.error(f"K8s audit_trace_budget timeout ({timeout_s}s)")
        return {
            "flagged": True,
            "under_budget": True,
            "error": f"Service timeout after {timeout_s}s",
            "details": [],
        }
    except httpx.RequestError as e:
        logger.error(f"K8s audit_trace_budget request error: {e}")
        return {
            "flagged": True,
            "under_budget": True,
            "error": f"Service connection error: {e}",
            "details": [],
        }
