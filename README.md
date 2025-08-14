# MCP Browser Tools

A Model Context Protocol (MCP) server that provides browser automation tools over SSE (Server-Sent Events). Built with FastMCP and Selenium, this server enables MCP-capable clients to interact with web pages, extract content, perform automated browser tasks, and access academic search engines.

## Features

- **SSE Transport**: MCP server over SSE (Server-Sent Events) via FastMCP
- **Browser Automation**: Selenium-powered Chrome automation with headless support
- **Seven Core Tools**:
  - `fetch_url`: Navigate to URLs and retrieve page content
  - `find_elements`: Parse web pages and extract element information  
  - `click_element`: Interact with page elements
  - `run_js_interaction`: Execute JavaScript in browser context
  - `download_pdfs`: Download PDF files with multiple strategies (auto/links/js)
  - `web_search`: Academic search across multiple engines (Google Scholar, PubMed, IEEE, arXiv, medRxiv, bioRxiv)
  - `convert_to_markdown`: Convert HTML content or web pages to Markdown format
- **Academic Focus**: Specialized search capabilities for research papers and scholarly content
- **Security**: URL validation, domain allowlists, and private IP blocking
- **Robust Error Handling**: Comprehensive error handling and retry logic
- **Smart Driver Management**: Selenium Manager with webdriver-manager fallback

## Quick Start

### Installation

1. **Clone and setup environment:**
```powershell
git clone <repository-url>
cd mcp-browser
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. **Configure environment (optional):**
```powershell
copy .env.example .env
# Edit .env with your preferences
```

3. **Start the server:**
```powershell
python -m server.app
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
py -m fastmcp sse server.app:app --host 127.0.0.1 --port 3333

# Using the __main__ module
python -m server
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

### 1. `fetch_url`
Navigate to any URL and retrieve page content with metadata.

**Input:**
- `url` (string): The URL to fetch

**Output:**
- `final_url`: Final URL after redirects
- `title`: Page title
- `html`: Page HTML content
- `status`: Success/error status
- `metadata`: Additional page information

### 2. `find_elements`
Parse web pages and extract information from elements using CSS or XPath selectors.

**Input:**
- `selector` (string): CSS or XPath selector
- `by` (string): "css" or "xpath" 
- `url` (string, optional): URL to navigate to first
- `max_results` (integer, optional): Maximum elements to return

**Output:**
- `count`: Number of elements found
- `elements`: Array of element information (text, attributes, HTML)
- `url`: Current page URL
- `metadata`: Selector and page information

### 3. `click_element`
Click on page elements and optionally wait for page changes.

**Input:**
- `selector` (string): Element selector
- `by` (string): "css" or "xpath"
- `url` (string, optional): URL to navigate to first
- `wait_for_selector` (string, optional): Wait for this element after click
- `wait_for_url_change` (boolean, optional): Wait for URL change
- `timeout_s` (integer, optional): Maximum wait time

**Output:**
- `success`: Whether click succeeded
- `final_url`: URL after click and navigation
- `title`: Page title after click
- `html`: Updated page HTML
- `metadata`: Click and page information

### 4. `run_js_interaction`
Execute JavaScript code in the browser context.

**Input:**
- `script` (string): JavaScript code to execute
- `url` (string, optional): URL to navigate to first
- `args` (array, optional): Arguments to pass to script

**Output:**
- `result`: Script execution result (JSON-serializable)
- `logs`: Console logs from execution
- `url`: Current page URL
- `metadata`: Execution information

### 5. `download_pdfs`
Download PDF files from web pages using multiple strategies.

**Input:**
- `url` (string): Page URL to process
- `strategy` (string): "auto", "links", or "js"
- `link_selector` (string, optional): CSS selector for PDF links (links strategy)
- `js_action` (string, optional): JavaScript to trigger download (js strategy)
- `max_files` (integer, optional): Maximum files to download

**Output:**
- `success`: Whether downloads succeeded
- `downloaded_files`: List of downloaded file information
- `directory`: Download directory path
- `metadata`: Download process information

### 6. `web_search`
Search academic databases and repositories for research papers and scholarly content.

**Input:**
- `query` (string): Search query
- `engine` (string): Search engine - "google_scholar", "pubmed", "ieee", "arxiv", "medrxiv", "biorxiv"
- `num_results` (integer, optional): Maximum results to return (default: 10)

**Output:**
- `success`: Whether search succeeded
- `results`: Array of search results with title, URL, snippet, authors, etc.
- `metadata`: Search engine and query information

**Supported Academic Engines:**
- **Google Scholar**: General academic search
- **PubMed**: Biomedical literature
- **IEEE Xplore**: Engineering and technology papers
- **arXiv**: Preprints in physics, mathematics, computer science
- **medRxiv**: Medical preprints
- **bioRxiv**: Biology preprints

### 7. `convert_to_markdown`
Convert HTML content or web pages to clean Markdown format.

**Input:**
- `content` (string, optional): HTML content to convert
- `url` (string, optional): URL to fetch and convert
- `content_type` (string, optional): Content type hint

**Output:**
- `success`: Whether conversion succeeded
- `markdown`: Converted Markdown content
- `metadata`: Conversion information

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
│   │   └── search.py       # web_search tool
│   └── utils/              # Shared utilities
│       ├── io.py           # Path and file utilities
│       ├── net.py          # URL validation and security
│       └── parsing.py      # HTML/selector utilities
├── tests/                  # Test suites
├── .data/                  # Data directory (downloads, logs)
├── requirements.txt        # Python dependencies
└── .env.example           # Environment configuration template
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
- Initial release with all six core tools
- SSE transport with FastMCP
- Chrome automation with Selenium
- Security features and error handling
- Client configuration examples