"""
MCP Browser Tools Server CLI

Command-line interface for starting the MCP Browser Tools server.
"""

import argparse
import asyncio
import sys
import os
from pathlib import Path

try:
    import uvicorn
except ImportError:
    print("Error: uvicorn is not installed. Please run: pip install -r requirements.txt")
    sys.exit(1)

def create_parser() -> argparse.ArgumentParser:
    """Create command line argument parser."""
    parser = argparse.ArgumentParser(
    prog="navmcp",
        description="MCP Browser Tools Server - Browser automation tools for MCP clients"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Start command
    start_parser = subparsers.add_parser("start", help="Start the MCP server")
    start_parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)"
    )
    start_parser.add_argument(
        "--port",
        type=int,
        default=3333,
        help="Port to bind to (default: 3333)"
    )
    start_parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development"
    )
    start_parser.add_argument(
        "--log-level",
        choices=["critical", "error", "warning", "info", "debug", "trace"],
        default="info",
        help="Log level (default: info)"
    )
    headless_group = start_parser.add_mutually_exclusive_group()
    headless_group.add_argument(
        "--headless",
        dest="headless",
        action="store_true",
        default=None,
        help="Run browser in headless mode (default: true)"
    )
    headless_group.add_argument(
        "--no-headless",
        dest="headless",
        action="store_false",
        default=None,
        help="Run browser with GUI (not headless)"
    )
    
    return parser


def start_server(host: str, port: int, reload: bool = False, log_level: str = "info", headless: bool = None) -> None:
    """Start the MCP server using uvicorn."""
    print(f"Starting MCP Browser Tools Server...")
    print(f"Host: {host}")
    print(f"Port: {port}")
    print(f"Reload: {reload}")
    print(f"Log level: {log_level}")
    print(f"Headless: {headless}")
    print()

    # Headless mode is now only controlled by command parameters, not environment variable
    # (removed BROWSER_HEADLESS logic)

    try:
        uvicorn.run(
            "navmcp.app:app",
            host=host,
            port=port,
            reload=reload,
            log_level=log_level,
            access_log=True
        )
    except KeyboardInterrupt:
        print("\nServer stopped by user")
    except Exception as e:
        print(f"Error starting server: {e}")
        sys.exit(1)


def main():
    """Main entry point for the CLI."""
    parser = create_parser()
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    if args.command == "start":
        start_server(
            host=args.host,
            port=args.port,
            reload=args.reload,
            log_level=args.log_level,
            headless=args.headless
        )
    else:
        print(f"Unknown command: {args.command}")
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
