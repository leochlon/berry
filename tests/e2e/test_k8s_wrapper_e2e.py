#!/usr/bin/env python3
"""End-to-end tests for K8s wrapper functions.

These tests require:
1. Access to the Kubernetes cluster (kubectl configured)
2. The berry-service deployed and running
3. A valid API key set in OPENAI_API_KEY

Run with: OPENAI_API_KEY=sk-your-key python -m pytest tests/e2e/test_k8s_wrapper_e2e.py -v
"""

import os
import sys
import pytest

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))


# Skip all tests if OPENAI_API_KEY not set or not a valid sk- key
pytestmark = pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY", "").startswith("sk-"),
    reason="OPENAI_API_KEY not set or not a valid sk- key"
)


class TestDetectHallucinationK8sE2E:
    """End-to-end tests for detect_hallucination via K8s service."""

    def test_basic_verification(self):
        """Basic verification call through K8s service."""
        # Must set BERRY_SERVICE_URL to point to the service
        # For local testing, use kubectl port-forward
        if not os.environ.get("BERRY_SERVICE_URL"):
            pytest.skip("BERRY_SERVICE_URL not set (use kubectl port-forward berry-service 8000:8000)")

        from berry.hallucination_detector.k8s_wrapper import run_detect_hallucination_k8s

        result = run_detect_hallucination_k8s(
            answer="The sky is blue.",
            spans=[{"sid": "S0", "text": "The sky appears blue due to Rayleigh scattering of sunlight."}],
            timeout_s=30.0,
        )

        # Check structure
        assert "flagged" in result
        assert "details" in result

        # Should not have error
        if "error" in result:
            pytest.fail(f"Got error: {result['error']}")

    def test_invalid_key_returns_error(self):
        """Invalid API key returns auth error."""
        if not os.environ.get("BERRY_SERVICE_URL"):
            pytest.skip("BERRY_SERVICE_URL not set")

        from berry.hallucination_detector.k8s_wrapper import run_detect_hallucination_k8s

        # Temporarily override with invalid key
        original_key = os.environ.get("OPENAI_API_KEY")
        try:
            os.environ["OPENAI_API_KEY"] = "sk-invalid-key-that-does-not-exist"

            result = run_detect_hallucination_k8s(
                answer="Test",
                spans=[{"sid": "S0", "text": "Evidence"}],
                timeout_s=10.0,
            )

            # Should get error
            assert result.get("flagged") is True
            assert "error" in result
            assert "Authentication" in result["error"] or "Invalid" in result["error"]
        finally:
            if original_key:
                os.environ["OPENAI_API_KEY"] = original_key


class TestAuditTraceBudgetK8sE2E:
    """End-to-end tests for audit_trace_budget via K8s service."""

    def test_basic_audit(self):
        """Basic audit call through K8s service."""
        if not os.environ.get("BERRY_SERVICE_URL"):
            pytest.skip("BERRY_SERVICE_URL not set")

        from berry.hallucination_detector.k8s_wrapper import run_audit_trace_budget_k8s

        result = run_audit_trace_budget_k8s(
            steps=[
                {"claim": "The sky is blue.", "cites": ["S0"]},
            ],
            spans=[
                {"sid": "S0", "text": "The sky appears blue due to Rayleigh scattering."},
            ],
            timeout_s=30.0,
        )

        # Check structure
        assert "flagged" in result
        assert "details" in result

        # Should not have error
        if "error" in result:
            pytest.fail(f"Got error: {result['error']}")


class TestK8sServiceConnectivity:
    """Test connectivity to K8s service."""

    def test_service_reachable(self):
        """K8s service is reachable."""
        if not os.environ.get("BERRY_SERVICE_URL"):
            pytest.skip("BERRY_SERVICE_URL not set")

        import httpx

        url = os.environ["BERRY_SERVICE_URL"]
        try:
            resp = httpx.get(f"{url}/health", timeout=5.0)
            assert resp.status_code == 200
            data = resp.json()
            assert data.get("status") == "ok"
        except httpx.RequestError as e:
            pytest.fail(f"Cannot reach K8s service at {url}: {e}")


if __name__ == "__main__":
    # For manual testing with port-forward
    print("To run these tests:")
    print("1. kubectl port-forward -n berry svc/berry 8000:8000")
    print("2. export BERRY_SERVICE_URL=http://localhost:8000")
    print("3. export OPENAI_API_KEY=sk-your-key")
    print("4. python -m pytest tests/e2e/test_k8s_wrapper_e2e.py -v")
    pytest.main([__file__, "-v"])
