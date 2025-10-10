"""CLI entrypoint for vnc-use."""

import argparse
import logging
import sys

from .agent import VncUseAgent


def setup_logging(verbose: bool = False) -> None:
    """Setup logging configuration.

    Args:
        verbose: Enable verbose (DEBUG) logging
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main() -> None:
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="VNC Computer Use Agent powered by Gemini",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with default VNC server (localhost::5901)
  vnc-use run --task "Open a browser and search for LangGraph"

  # Specify custom VNC server
  vnc-use run --vnc remote-host:5901 --password secret --task "..."

  # Disable HITL safety confirmations
  vnc-use run --no-hitl --task "..."

  # Set custom limits
  vnc-use run --step-limit 50 --timeout 600 --task "..."
        """,
    )

    parser.add_argument("command", choices=["run"], help="Command to execute")
    parser.add_argument("--task", required=True, help="Task description for the agent")
    parser.add_argument(
        "--vnc",
        default="localhost::5901",
        help="VNC server address (default: localhost::5901)",
    )
    parser.add_argument("--password", help="VNC password")
    parser.add_argument(
        "--step-limit",
        type=int,
        default=40,
        help="Maximum number of steps (default: 40)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Timeout in seconds (default: 300)",
    )
    parser.add_argument(
        "--no-hitl",
        action="store_true",
        help="Disable human-in-the-loop safety confirmations",
    )
    parser.add_argument(
        "--excluded-actions",
        nargs="+",
        help="Actions to exclude (e.g., open_web_browser)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    if args.command == "run":
        logger.info("Starting VNC Computer Use Agent")
        logger.info(f"Task: {args.task}")
        logger.info(f"VNC Server: {args.vnc}")

        try:
            # Initialize agent
            agent = VncUseAgent(
                vnc_server=args.vnc,
                vnc_password=args.password,
                step_limit=args.step_limit,
                seconds_timeout=args.timeout,
                hitl_mode=not args.no_hitl,
                excluded_actions=args.excluded_actions,
            )

            # Run task
            result = agent.run(args.task)

            # Display results
            if result.get("success"):
                logger.info("✓ Task completed successfully!")
                print("\n✓ Task completed!")
                print(f"Run ID: {result.get('run_id')}")
                print(f"Artifacts: {result.get('run_dir')}")
                sys.exit(0)
            else:
                error = result.get("error", "Unknown error")
                logger.error(f"✗ Task failed: {error}")
                print(f"\n✗ Task failed: {error}")
                if result.get("run_dir"):
                    print(f"Run artifacts: {result.get('run_dir')}")
                sys.exit(1)

        except KeyboardInterrupt:
            logger.info("Interrupted by user")
            print("\n⚠ Interrupted by user")
            sys.exit(130)

        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            print(f"\n✗ Fatal error: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
