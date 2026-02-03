"""Tests for MCP server verification tools (now via K8s service)."""

import pytest
from unittest.mock import patch, MagicMock
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))


class TestMCPServerTools:
    """Test that MCP server has verification tools."""

    def test_server_has_detect_hallucination(self):
        """MCP server has detect_hallucination tool."""
        from berry.mcp_server import create_server

        mcp = create_server(project_root=None)
        tool_names = [t.name for t in mcp._tool_manager._tools.values()]

        assert "detect_hallucination" in tool_names

    def test_server_has_audit_trace_budget(self):
        """MCP server has audit_trace_budget tool."""
        from berry.mcp_server import create_server

        mcp = create_server(project_root=None)
        tool_names = [t.name for t in mcp._tool_manager._tools.values()]

        assert "audit_trace_budget" in tool_names

    def test_all_expected_tools_exist(self):
        """All expected tools are registered."""
        from berry.mcp_server import create_server

        mcp = create_server(project_root=None)
        tool_names = set(t.name for t in mcp._tool_manager._tools.values())

        expected = {
            "start_run",
            "load_run",
            "get_deliverable",
            "add_span",
            "add_file_span",
            "list_spans",
            "get_span",
            "search_spans",
            "distill_span",
            "detect_hallucination",
            "audit_trace_budget",
        }

        assert expected.issubset(tool_names)


class TestVerificationToolsCallK8sWrapper:
    """Test that verification tools call the K8s wrapper functions."""

    @patch("berry.mcp_server.run_detect_hallucination_k8s")
    def test_detect_hallucination_calls_k8s_wrapper(self, mock_wrapper):
        """detect_hallucination tool calls the K8s wrapper."""
        mock_wrapper.return_value = {
            "flagged": False,
            "under_budget": False,
            "summary": {"claims_scored": 1},
            "details": [],
        }

        from berry.mcp_server import create_server

        mcp = create_server(project_root=None)

        # Find the tool
        tool = None
        for t in mcp._tool_manager._tools.values():
            if t.name == "detect_hallucination":
                tool = t
                break

        assert tool is not None

        # Call the tool function directly
        result = tool.fn(
            answer="Test answer",
            spans=[{"sid": "S0", "text": "Evidence"}],
        )

        mock_wrapper.assert_called_once()
        assert result["flagged"] is False

    @patch("berry.mcp_server.run_audit_trace_budget_k8s")
    def test_audit_trace_budget_calls_k8s_wrapper(self, mock_wrapper):
        """audit_trace_budget tool calls the K8s wrapper."""
        mock_wrapper.return_value = {
            "flagged": False,
            "under_budget": False,
            "summary": {"steps_scored": 1},
            "details": [],
        }

        from berry.mcp_server import create_server

        mcp = create_server(project_root=None)

        # Find the tool
        tool = None
        for t in mcp._tool_manager._tools.values():
            if t.name == "audit_trace_budget":
                tool = t
                break

        assert tool is not None

        # Call the tool function directly
        result = tool.fn(
            steps=[{"claim": "Test", "cites": ["S0"]}],
            spans=[{"sid": "S0", "text": "Evidence"}],
        )

        mock_wrapper.assert_called_once()
        assert result["flagged"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
