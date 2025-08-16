"""
MCP Browser Tools Server

A FastMCP server that provides browser automation tools over SSE.
Uses Selenium for browser automation and exposes MCP-compliant tools.
"""

import sys
import threading
import os
import asyncio
from typing import Dict, Any
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastmcp import FastMCP
from fastmcp.server.http import create_sse_app
from loguru import logger
from dotenv import load_dotenv

from navmcp.browser import BrowserManager
from navmcp.tools import (
    setup_fetch_tools,
    setup_parse_tools,
    setup_interact_tools,
    setup_search_tools,
    setup_convert_tools,
    setup_pdf_tools,
    setup_save_tools,
    setup_control_tools,
)

# Load environment variables
load_dotenv()
# --- Server shutdown endpoint ---

# Configuration
MCP_HOST = os.getenv("MCP_HOST", "127.0.0.1")
MCP_PORT = int(os.getenv("MCP_PORT", "3333"))
CORS_ORIGINS = os.getenv("MCP_CORS_ORIGINS", "http://127.0.0.1,http://localhost").split(",")
SSE_PATH = os.getenv("MCP_SSE_PATH", "/sse")
MESSAGE_PATH = os.getenv("MCP_MESSAGE_PATH", "/messages")
DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", ".data/downloads")
LOG_DIR = Path(".data/logs")

# Ensure directories exist
Path(DOWNLOAD_DIR).mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Configure logging
logger.add(
    LOG_DIR / "server.log",
    rotation="10 MB",
    retention="7 days",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} | {message}"
)

# Initialize browser manager
browser_manager = None
_browser_manager_initialized = False

@asynccontextmanager
async def lifespan(app):
    """Lifespan context manager for startup and shutdown."""
    global browser_manager, _browser_manager_initialized
    # Startup
    logger.info("Starting MCP Browser Tools server")
    if not _browser_manager_initialized:
        browser_manager = BrowserManager()
        await browser_manager.start()
        _browser_manager_initialized = True
        logger.info("Browser manager initialized")
    
    yield
    
    # Shutdown
    if browser_manager:
        await browser_manager.stop()
        logger.info("Browser manager stopped")

# Initialize FastMCP with proper settings
mcp = FastMCP("navmcp", version="1.0.0")

# Helper to ensure browser_manager is initialized
async def get_browser_manager():
    global browser_manager, _browser_manager_initialized
    if browser_manager is None and not _browser_manager_initialized:
        logger.info("Initializing browser manager for testing context")
        browser_manager = BrowserManager()
        await browser_manager.start()
        _browser_manager_initialized = True
    elif browser_manager is None:
        raise RuntimeError("Browser manager is not initialized. Make sure the server is started with the lifespan context.")
    return browser_manager

setup_fetch_tools(mcp, get_browser_manager)
setup_parse_tools(mcp, get_browser_manager)
setup_interact_tools(mcp, get_browser_manager)
setup_search_tools(mcp, get_browser_manager)
setup_convert_tools(mcp, get_browser_manager)
setup_pdf_tools(mcp, get_browser_manager)
setup_save_tools(mcp)
setup_control_tools(mcp)

# Create Starlette app from FastMCP for SSE transport
app = create_sse_app(
    server=mcp,
    message_path=MESSAGE_PATH, 
    sse_path=SSE_PATH
)


# Custom ASGI middleware to allow chat to continue when MCP server is down
from starlette.middleware.base import BaseHTTPMiddleware

class MCPServerAvailabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Only block MCP tool requests if server is down
        # Remove invalid is_running check; always allow requests to continue
        return await call_next(request)


# ...existing code...


# Set the lifespan on the app
app.router.lifespan_context = lifespan

# Add custom and CORS middleware
app.add_middleware(MCPServerAvailabilityMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Health check endpoint
async def health_check(request):
    """Health check endpoint for monitoring."""
    return JSONResponse(
    content={"status": "ok", "server": "navmcp", "version": "1.0.0"},
        status_code=200
    )

# Add health route to Starlette app
app.add_route("/health", health_check, methods=["GET"])


# --- MCP tools: browser control ---
@mcp.tool()
async def start_browser() -> Dict[str, Any]:
    """Start the browser (if not already running)."""
    bm = await get_browser_manager()
    await bm.start()
    return {"status": "started"}

@mcp.tool()
async def stop_browser() -> Dict[str, Any]:
    """Stop the browser."""
    bm = await get_browser_manager()
    await bm.stop()
    return {"status": "stopped"}

@mcp.tool()
async def restart_browser() -> Dict[str, Any]:
    """Restart the browser."""
    bm = await get_browser_manager()
    await bm.restart_driver()
    return {"status": "restarted"}
if __name__ == "__main__":
    import asyncio
    asyncio.run(mcp.run_http_async(host=MCP_HOST, port=MCP_PORT))
