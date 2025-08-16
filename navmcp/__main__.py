"""
MCP Browser Tools Server CLI

Command-line interface for starting the MCP Browser Tools server.
"""

import argparse
import asyncio
import sys
from pathlib import Path

try:
    import uvicorn
except ImportError:
    print("Error: uvicorn is not installed. Please run: pip install -r requirements.txt")
    sys.exit(1)

def create_parser() -> argparse.ArgumentParser:
    """Create command line argument parser."""
    parser = argparse.ArgumentParser(
        prog="mcp-browser",
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
    
    return parser


def start_server(host: str, port: int, reload: bool = False, log_level: str = "info") -> None:
    """Start the MCP server using uvicorn."""
    print(f"Starting MCP Browser Tools Server...")
    print(f"Host: {host}")
    print(f"Port: {port}")
    print(f"Reload: {reload}")
    print(f"Log level: {log_level}")
    print()
    
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
            log_level=args.log_level
        )
    else:
        print(f"Unknown command: {args.command}")
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
