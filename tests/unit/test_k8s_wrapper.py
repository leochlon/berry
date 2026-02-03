"""Unit tests for Kubernetes service wrappers."""

import pytest
from unittest.mock import patch, MagicMock
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from berry.hallucination_detector.k8s_wrapper import (
    run_detect_hallucination_k8s,
    run_audit_trace_budget_k8s,
    _get_service_url,
    _get_api_key,
    DEFAULT_BERRY_SERVICE_URL,
)


class TestGetServiceUrl:
    """Tests for _get_service_url helper."""

    def test_default_url(self):
        """Default URL is K8s internal DNS."""
        with patch.dict(os.environ, {"BERRY_SERVICE_URL": ""}, clear=False):
            url = _get_service_url()
            assert url == DEFAULT_BERRY_SERVICE_URL

    def test_custom_url_from_env(self):
        """Custom URL from environment variable."""
        with patch.dict(os.environ, {"BERRY_SERVICE_URL": "http://localhost:8000"}):
            url = _get_service_url()
            assert url == "http://localhost:8000"


class TestGetApiKey:
    """Tests for _get_api_key helper."""

    def test_missing_api_key_raises(self):
        """Missing API key raises ValueError."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            with pytest.raises(ValueError) as exc_info:
                _get_api_key()
            assert "OPENAI_API_KEY is not set" in str(exc_info.value)

    def test_api_key_from_env(self):
        """API key retrieved from environment."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-testkey123"}):
            key = _get_api_key()
            assert key == "sk-testkey123"


class TestDetectHallucinationK8s:
    """Tests for run_detect_hallucination_k8s wrapper."""

    @patch("berry.hallucination_detector.k8s_wrapper.httpx.Client")
    def test_successful_request(self, mock_client_class):
        """Successful verification request."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "flagged": False,
            "under_budget": False,
            "summary": {"claims_scored": 1},
            "details": [{"idx": 0, "claim": "Test", "flagged": False}],
        }

        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = None
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test", "BERRY_SERVICE_URL": ""}):
            result = run_detect_hallucination_k8s(
                answer="The sky is blue",
                spans=[{"sid": "S0", "text": "Evidence about sky color"}],
            )

        assert result["flagged"] is False
        assert result["summary"]["claims_scored"] == 1

        # Verify request was made correctly
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert "/detect_hallucination" in call_args[0][0]
        assert call_args[1]["headers"]["Authorization"] == "Bearer sk-test"

    @patch("berry.hallucination_detector.k8s_wrapper.httpx.Client")
    def test_401_unauthorized(self, mock_client_class):
        """401 response returns error result."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"detail": "Invalid API key"}

        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = None
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-invalid", "BERRY_SERVICE_URL": ""}):
            result = run_detect_hallucination_k8s(
                answer="Test",
                spans=[{"sid": "S0", "text": "Evidence"}],
            )

        assert result["flagged"] is True
        assert "Authentication failed" in result["error"]

    @patch("berry.hallucination_detector.k8s_wrapper.httpx.Client")
    def test_402_budget_exceeded(self, mock_client_class):
        """402 response returns budget error."""
        mock_response = MagicMock()
        mock_response.status_code = 402
        mock_response.json.return_value = {"detail": "Budget exceeded. Spent: $5.00, Limit: $5.00"}

        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = None
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-overbudget", "BERRY_SERVICE_URL": ""}):
            result = run_detect_hallucination_k8s(
                answer="Test",
                spans=[{"sid": "S0", "text": "Evidence"}],
            )

        assert result["flagged"] is True
        assert "Budget exceeded" in result["error"]

    @patch("berry.hallucination_detector.k8s_wrapper.httpx.Client")
    def test_timeout_error(self, mock_client_class):
        """Timeout returns error result."""
        import httpx

        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = None
        mock_client.post.side_effect = httpx.TimeoutException("Connection timed out")
        mock_client_class.return_value = mock_client

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test", "BERRY_SERVICE_URL": ""}):
            result = run_detect_hallucination_k8s(
                answer="Test",
                spans=[{"sid": "S0", "text": "Evidence"}],
                timeout_s=5.0,
            )

        assert result["flagged"] is True
        assert "timeout" in result["error"].lower()

    @patch("berry.hallucination_detector.k8s_wrapper.httpx.Client")
    def test_connection_error(self, mock_client_class):
        """Connection error returns error result."""
        import httpx

        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = None
        mock_client.post.side_effect = httpx.RequestError("Connection refused")
        mock_client_class.return_value = mock_client

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test", "BERRY_SERVICE_URL": ""}):
            result = run_detect_hallucination_k8s(
                answer="Test",
                spans=[{"sid": "S0", "text": "Evidence"}],
            )

        assert result["flagged"] is True
        assert "connection error" in result["error"].lower()

    @patch("berry.hallucination_detector.k8s_wrapper.httpx.Client")
    def test_span_format_conversion(self, mock_client_class):
        """Spans with 'sid' key are converted to 'id' for API."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"flagged": False, "details": []}

        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = None
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test", "BERRY_SERVICE_URL": ""}):
            run_detect_hallucination_k8s(
                answer="Test",
                spans=[{"sid": "S0", "text": "Evidence"}],
            )

        # Check the payload sent
        call_args = mock_client.post.call_args
        payload = call_args[1]["json"]
        assert payload["spans"][0]["id"] == "S0"
        assert "sid" not in payload["spans"][0]

    def test_missing_api_key(self):
        """Missing API key returns graceful error dict."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "", "BERRY_SERVICE_URL": ""}):
            result = run_detect_hallucination_k8s(
                answer="Test",
                spans=[{"sid": "S0", "text": "Evidence"}],
            )
            assert result["flagged"] is True
            assert "OPENAI_API_KEY is not set" in result["error"]


