"""LangGraph agent for VNC Computer Use."""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from .backends.vnc import VNCController
from .logging_utils import RunLogger
from .planners.gemini import GeminiComputerUse
from .safety import HITLGate, requires_confirmation, should_block
from .types import CUAState


logger = logging.getLogger(__name__)


class VncUseAgent:
    """VNC Computer Use Agent powered by Gemini and LangGraph.

    Runs an observe → propose → act loop with HITL safety gates.
    """

    def __init__(
        self,
        vnc_server: str = "localhost::5901",
        vnc_password: str | None = None,
        screen_size: tuple[int, int] = (1440, 900),
        excluded_actions: list[str] | None = None,
        step_limit: int = 40,
        seconds_timeout: int = 300,
        hitl_mode: bool = True,
        hitl_callback: Callable[[dict, list], Awaitable[bool]] | None = None,
        api_key: str | None = None,
    ) -> None:
        """Initialize VNC Use Agent.

        Args:
            vnc_server: VNC server address
            vnc_password: VNC password
            screen_size: Default screen size (auto-detected from screenshots)
            excluded_actions: Actions to exclude from Computer Use tool.
                Defaults to excluding browser-specific actions (open_web_browser,
                navigate, go_back, go_forward, search) that cannot be reliably
                implemented via VNC mouse/keyboard simulation.
            step_limit: Maximum number of steps
            seconds_timeout: Wall-clock timeout in seconds
            hitl_mode: Enable human-in-the-loop for safety
            hitl_callback: Optional async callback for HITL decisions.
                Called with (safety_decision, pending_calls) and should return bool.
                If not provided, uses LangGraph interrupt mechanism.
            api_key: Google API key (defaults to GOOGLE_API_KEY env)
        """
        self.vnc_server = vnc_server
        self.vnc_password = vnc_password
        self.screen_size = screen_size
        self.step_limit = step_limit
        self.seconds_timeout = seconds_timeout
        self.hitl_mode = hitl_mode
        self.hitl_callback = hitl_callback

        # Default exclusions for browser-specific actions we cannot implement via VNC
        if excluded_actions is None:
            excluded_actions = [
                "open_web_browser",  # Cannot reliably implement via desktop clicking
                "navigate",  # Requires browser URL bar API
                "go_back",  # Requires browser history API
                "go_forward",  # Requires browser history API
                "search",  # Requires browser search API
            ]

        # Initialize components
        self.vnc = VNCController()
        self.planner = GeminiComputerUse(
            excluded_actions=excluded_actions,
            api_key=api_key,
        )
        self.hitl_gate = HITLGate()
        self.run_logger: RunLogger | None = None  # Set during run()

        # Build graph
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build LangGraph state machine.

        Returns:
            Compiled graph
        """
        builder = StateGraph(CUAState)

        # Add nodes
        builder.add_node("propose", self._propose_node)
        builder.add_node("act", self._act_node)
        builder.add_node("hitl_gate", self._hitl_gate_node)

        # Add edges
        builder.add_edge(START, "propose")
        builder.add_conditional_edges(
            "propose",
            self._route_after_propose,
        )
        builder.add_conditional_edges(
            "hitl_gate",
            self._route_after_hitl,
        )
        builder.add_edge("act", "propose")

        # Compile without checkpointer for now (TODO: fix checkpointing)
        return builder.compile()

    def _propose_node(self, state: CUAState) -> dict:
        """Propose node: Call Gemini to get next actions.

        Args:
            state: Current state

        Returns:
            State updates
        """
        step = state["step"]
        logger.info(f"Step {step}: Proposing actions...")

        # Check guards
        elapsed = time.time() - state["start_time"]
        if step >= self.step_limit:
            logger.warning(f"Step limit reached: {step}/{self.step_limit}")
            return {"done": True, "error": f"Step limit reached: {self.step_limit}"}

        if elapsed >= self.seconds_timeout:
            logger.warning(f"Timeout reached: {elapsed:.1f}s/{self.seconds_timeout}s")
            return {"done": True, "error": f"Timeout reached: {self.seconds_timeout}s"}

        # Get current screenshot
        screenshot_png = state.get("last_screenshot_png")
        if not screenshot_png:
            logger.error("No screenshot available")
            return {"done": True, "error": "No screenshot available"}

        # Call Gemini with stateless approach
        try:
            response = self.planner.generate_stateless(
                task=state["task"],
                action_history=state["action_history"],
                screenshot_png=screenshot_png,
            )

            # Extract text observation/reasoning
            observation = self.planner.extract_text(response)
            logger.debug(f"Model observation: {observation[:100]}...")

            # Extract function calls
            function_calls = self.planner.extract_function_calls(response)
            logger.info(f"Received {len(function_calls)} function call(s)")

            # Extract safety decision
            safety_decision = self.planner.extract_safety_decision(response)

            if not function_calls:
                logger.info("No function calls - task complete")
                return {
                    "done": True,
                    "pending_calls": [],
                    "safety": safety_decision,
                    "observation": observation,
                }

            # Check for blocking safety decision
            if should_block(safety_decision):
                reason = safety_decision.get("reason", "Unknown")
                logger.warning(f"Action blocked by safety: {reason}")
                return {
                    "done": True,
                    "error": f"Blocked by safety: {reason}",
                    "safety": safety_decision,
                    "observation": observation,
                }

            return {
                "pending_calls": function_calls,
                "safety": safety_decision,
                "step": step + 1,
                "observation": observation,
                "proposed_actions": function_calls,
            }

        except Exception as e:
            logger.error(f"Propose failed: {e}")
            return {"done": True, "error": str(e)}

    def _act_node(self, state: CUAState) -> dict:
        """Act node: Execute one pending function call.

        Args:
            state: Current state

        Returns:
            State updates
        """
        pending = state["pending_calls"]
        if not pending:
            logger.warning("Act called with no pending calls")
            return {"done": True}

        # Pop first call
        call = pending[0]
        remaining = pending[1:]

        function_name = call["name"]
        args = call["args"]

        logger.info(f"Executing: {function_name}({args})")

        # Format action text
        args_str = ", ".join(f"{k}={v}" for k, v in args.items())
        action_text = f"Executed {function_name}({args_str})"

        step_number = state["step"]

        try:
            # Execute action
            result = self.vnc.execute_action(function_name, args)

            # Add to text history
            if result.error:
                action_text += f" - Error: {result.error}"
                result_text = f"Error: {result.error}"
            else:
                action_text += " - Success"
                result_text = "Success"

            updated_history = state["action_history"] + [action_text]

            # Save screenshot after action
            screenshot_path = None
            if self.run_logger and result.screenshot_png:
                path = self.run_logger.log_screenshot(
                    step_number, result.screenshot_png, f"step_{step_number:03d}_after"
                )
                screenshot_path = str(path.name)

            # Create step log
            from .types import StepLog

            step_log: StepLog = {
                "step_number": step_number,
                "observation": state.get("observation", ""),
                "proposed_actions": state.get("proposed_actions", []),
                "executed_action": {"name": function_name, "args": args},
                "result": result_text,
                "screenshot_path": screenshot_path,
                "timestamp": time.time(),
            }

            updated_step_logs = state.get("step_logs", []) + [step_log]

            return {
                "pending_calls": remaining,
                "last_screenshot_png": result.screenshot_png,
                "action_history": updated_history,
                "step_logs": updated_step_logs,
            }

        except Exception as e:
            logger.error(f"Action failed: {e}")
            # Still try to get screenshot for error reporting
            try:
                screenshot = self.vnc.screenshot_png()
            except:
                screenshot = b""

            action_text += f" - Exception: {e!s}"
            result_text = f"Exception: {e!s}"
            updated_history = state["action_history"] + [action_text]

            # Save screenshot even on error
            screenshot_path = None
            if self.run_logger and screenshot:
                path = self.run_logger.log_screenshot(
                    step_number, screenshot, f"step_{step_number:03d}_error"
                )
                screenshot_path = str(path.name)

            # Create step log for error
            from .types import StepLog

            step_log: StepLog = {
                "step_number": step_number,
                "observation": state.get("observation", ""),
                "proposed_actions": state.get("proposed_actions", []),
                "executed_action": {"name": function_name, "args": args},
                "result": result_text,
                "screenshot_path": screenshot_path,
                "timestamp": time.time(),
            }

            updated_step_logs = state.get("step_logs", []) + [step_log]

            return {
                "pending_calls": remaining,
                "last_screenshot_png": screenshot,
                "action_history": updated_history,
                "step_logs": updated_step_logs,
                "error": str(e),
            }

    def _hitl_gate_node(self, state: CUAState) -> dict:
        """HITL gate node: Wait for user approval.

        Args:
            state: Current state

        Returns:
            State updates (interrupts if no decision)
        """
        logger.info("HITL gate: Waiting for user decision...")

        safety = state["safety"]
        pending = state["pending_calls"]

        # Log the confirmation request
        self.hitl_gate.request_confirmation(safety, pending)

        # Use callback if provided, otherwise use LangGraph interrupt
        if self.hitl_callback:
            logger.debug("Using HITL callback for user decision")
            try:
                # Call async callback from sync context
                approved = asyncio.run(self.hitl_callback(safety, pending))

                if not approved:
                    logger.warning("User denied action via callback")
                    return {"done": True, "error": "User denied action"}

                logger.info("User approved action via callback")
                return {}
            except Exception as e:
                logger.error(f"HITL callback failed: {e}")
                return {"done": True, "error": f"HITL callback failed: {e}"}
        else:
            # Use LangGraph interrupt mechanism
            logger.debug("Using LangGraph interrupt for user decision")
            decision = interrupt(
                {
                    "type": "hitl_confirmation",
                    "reason": safety.get("reason") if safety else "Unknown",
                    "pending_calls": pending,
                }
            )

            # Process user decision
            if decision == "deny":
                logger.warning("User denied action")
                return {"done": True, "error": "User denied action"}

            logger.info("User approved action")
            return {}

    def _route_after_propose(self, state: CUAState) -> str:
        """Route after propose node.

        Args:
            state: Current state

        Returns:
            Next node name
        """
        if state["done"]:
            return END

        # Check if HITL confirmation required
        if self.hitl_mode and requires_confirmation(state.get("safety")):
            return "hitl_gate"

        # Continue to act
        return "act"

    def _route_after_hitl(self, state: CUAState) -> str:
        """Route after HITL gate.

        Args:
            state: Current state

        Returns:
            Next node name
        """
        if state["done"]:
            return END

        return "act"

    def run(self, task: str, thread_id: str | None = None) -> dict[str, Any]:
        """Run the agent on a task.

        Args:
            task: User's task description
            thread_id: Optional thread ID for resumable runs

        Returns:
            Final state and run artifacts
        """
        logger.info(f"Starting task: {task}")

        # Initialize run logger
        run_logger = RunLogger(task=task)
        self.run_logger = run_logger  # Make it available to nodes

        # Connect to VNC
        try:
            self.vnc.connect(self.vnc_server, self.vnc_password)
            logger.info("VNC connected")
        except Exception as e:
            logger.error(f"VNC connection failed: {e}")
            return {"error": f"VNC connection failed: {e}"}

        try:
            # Capture initial screenshot
            initial_screenshot = self.vnc.screenshot_png()
            run_logger.log_screenshot(0, initial_screenshot, "initial")
            logger.info("Initial screenshot captured")

            # Initialize state with text-only history
            initial_state: CUAState = {
                "task": task,
                "action_history": [],
                "step_logs": [],
                "pending_calls": [],
                "last_screenshot_png": initial_screenshot,
                "step": 0,
                "done": False,
                "safety": None,
                "start_time": time.time(),
                "error": None,
            }

            # Run graph with increased recursion limit
            logger.info("Invoking graph...")
            final_state = self.graph.invoke(
                initial_state,
                config={"recursion_limit": 100},  # Allow up to 100 steps
            )
            logger.info("Graph execution completed")

            # Finalize logging
            metadata_path = run_logger.finalize(
                done=final_state.get("done", False) if final_state else False,
                final_state=final_state or {},
            )

            logger.info(f"Task completed. Run artifacts: {run_logger.get_run_dir()}")

            return {
                "success": final_state.get("done", False) if final_state else False,
                "final_state": final_state,
                "run_id": run_logger.get_run_id(),
                "run_dir": str(run_logger.get_run_dir()),
                "metadata": str(metadata_path),
            }

        except Exception as e:
            logger.error(f"Agent failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "run_id": run_logger.get_run_id(),
                "run_dir": str(run_logger.get_run_dir()),
            }

        finally:
            self.vnc.disconnect()
            logger.info("VNC disconnected")
