#!/usr/bin/env python3
"""Basic tests for multi-model support."""

import os

import pytest
from vnc_use.agent import VncUseAgent
from vnc_use.planners import AnthropicPlanner, GeminiPlanner
from vnc_use.planners.base import BasePlanner


def test_gemini_planner_implements_base():
    """Test that GeminiPlanner implements BasePlanner interface."""
    assert issubclass(GeminiPlanner, BasePlanner)


def test_anthropic_planner_implements_base():
    """Test that AnthropicPlanner implements BasePlanner interface."""
    assert issubclass(AnthropicPlanner, BasePlanner)


def test_agent_default_model_provider():
    """Test that agent defaults to Gemini when no provider specified."""
    # Skip if no API keys available
    if not os.getenv("GOOGLE_API_KEY") and not os.getenv("GEMINI_API_KEY"):
        pytest.skip("No Gemini API key available")

    agent = VncUseAgent(
        vnc_server="localhost::5901",
        vnc_password="test",
    )

    assert isinstance(agent.planner, GeminiPlanner)


def test_agent_gemini_provider():
    """Test that agent creates GeminiPlanner when provider='gemini'."""
    if not os.getenv("GOOGLE_API_KEY") and not os.getenv("GEMINI_API_KEY"):
        pytest.skip("No Gemini API key available")

    agent = VncUseAgent(
        vnc_server="localhost::5901",
        vnc_password="test",
        model_provider="gemini",
    )

    assert isinstance(agent.planner, GeminiPlanner)


def test_agent_anthropic_provider():
    """Test that agent creates AnthropicPlanner when provider='anthropic'."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        pytest.skip("No Anthropic API key available")

    agent = VncUseAgent(
        vnc_server="localhost::5901",
        vnc_password="test",
        model_provider="anthropic",
    )

    assert isinstance(agent.planner, AnthropicPlanner)


def test_agent_invalid_provider():
    """Test that agent raises ValueError for invalid provider."""
    with pytest.raises(ValueError, match="Unknown model_provider"):
        VncUseAgent(
            vnc_server="localhost::5901",
            vnc_password="test",
            model_provider="invalid_provider",
        )


def test_anthropic_planner_initialization():
    """Test that AnthropicPlanner can be initialized."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        pytest.skip("No Anthropic API key available")

    planner = AnthropicPlanner(excluded_actions=["drag_and_drop"])

    assert planner is not None
    assert hasattr(planner, "llm")
    assert hasattr(planner, "llm_with_tools")


def test_gemini_planner_initialization():
    """Test that GeminiPlanner can be initialized."""
    if not os.getenv("GOOGLE_API_KEY") and not os.getenv("GEMINI_API_KEY"):
        pytest.skip("No Gemini API key available")

    planner = GeminiPlanner(excluded_actions=["drag_and_drop"])

    assert planner is not None
    assert hasattr(planner, "client")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
