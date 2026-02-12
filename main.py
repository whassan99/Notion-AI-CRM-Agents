"""
Main entry point for the Notion AI CRM Copilot.

Usage:
    python main.py              # Run full pipeline on all leads
    python main.py --limit 5    # Process only first 5 leads
    python main.py --dry-run    # Test with sample data, no Notion writes
"""

import sys
import logging
import argparse

from config import Config
from pipeline import run_pipeline


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Notion AI CRM Copilot — AI-powered lead intelligence",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py              Process all leads
  python main.py --limit 3    Process first 3 leads only
  python main.py --dry-run    Test with sample data (no Notion writes)
        """,
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of leads to process (default: all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Use sample leads and skip Notion writes",
    )

    args = parser.parse_args()

    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    # Validate configuration
    try:
        Config.validate(require_notion=not args.dry_run)
    except ValueError as e:
        print(f"\nConfiguration error: {e}\n")
        sys.exit(1)

    # Run the pipeline
    try:
        result = run_pipeline(limit=args.limit, dry_run=args.dry_run)
        if result.failed and not result.succeeded:
            sys.exit(1)
    except KeyboardInterrupt:
        print("\nPipeline interrupted by user")
        sys.exit(0)
    except Exception as e:
        logging.getLogger(__name__).error("Pipeline failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
