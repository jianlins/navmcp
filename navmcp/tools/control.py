"""
Control tools for MCP browser server (shutdown, etc.)
"""
import sys
import threading
from typing import Dict, Any
from loguru import logger
from fastmcp import FastMCP

def setup_control_tools(mcp: FastMCP):
    @mcp.tool()
    async def shutdown_server() -> Dict[str, Any]:
        """
        Gracefully shut down the MCP server process. Should only be called when all clients are finished.
        Returns a status dict. Shutdown is performed in a background thread to allow response to be sent.
        """
        import os
        import time

        logger.info("Shutting down MCP server process via MCP tool.")

        def delayed_exit():
            time.sleep(1)
            os._exit(0)

        threading.Thread(target=delayed_exit, daemon=True).start()
        return {"status": "server shutting down"}
