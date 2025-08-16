# navmcp Browser Tools

[![PyPI version](https://img.shields.io/pypi/v/navmcp.svg)](https://pypi.org/project/navmcp/)
[![Python Version](https://img.shields.io/pypi/pyversions/navmcp.svg)](https://pypi.org/project/navmcp/)
[![License](https://img.shields.io/github/license/jianlins/navmcp.svg)](./LICENSE)
[![Coverage Status](https://img.shields.io/endpoint?url=https://gist.githubusercontent.com/jianlins/coverage-badge.json)](./)

---

## Table of Contents
- [Features](#features)
- [Quick Start](#quick-start)
- [Installation](#installation)
- [Usage](#usage)
- [Configuration](#configuration)
- [Tools Overview](#tools-overview)
- [Development](#development)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)
- [Changelog](#changelog)


A Model Context Protocol (MCP) server that provides browser automation tools over SSE (Server-Sent Events). Built with FastMCP and Selenium, this server enables MCP-capable clients to interact with web pages, extract content, perform automated browser tasks, and access academic search engines.

**Project folder:** `navmcp` (previously `mcp-browser`)





## Tool Annotations & Notifications

FastMCP supports tool annotations for improved client UX and dynamic tool management:

- **Annotations**: Add metadata to tools (title, readOnlyHint, destructiveHint, etc.) to help clients present better UI and safety controls.
- **Notifications**: FastMCP automatically sends notifications to clients when tools are added, removed, enabled, or disabled, keeping tool lists up-to-date.

**Example: Tool Annotations**
```python
@mcp.tool(
  annotations={
    "title": "Calculate Sum",
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False
  }
)
def calculate_sum(a: float, b: float) -> float:
  """Add two numbers together."""
  return a + b
```

> See [FastMCP annotations docs](https://gofastmcp.com/servers/tools#annotations) for more details.

FastMCP is async-first and supports both asynchronous (`async def`) and synchronous (`def`) tools:

- **Async tools** are preferred for I/O-bound operations (network, file, browser automation) to keep the server responsive.
- **Sync tools** work for quick, non-blocking tasks. For CPU-intensive or blocking operations, wrap them using `anyio.to_thread.run_sync` or similar techniques.

**Example: Wrapping a CPU-bound sync function as async**
```python
import anyio

def cpu_intensive_task(data: str) -> str:
  # Heavy computation
  return processed_data

@mcp.tool
async def wrapped_cpu_task(data: str) -> str:
  """CPU-intensive task wrapped to prevent blocking."""
  return await anyio.to_thread.run_sync(cpu_intensive_task, data)
```

> **Tip:** Always annotate tool parameters and return types for proper schema generation and validation. See [FastMCP async docs](https://gofastmcp.com/servers/tools) for more details.

FastMCP tools now support automatic and custom output schemas, enabling clients to receive machine-readable JSON data alongside human-readable content. This is especially useful for AI agents and automation workflows.

**Automatic Structured Output:**
- If your tool returns a `dict`, Pydantic model, or dataclass, FastMCP automatically generates a structured output schema and sends JSON data to the client.
- For primitive types (`int`, `str`, `bool`), FastMCP wraps the result under a `"result"` key for structured output.

**Custom Output Schema Example:**
```python
@mcp.tool(output_schema={
  "type": "object",
  "properties": {
    "data": {"type": "string"},
    "metadata": {"type": "object"}
  }
})
def custom_schema_tool() -> dict:
  """Tool with custom output schema."""
  return {"data": "Hello", "metadata": {"version": "1.0"}}
```

**Full Control with ToolResult:**
```python
from fastmcp.tools.tool import ToolResult

@mcp.tool
def advanced_tool() -> ToolResult:
  """Tool with full control over output."""
  return ToolResult(
    content=[TextContent(text="Human-readable summary")],
    structured_content={"data": "value", "count": 42}
  )
```

> See [FastMCP documentation](https://gofastmcp.com/servers/tools) for more details on output schemas and structured content.

- **SSE Transport**: MCP server over SSE (Server-Sent Events) via FastMCP
- **Browser Automation**: Selenium-powered Chrome automation with headless support
- **Comprehensive Toolset** (14 tools):

  - `fetch_url`: Navigate to a URL using a real browser and retrieve the final page content, title, and metadata (handles redirects, bot protection, errors).
  - `find_elements`: Parse the current or specified web page and extract detailed information about elements using CSS selectors or XPath (text, attributes, HTML, visibility).
  - `click_element`: Find and click a page element (button, link, form, etc.), optionally waiting for post-click changes; returns updated page state and metadata.
  - `run_js_interaction`: Execute custom JavaScript in the browser context, with argument support and JSON-serializable results; ideal for advanced DOM interactions.
  - `download_pdfs`: Download PDF files from web pages using multiple strategies (auto-detect, custom selector, or JavaScript-triggered); returns file info and metadata.
  - `web_search`: Perform general web searches using Google or Bing; returns structured results (title, URL, snippet) and metadata.
  - `paper_search`: Search academic literature across Google Scholar, PubMed, IEEE, arXiv, medRxiv, and bioRxiv; returns structured results and metadata.
  - `convert_to_markdown`: Convert HTML content, web pages, or PDFs to Markdown format using MarkItDown; supports URLs and raw HTML.
  - `convert_file_to_markdown`: Convert a local HTML or PDF file to Markdown and write to output; supports extracting specific HTML elements by ID.
  - `save_file`: Save raw content to a file at the specified path (supports large files, returns metadata).
  - `fetch_and_save_url`: Fetch content from a URL (using browser automation) and save it directly to a file.
  - `start_browser`: Start the Selenium browser session (if not already running).
  - `stop_browser`: Stop the Selenium browser session (not the server).
  - `restart_browser`: Restart the Selenium browser session (not the server).
  - `shutdown_server`: Gracefully shut down the MCP server process (safe for automation workflows).
- **Academic Focus**: Specialized search capabilities for research papers and scholarly content
- **Security**: URL validation, domain allowlists, and private IP blocking
- **Robust Error Handling**: Comprehensive error handling and retry logic
- **Smart Driver Management**: Selenium Manager with webdriver-manager fallback

### Example: Modern FastMCP Tool Definition (2025)

```python
from typing import Annotated
from pydantic import Field
from fastmcp import FastMCP

mcp = FastMCP(name="MCPBrowserServer")

@mcp.tool
def fetch_url(
  url: Annotated[str, Field(description="URL to fetch")],
  timeout: Annotated[int, Field(description="Timeout in seconds", ge=1, le=60)] = 30
) -> dict:
  """Navigate to a URL and retrieve page content."""
  # Implementation here
  return {"content": "...", "status": 200}

@mcp.tool
async def web_search(
  query: Annotated[str, Field(description="Search query")],
  engine: Annotated[str, Field(description="Search engine", pattern="^(google|bing)$")] = "google"
) -> dict:
  """Perform a web search using the specified engine."""
  # Implementation here
  return {"results": ["..."]}
```

> **Tip:** Use `Annotated` and `Field` for all tool parameters to expose clear schemas and validation to MCP clients. Async tools are preferred for I/O-bound operations.

## Quick Start

### Installation

1. **Install from PyPI:**
```powershell
pip install navmcp
```

2. **Configure environment (optional):**
```powershell
copy .env.example .env
# Edit .env with your preferences
```

3. **Start the server:**
```powershell
python -m navmcp start
```

4. **Verify it's running:**
```powershell
# Health check
curl http://127.0.0.1:3333/health

# SSE endpoint check 
curl http://127.0.0.1:3333/sse
```

### Alternative Start Methods
```powershell
# Using fastmcp SSE directly (if your fastmcp version supports it)
py -m fastmcp sse navmcp.app:app --host 127.0.0.1 --port 3333

# Using the __main__ module
python -m navmcp
```

## Client Configuration

### Cline / Continue

Add to your `.continue/config.json`:
```json
{
  "mcpServers": {
    "navmcp": {
      "transport": { "type": "sse", "url": "http://127.0.0.1:3333/sse" }
    }
  }
}
```

### VS Code Copilot Chat

Add to VS Code settings:
```json
{
  "mcp.servers": {
    "navmcp": {
      "transport": { "type": "sse", "url": "http://127.0.0.1:3333/sse" }
    }
  }
}
```

### CodeGeeX

Configuration (exact location varies by version):
```json
{
  "name": "navmcp",
  "transport": { "type": "sse", "url": "http://127.0.0.1:3333/sse" }
}
```

## Tools Overview

### Browser Control & Server Management
- `start_browser`: Start the Selenium browser session (if not already running)
- `stop_browser`: Stop the Selenium browser session (not the server)
- `restart_browser`: Restart the Selenium browser session (not the server)
- `shutdown_server`: Gracefully shut down the MCP server process

### Content Fetching & Extraction
- `fetch_url`: Navigate to any URL and retrieve page content with metadata
- `find_elements`: Parse web pages and extract information from elements using CSS or XPath selectors
- `click_element`: Click on page elements and optionally wait for page changes
- `run_js_interaction`: Execute JavaScript code in the browser context

### File Operations
- `download_pdfs`: Download PDF files from web pages using multiple strategies
- `save_file`: Save raw content to a file at the specified path
- `fetch_and_save_url`: Fetch content from a URL and save it directly to a file

### Conversion & Search
- `convert_to_markdown`: Convert HTML content or web pages to clean Markdown format
- `convert_file_to_markdown`: Convert a local HTML or PDF file to markdown and write to output
- `web_search`: General web search (Google/Bing)
- `paper_search`: Academic/literature search (Google Scholar, PubMed, IEEE, arXiv, medRxiv, bioRxiv)

See `mcp.json` in the `navmcp` folder for full tool descriptions and endpoints.

## Configuration

### Environment Variables (.env)

```bash
# Server Configuration
MCP_PORT=3333
MCP_HOST=127.0.0.1

# Browser Configuration  
BROWSER_HEADLESS=true
DOWNLOAD_DIR=.data\downloads
PAGE_LOAD_TIMEOUT_S=30
SCRIPT_TIMEOUT_S=30

# Security
MCP_ALLOWED_HOSTS=
MCP_CORS_ORIGINS=http://127.0.0.1,http://localhost
```

### Browser Configuration

The server automatically:
- Uses Chrome with Selenium Manager (Selenium ≥4.6) for driver management
- Falls back to webdriver-manager on Windows if needed
- Configures headless mode for CI/server environments
- Sets up automatic PDF downloads without prompts
- Creates download directories as needed

### Security Features

- **URL Validation**: Blocks invalid, file://, data:, and javascript: URLs
- **Private IP Blocking**: Prevents access to local/private IP ranges by default
- **Domain Allowlists**: Optional restriction to specific hosts via `MCP_ALLOWED_HOSTS`
- **Rate Limiting**: Built-in protections against abuse

## MCP Tool Schema

All MCP tools now use explicit Annotated parameters with Pydantic Field annotations for proper schema exposure and validation.

## Development

### Running Tests

```powershell
# Install test dependencies (included in requirements.txt)
pip install -r requirements.txt

# Run smoke tests (server must be running)
pytest tests/test_smoke_http.py -v

# Run basic tool tests (requires browser)
pytest tests/test_tools_basic.py -v

# Skip browser tests in CI
$env:SKIP_BROWSER_TESTS="1"
pytest -v
```


### Project Structure

```
```
navmcp/
├── app.py              # FastMCP server and SSE entrypoint
├── browser.py          # Selenium driver lifecycle management
├── tools/              # MCP tool implementations
│   ├── fetch.py        # fetch_url tool
│   ├── parse.py        # find_elements tool  
│   ├── interact.py     # click_element, run_js_interaction
│   ├── pdf.py          # download_pdfs tool
│   ├── convert.py      # convert_to_markdown, convert_file_to_markdown tools
│   ├── save.py         # save_file, fetch_and_save_url tools
│   ├── control.py      # start/stop/restart/shutdown tools
│   └── search.py       # web_search tool
├── utils/              # Shared utilities
│   ├── io.py           # Path and file utilities
│   ├── net.py          # URL validation and security
│   └── parsing.py      # HTML/selector utilities
├── tests/              # Test suites
├── .data/              # Data directory (downloads, logs)
├── requirements.txt    # Python dependencies
└── .env.example        # Environment configuration template
```
## Troubleshooting

### Server Issues
- **Server won't start**: Check if port 3333 is available, verify your Python environment, and ensure all dependencies in `requirements.txt` are installed.
- **Browser errors**: Make sure Chrome is installed and up-to-date. Selenium Manager (Selenium ≥4.6) should auto-manage drivers, but on Windows, `webdriver-manager` is used as fallback.
- **Download issues**: Ensure `.data/downloads` directory exists and is writable. On permission errors, run your shell as administrator.
- **Structured output errors**: If tool results are not returned as JSON, check your return type annotations and output schemas.
- **Async errors**: For async tools, ensure you are not blocking the event loop with sync code. Use `anyio.to_thread.run_sync` for CPU-bound tasks.

### Client Integration
- **Tools not showing**: Confirm the server is running and accessible at `http://127.0.0.1:3333/`. Use `/health` and `/sse` endpoints to verify.
- **CORS errors**: Add your client's origin to `MCP_CORS_ORIGINS` in your `.env` or environment config.
- **Timeout errors**: Increase timeout values in your environment configuration if requests are slow or failing.
- **Schema validation errors**: Ensure your client sends parameters matching the tool's schema (see tool docs or `/sse` endpoint).

### Common Commands
```powershell
# Check server health
curl http://127.0.0.1:3333/health

# Check SSE endpoint (tools/list requires MCP client)
curl http://127.0.0.1:3333/sse

# Run all tests
pytest tests/
```

> For more help, see the [FastMCP documentation](https://gofastmcp.com/servers/tools) and Selenium [driver docs](https://www.selenium.dev/documentation/webdriver/getting_started/).

## Requirements

- **Python**: ≥3.10
- **Chrome**: Installed (or automatically managed by Selenium Manager)
- **Dependencies**: See `requirements.txt`
- **Operating System**: Windows (PowerShell commands), adaptable to other OSes


## License

This project is licensed under the terms of the MIT License. See [LICENSE](./LICENSE) for details.

## Author & Contact

- **Author:** Jianlin Shi
- **GitHub:** [jianlins](https://github.com/jianlins)
- **Project Issues:** [GitHub Issues](https://github.com/jianlins/navmcp/issues)
- **Email:** your-email@example.com (replace with your actual email)

## Useful Links

- [FastMCP Documentation](https://gofastmcp.com/servers/tools)
- [Selenium WebDriver Docs](https://www.selenium.dev/documentation/webdriver/getting_started/)
- [MarkItDown Library](https://github.com/microsoft/markitdown)
- [Pydantic Docs](https://docs.pydantic.dev/)


## Contributing

We welcome contributions! To contribute:

1. **Fork the repository** and create your branch from `main`.
2. **Code style**: Follow [PEP8](https://peps.python.org/pep-0008/) and use type annotations. Run `black` and `ruff` before submitting.
3. **Testing**: Add or update tests in the `tests/` directory. Run all tests with:
  ```powershell
  pytest tests/
  ```
  Make sure your changes pass on Windows and Linux.
4. **Pull Requests**: Open a PR with a clear description of your changes and reference any related issues.
5. **Documentation**: Update the README and docstrings as needed.

> For major changes, open an issue first to discuss your proposal.

## Changelog

### v1.0.0
- Initial release with 14 tools (browser control, fetch, parse, interact, PDF, conversion, file ops, search, shutdown)
- SSE transport with FastMCP
- Chrome automation with Selenium
- Security features and error handling
- Client configuration examples
