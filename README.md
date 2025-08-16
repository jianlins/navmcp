# MCP Browser Tools

A Model Context Protocol (MCP) server that provides browser automation tools over SSE (Server-Sent Events). Built with FastMCP and Selenium, this server enables MCP-capable clients to interact with web pages, extract content, perform automated browser tasks, and access academic search engines.

## Features

- **SSE Transport**: MCP server over SSE (Server-Sent Events) via FastMCP
- **Browser Automation**: Selenium-powered Chrome automation with headless support
- **Comprehensive Toolset** (14 tools):
  - `fetch_url`: Navigate to URLs and retrieve page content
  - `find_elements`: Parse web pages and extract element information  
  - `click_element`: Interact with page elements
  - `run_js_interaction`: Execute JavaScript in browser context
  - `download_pdfs`: Download PDF files with multiple strategies (auto/links/js)
  - `web_search`: General web search (Google by default, Bing if specified)
  - `paper_search`: Academic/literature search across multiple engines (Google Scholar, PubMed, IEEE, arXiv, medRxiv, bioRxiv)
  - `convert_to_markdown`: Convert HTML content or web pages to Markdown format
  - `convert_file_to_markdown`: Convert a local HTML or PDF file to markdown and write to output
  - `save_file`: Save raw content to a file at the specified path
  - `fetch_and_save_url`: Fetch content from a URL and save it directly to a file
  - `start_browser`: Start the Selenium browser session (if not already running)
  - `stop_browser`: Stop the Selenium browser session (not the server)
  - `restart_browser`: Restart the Selenium browser session (not the server)
  - `shutdown_server`: Gracefully shut down the MCP server process
- **Academic Focus**: Specialized search capabilities for research papers and scholarly content
- **Security**: URL validation, domain allowlists, and private IP blocking
- **Robust Error Handling**: Comprehensive error handling and retry logic
- **Smart Driver Management**: Selenium Manager with webdriver-manager fallback

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
py -m fastmcp sse mbrowser.app:app --host 127.0.0.1 --port 3333

# Using the __main__ module
python -m mbrowser
```

## Client Configuration

### Cline / Continue

Add to your `.continue/config.json`:
```json
{
  "mcpServers": {
    "mcp-browser": {
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
    "mcp-browser": {
      "transport": { "type": "sse", "url": "http://127.0.0.1:3333/sse" }
    }
  }
}
```

### CodeGeeX

Configuration (exact location varies by version):
```json
{
  "name": "mcp-browser",
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

See `mcp.json` for full tool descriptions and endpoints.

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
mcp-browser/
├── server/
│   ├── app.py              # FastMCP server and SSE entrypoint
│   ├── browser.py          # Selenium driver lifecycle management
│   ├── tools/              # MCP tool implementations
│   │   ├── fetch.py        # fetch_url tool
│   │   ├── parse.py        # find_elements tool  
│   │   ├── interact.py     # click_element, run_js_interaction
│   │   ├── pdf.py          # download_pdfs tool
│   │   ├── convert.py      # convert_to_markdown, convert_file_to_markdown tools
│   │   ├── save.py         # save_file, fetch_and_save_url tools
│   │   ├── control.py      # start/stop/restart/shutdown tools
│   │   └── search.py       # web_search tool
│   └── utils/              # Shared utilities
│       ├── io.py           # Path and file utilities
│       ├── net.py          # URL validation and security
│       └── parsing.py      # HTML/selector utilities
├── tests/                  # Test suites
├── .data/                  # Data directory (downloads, logs)
├── requirements.txt        # Python dependencies
└── .env.example            # Environment configuration template
```

## Troubleshooting

### Server Issues

- **Server won't start**: Check if port 3333 is available, verify Python environment
- **Browser errors**: Ensure Chrome is installed or let Selenium Manager handle it
- **Download issues**: Check that `.data/downloads` directory is writable

### Client Integration

- **Tools not showing**: Verify server is running and accessible at `http://127.0.0.1:3333/`
- **CORS errors**: Add your client's origin to `MCP_CORS_ORIGINS`
- **Timeout errors**: Increase timeout values in environment configuration

### Common Commands

```powershell
# Check server health
curl http://127.0.0.1:3333/health

# Check SSE endpoint (tools/list requires MCP client)
curl http://127.0.0.1:3333/sse

# Note: Tool calls require an MCP client with SSE support
# Use pytest tests or MCP clients for testing functionality
```

## Requirements

- **Python**: ≥3.10
- **Chrome**: Installed (or automatically managed by Selenium Manager)
- **Dependencies**: See `requirements.txt`
- **Operating System**: Windows (PowerShell commands), adaptable to other OSes

## License

[Add your license here]

## Contributing

[Add contributing guidelines here]

## Changelog

### v1.0.0
- Initial release with 14 tools (browser control, fetch, parse, interact, PDF, conversion, file ops, search, shutdown)
- SSE transport with FastMCP
- Chrome automation with Selenium
- Security features and error handling
- Client configuration examples
