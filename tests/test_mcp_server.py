"""Tests for MCP server functionality."""

import pytest
from vnc_use.mcp_server import mcp


def test_mcp_server_initialization():
    """Test that MCP server is properly initialized."""
    assert mcp.name == "VNC Computer Use Agent"


def test_execute_vnc_task_tool_exists():
    """Test that execute_vnc_task tool is registered."""
    # Get registered tools
    tools = mcp._tool_manager._tools
    assert "execute_vnc_task" in tools


def test_execute_vnc_task_signature():
    """Test execute_vnc_task has correct signature."""
    import inspect

    from vnc_use.mcp_server import execute_vnc_task

    sig = inspect.signature(execute_vnc_task)
    params = sig.parameters

    # Check required parameters
    assert "vnc_server" in params
    assert "task" in params

    # Check optional parameters
    assert "vnc_password" in params
    assert "step_limit" in params
    assert "timeout" in params
    assert "ctx" in params

    # Check defaults
    assert params["vnc_password"].default is None
    assert params["step_limit"].default == 40
    assert params["timeout"].default == 300


@pytest.mark.asyncio
async def test_execute_vnc_task_without_vnc():
    """Test execute_vnc_task error handling when VNC is unavailable."""
    from vnc_use.mcp_server import execute_vnc_task

    result = await execute_vnc_task(
        vnc_server="nonexistent::9999",
        task="Test task",
        vnc_password=None,
        step_limit=5,
        timeout=10,
        ctx=None,
    )

    # Should return error result
    assert result["success"] is False
    assert result["error"] is not None
    assert "Task execution failed" in result["error"]


@pytest.mark.asyncio
async def test_execute_vnc_task_parameter_validation():
    """Test parameter types are correct."""
    from vnc_use.mcp_server import execute_vnc_task

    # Should accept valid parameters without error
    result = await execute_vnc_task(
        vnc_server="localhost::5901",
        task="Open browser",
        vnc_password="test",
        step_limit=10,
        timeout=60,
        ctx=None,
    )

    # Should return a dict with expected keys
    assert isinstance(result, dict)
    assert "success" in result
    assert "run_id" in result
    assert "run_dir" in result
    assert "steps" in result
    assert "error" in result


def test_mcp_server_name():
    """Test MCP server has correct name."""
    assert mcp.name == "VNC Computer Use Agent"


def test_mcp_tool_manager():
    """Test tool manager is properly configured."""
    assert hasattr(mcp, "_tool_manager")
    assert len(mcp._tool_manager._tools) > 0
