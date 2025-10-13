"""MCP server for VNC Computer Use agent.

Provides a streaming MCP tool that executes tasks on VNC desktops,
reporting progress, observations, and screenshots in real-time.

Security: VNC credentials are stored securely using a credential store
(OS keyring, .netrc file, or environment variables). Never pass passwords
as tool parameters to avoid exposing them to LLMs.
"""

import base64
import logging
from typing import Any

from fastmcp import Context, FastMCP

from .agent import VncUseAgent
from .credential_store import get_default_store
from .planners.gemini import compress_screenshot


logger = logging.getLogger(__name__)

# Create MCP server instance
mcp = FastMCP("VNC Computer Use Agent")

# Initialize credential store
credential_store = get_default_store()


@mcp.tool()
async def execute_vnc_task(
    hostname: str,
    task: str,
    step_limit: int = 40,
    timeout: int = 300,
    ctx: Context | None = None,
) -> dict[str, Any]:
    """Execute a task on a VNC desktop with streaming progress updates.

    This tool connects to a VNC server, executes the given task using the
    Gemini 2.5 Computer Use model, and streams progress updates, observations,
    and screenshots back to the client.

    Security: Credentials are looked up from the credential store by hostname.
    Never pass passwords as tool parameters - they would be exposed to the LLM.

    Args:
        hostname: VNC server hostname (e.g., "vnc-prod-01.example.com" or "vnc-desktop")
                  Used to look up credentials from credential store.
        task: Task description to execute
        step_limit: Maximum number of steps (default: 40)
        timeout: Timeout in seconds (default: 300)
        ctx: FastMCP context for streaming (injected automatically)

    Returns:
        Result dictionary with:
        - success: Whether task completed successfully
        - run_id: Unique run identifier
        - run_dir: Path to run artifacts directory
        - steps: Number of steps executed
        - error: Error message (if failed)

    Raises:
        ValueError: If credentials for hostname not found in credential store
    """
    if ctx:
        await ctx.info(f"Starting VNC task: {task}")
        await ctx.info(f"Looking up credentials for hostname: {hostname}")

    try:
        # Look up credentials from store
        credentials = credential_store.get(hostname)
        if not credentials:
            error_msg = (
                f"No credentials found for hostname '{hostname}'. "
                f"Configure credentials using: vnc-use credentials set {hostname}"
            )
            logger.error(error_msg)
            if ctx:
                await ctx.info(f"✗ Error: {error_msg}")
            return {
                "success": False,
                "error": error_msg,
                "run_id": None,
                "run_dir": None,
                "steps": 0,
            }

        if ctx:
            await ctx.info(f"Found credentials for {hostname}")
            await ctx.info(f"Connecting to VNC server: {credentials.server}")

        # Create HITL callback for user approval via MCP elicitation
        async def hitl_callback(safety_decision: dict, pending_calls: list) -> bool:
            """Request user approval via MCP elicitation.

            Args:
                safety_decision: Gemini's safety decision
                pending_calls: List of pending function calls

            Returns:
                True if user approved, False if denied
            """
            if not ctx:
                # No context for elicitation, auto-approve
                logger.warning("No MCP context for HITL, auto-approving")
                return True

            reason = (
                safety_decision.get("reason", "Unknown reason")
                if safety_decision
                else "Unknown"
            )
            actions = ", ".join(call["name"] for call in pending_calls)

            await ctx.info(f"⚠️  Safety confirmation required: {reason}")
            await ctx.info(f"📋 Proposed actions: {actions}")

            try:
                result = await ctx.elicit(
                    message=f"Safety confirmation required: {reason}\n"
                    f"Proposed actions: {actions}\n"
                    f"Approve execution?",
                    response_type=None,  # Simple yes/no approval
                )

                if result.action == "accept":
                    await ctx.info("✓ User approved action")
                    return True
                if result.action == "decline":
                    await ctx.info("✗ User declined action")
                    return False
                # cancel
                await ctx.info("✗ User cancelled operation")
                return False

            except Exception as e:
                logger.error(f"Elicitation failed: {e}")
                await ctx.info(f"✗ Approval request failed: {e}")
                return False

        # Create agent with HITL enabled and elicitation callback
        agent = VncUseAgent(
            vnc_server=credentials.server,
            vnc_password=credentials.password,
            step_limit=step_limit,
            seconds_timeout=timeout,
            hitl_mode=True,  # Enable HITL for risky actions
            hitl_callback=hitl_callback
            if ctx
            else None,  # Use elicitation when context available
        )

        # Monkey-patch agent nodes to add streaming
        if ctx:
            agent = _wrap_agent_for_streaming(agent, ctx, step_limit)

        # Execute task
        result = agent.run(task)

        # Report completion
        if ctx:
            await ctx.info("Task execution completed")
            if result.get("success"):
                await ctx.info(
                    f"✓ Task completed successfully in {result['final_state'].get('step', 0)} steps"
                )
            else:
                error = result.get("error") or result.get("final_state", {}).get(
                    "error", "Unknown error"
                )
                await ctx.info(f"✗ Task failed: {error}")

        return {
            "success": result.get("success", False),
            "run_id": result.get("run_id"),
            "run_dir": result.get("run_dir"),
            "steps": result.get("final_state", {}).get("step", 0),
            "error": result.get("error") or result.get("final_state", {}).get("error"),
        }

    except Exception as e:
        error_msg = f"Task execution failed: {e}"
        logger.error(error_msg, exc_info=True)
        if ctx:
            await ctx.info(f"✗ Error: {error_msg}")
        return {
            "success": False,
            "error": error_msg,
            "run_id": None,
            "run_dir": None,
            "steps": 0,
        }


