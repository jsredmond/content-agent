#!/usr/bin/env python3
"""Main entry point for the Content Agent.

This module provides the CLI interface for running the content curation pipeline.

Usage:
    python -m src.main           # Run with live data
    python -m src.main --mock    # Run with mock data (for testing)
    python -m src.main -v        # Run with verbose logging

Requirements: 10.1
"""

import argparse
import sys

from src.agent.runner import run


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments.
    
    Args:
        args: Command line arguments. If None, uses sys.argv.
        
    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        prog="content-agent",
        description="Content Agent - AI-assisted blog article curation pipeline",
    )
    
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock data instead of live fetching (for testing)",
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging output",
    )
    
    return parser.parse_args(args)


def main(args: list[str] | None = None) -> int:
    """Main entry point for the content agent.
    
    Args:
        args: Command line arguments. If None, uses sys.argv.
        
    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    parsed = parse_args(args)
    return run(mock=parsed.mock, verbose=parsed.verbose)


if __name__ == "__main__":
    sys.exit(main())
