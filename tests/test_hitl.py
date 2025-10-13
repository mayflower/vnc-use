#!/usr/bin/env python3
"""Test HITL callback integration."""


from vnc_use.agent import VncUseAgent


def test_hitl_callback():
    """Test that HITL callback is invoked when safety decision requires confirmation."""
    print("Testing HITL callback integration...")

    # Track callback invocations
    callback_invoked = False
    callback_safety = None
    callback_pending = None

    async def mock_callback(safety_decision: dict, pending_calls: list) -> bool:
        """Mock callback that records invocation."""
        nonlocal callback_invoked, callback_safety, callback_pending
        callback_invoked = True
        callback_safety = safety_decision
        callback_pending = pending_calls
        print(f"✓ Callback invoked with safety: {safety_decision}")
        print(f"✓ Callback invoked with pending: {pending_calls}")
        # Auto-approve for testing
        return True

    # Create agent with callback
    agent = VncUseAgent(
        vnc_server="localhost::5901",
        vnc_password="test",
        hitl_mode=True,
        hitl_callback=mock_callback,
    )

    # Verify callback is set
    assert agent.hitl_callback is not None, "HITL callback not set"
    print("✓ Agent created with HITL callback")

    # Test the _hitl_gate_node directly
    state = {
        "safety": {"action": "require_confirmation", "reason": "Test risky action"},
        "pending_calls": [{"name": "click_at", "args": {"x": 100, "y": 200}}],
    }

    print("\n✓ Invoking HITL gate node...")
    result = agent._hitl_gate_node(state)

    # Verify callback was invoked
    assert callback_invoked, "Callback was not invoked"
    assert callback_safety is not None, "Safety decision not passed to callback"
    assert callback_pending is not None, "Pending calls not passed to callback"
    assert result.get("done") is not True, "Action was denied unexpectedly"

    print("\n✅ HITL CALLBACK TEST PASSED")
    print("  ✓ Callback mechanism working")
    print("  ✓ Safety decision passed correctly")
    print("  ✓ Pending calls passed correctly")
    print("  ✓ Approval flows through correctly")


def test_hitl_denial():
    """Test that denial works correctly."""
    print("\n\nTesting HITL denial...")

    async def deny_callback(safety_decision: dict, pending_calls: list) -> bool:
        """Mock callback that denies."""
        print(f"✓ Callback denying action: {pending_calls}")
        return False

    agent = VncUseAgent(
        vnc_server="localhost::5901",
        vnc_password="test",
        hitl_mode=True,
        hitl_callback=deny_callback,
    )

    state = {
        "safety": {"action": "require_confirmation", "reason": "Test risky action"},
        "pending_calls": [{"name": "key_combination", "args": {"keys": "control+alt+delete"}}],
    }

    result = agent._hitl_gate_node(state)

    # Verify denial
    assert result.get("done") is True, "Action should be marked done after denial"
    assert "denied" in result.get("error", "").lower(), "Error should mention denial"

    print("\n✅ HITL DENIAL TEST PASSED")
    print("  ✓ Denial mechanism working")
    print("  ✓ Error message correct")


if __name__ == "__main__":
    test_hitl_callback()
    test_hitl_denial()
    print("\n\n🎉 ALL HITL TESTS PASSED")