def _wrap_agent_for_streaming(
    agent: VncUseAgent,
    ctx: Context,
    step_limit: int,
) -> VncUseAgent:
    """Wrap agent nodes to add streaming capabilities.

    Args:
        agent: Agent instance to wrap
        ctx: FastMCP context for streaming
        step_limit: Maximum steps for progress reporting

    Returns:
        Modified agent with streaming support
    """
    # Save original node methods
    original_propose = agent._propose_node
    original_act = agent._act_node

    async def _async_report(message: str) -> None:
        """Helper to report info messages."""
        try:
            await ctx.info(message)
        except Exception as e:
            logger.warning(f"Failed to report message: {e}")

    async def _async_progress(step: int, total: int, message: str) -> None:
        """Helper to report progress."""
        try:
            await ctx.report_progress(
                progress=step,
                total=total,
                message=message,
            )
        except Exception as e:
            logger.warning(f"Failed to report progress: {e}")

    async def _async_screenshot(screenshot_png: bytes, step: int) -> None:
        """Helper to stream compressed screenshot."""
        try:
            # Compress to 256px for streaming (smaller than Gemini's 512px)
            compressed = compress_screenshot(screenshot_png, max_width=256)
            encoded = base64.b64encode(compressed).decode("utf-8")
            await ctx.info(
                f"[Screenshot Step {step}] data:image/png;base64,{encoded[:100]}... ({len(compressed)} bytes)"
            )
        except Exception as e:
            logger.warning(f"Failed to stream screenshot: {e}")

    def streaming_propose_node(state: dict) -> dict:
        """Wrapped propose node with streaming."""
        step = state["step"]

        # Report progress
        import asyncio

        try:
            asyncio.run(
                _async_progress(
                    step, step_limit, f"Step {step}: Analyzing screenshot..."
                )
            )
        except Exception as e:
            logger.warning(f"Progress reporting failed: {e}")

        # Call original propose
        result = original_propose(state)

        # Stream observation if available
        observation = result.get("observation", "")
        if observation:
            try:
                # Truncate long observations
                obs_preview = (
                    observation[:200] + "..." if len(observation) > 200 else observation
                )
                asyncio.run(
                    _async_report(f"[Step {step}] Model observes: {obs_preview}")
                )
            except Exception as e:
                logger.warning(f"Observation streaming failed: {e}")

        # Report proposed actions
        proposed = result.get("proposed_actions", [])
        if proposed:
            try:
                action_summary = ", ".join(a["name"] for a in proposed[:3])
                if len(proposed) > 3:
                    action_summary += f" (+{len(proposed) - 3} more)"
                asyncio.run(_async_report(f"[Step {step}] Proposed: {action_summary}"))
            except Exception as e:
                logger.warning(f"Action streaming failed: {e}")

        return result

    def streaming_act_node(state: dict) -> dict:
        """Wrapped act node with streaming."""
        step = state["step"]

        # Call original act
        result = original_act(state)

        # Stream screenshot if available
        screenshot_png = result.get("last_screenshot_png")
        if screenshot_png:
            import asyncio

            try:
                asyncio.run(_async_screenshot(screenshot_png, step))
            except Exception as e:
                logger.warning(f"Screenshot streaming failed: {e}")

        # Report action result
        step_logs = result.get("step_logs", [])
        if step_logs:
            last_log = step_logs[-1]
            action = last_log.get("executed_action", {})
            result_text = last_log.get("result", "")

            import asyncio

            try:
                action_name = action.get("name", "unknown")
                args = action.get("args", {})
                args_str = ", ".join(f"{k}={v}" for k, v in args.items())
                status = "✓" if "Success" in result_text else "✗"
                asyncio.run(
                    _async_report(
                        f"[Step {step}] {status} Executed: {action_name}({args_str})"
                    )
                )
            except Exception as e:
                logger.warning(f"Result streaming failed: {e}")

        return result

    # Replace node methods
    agent._propose_node = streaming_propose_node
    agent._act_node = streaming_act_node

    return agent