class TestAuditTraceBudgetK8s:
    """Tests for run_audit_trace_budget_k8s wrapper."""

    @patch("berry.hallucination_detector.k8s_wrapper.httpx.Client")
    def test_successful_request(self, mock_client_class):
        """Successful audit request."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "flagged": False,
            "under_budget": False,
            "summary": {"steps_scored": 2},
            "details": [
                {"idx": 0, "claim": "Claim 1", "flagged": False},
                {"idx": 1, "claim": "Claim 2", "flagged": False},
            ],
        }

        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = None
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test", "BERRY_SERVICE_URL": ""}):
            result = run_audit_trace_budget_k8s(
                steps=[
                    {"claim": "Claim 1", "cites": ["S0"]},
                    {"claim": "Claim 2", "cites": ["S1"]},
                ],
                spans=[
                    {"sid": "S0", "text": "Evidence 1"},
                    {"sid": "S1", "text": "Evidence 2"},
                ],
            )

        assert result["flagged"] is False
        assert result["summary"]["steps_scored"] == 2

        # Verify request
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert "/audit_trace_budget" in call_args[0][0]

    @patch("berry.hallucination_detector.k8s_wrapper.httpx.Client")
    def test_401_unauthorized(self, mock_client_class):
        """401 response returns error."""
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"detail": "Invalid API key"}

        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = None
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-invalid", "BERRY_SERVICE_URL": ""}):
            result = run_audit_trace_budget_k8s(
                steps=[{"claim": "Test", "cites": ["S0"]}],
                spans=[{"sid": "S0", "text": "Evidence"}],
            )

        assert result["flagged"] is True
        assert "Authentication failed" in result["error"]

    @patch("berry.hallucination_detector.k8s_wrapper.httpx.Client")
    def test_step_format_with_confidence(self, mock_client_class):
        """Steps with confidence are properly formatted."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"flagged": False, "details": []}

        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.__exit__.return_value = None
        mock_client.post.return_value = mock_response
        mock_client_class.return_value = mock_client

        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test", "BERRY_SERVICE_URL": ""}):
            run_audit_trace_budget_k8s(
                steps=[{"claim": "Test", "cites": ["S0"], "confidence": 0.99}],
                spans=[{"sid": "S0", "text": "Evidence"}],
            )

        call_args = mock_client.post.call_args
        payload = call_args[1]["json"]
        assert payload["steps"][0]["confidence"] == 0.99

    def test_missing_api_key(self):
        """Missing API key returns graceful error dict."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "", "BERRY_SERVICE_URL": ""}):
            result = run_audit_trace_budget_k8s(
                steps=[{"claim": "Test", "cites": ["S0"]}],
                spans=[{"sid": "S0", "text": "Evidence"}],
            )
            assert result["flagged"] is True
            assert "OPENAI_API_KEY is not set" in result["error"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
