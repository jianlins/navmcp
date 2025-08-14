"""
MCP Browser Tools Server

A FastMCP server that provides browser automation tools over SSE.
Uses Selenium for browser automation and exposes MCP-compliant tools.
"""

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

from server.browser import BrowserManager
from server.tools.fetch import setup_fetch_tools
from server.tools.parse import setup_parse_tools
from server.tools.interact import setup_interact_tools
from server.tools.pdf import setup_pdf_tools
from server.tools.search import setup_search_tools
from server.tools.convert import setup_convert_tools

# Load environment variables
load_dotenv()

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

@asynccontextmanager
async def lifespan(app):
    """Lifespan context manager for startup and shutdown."""
    global browser_manager
    # Startup
    logger.info("Starting MCP Browser Tools server")
    browser_manager = BrowserManager()
    await browser_manager.start()
    logger.info("Browser manager initialized")
    
    yield
    
    # Shutdown
    if browser_manager:
        await browser_manager.stop()
        logger.info("Browser manager stopped")

# Initialize FastMCP with proper settings
mcp = FastMCP("mcp-browser", version="1.0.0")

# Setup all tools
setup_fetch_tools(mcp, lambda: browser_manager)
setup_parse_tools(mcp, lambda: browser_manager)
setup_interact_tools(mcp, lambda: browser_manager)
setup_pdf_tools(mcp, lambda: browser_manager)
setup_search_tools(mcp, lambda: browser_manager)
setup_convert_tools(mcp, lambda: browser_manager)

# Create Starlette app from FastMCP for SSE transport
app = create_sse_app(
    server=mcp,
    message_path=MESSAGE_PATH, 
    sse_path=SSE_PATH
)

# Set the lifespan on the app
app.router.lifespan_context = lifespan

# Add CORS middleware
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
        content={"status": "ok", "server": "mcp-browser", "version": "1.0.0"},
        status_code=200
    )

# Add health route to Starlette app
app.add_route("/health", health_check, methods=["GET"])

if __name__ == "__main__":
    import asyncio
    asyncio.run(mcp.run_http_async(host=MCP_HOST, port=MCP_PORT))